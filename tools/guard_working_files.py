#!/usr/bin/env python3
"""Tripwire + rolling backup for the files this repo cannot regenerate.

Why this exists
---------------
On 2026-09-04 a Python read-modify-write truncated `index.html` to 0 bytes.
`open(path, 'w')` empties the target before the encoder has seen a byte, so an
exception mid-write destroys the file and writes nothing back. Nobody noticed
for several minutes, and the only reason nothing was lost is that the file
happened to be committed.

Three defences, in order of how much they save you:

  1. `replace_atomically()` in the writing tools — the corruption never happens.
  2. This script, wired to Claude Code hooks (see .claude/settings.json) — the
     corruption is caught on the very next tool call, and a known-good copy is
     always one command away.
  3. `tests/test_no_unsafe_writes.py` — the dangerous pattern cannot be
     reintroduced into tools/ without a test failing.

Modes
-----
  --check     Report integrity as JSON. Exit 0 clean, 1 damaged.
  --guard     Hook mode. Verify; if damaged, exit 2 with restore instructions
              (Claude Code feeds a blocking error back to the model). If clean
              and the content changed, take a snapshot.
  --snapshot  Snapshot now if clean and changed. Never blocks. (SessionStart.)
  --restore   Copy the newest snapshot of each damaged file back into place.
  --self-test Prove the checks actually fail on damaged fixtures.

Deliberately dependency-free (no Pillow) and byte-level (no decode), so it is
fast enough to run on every tool call and cannot itself fail on an encoding.
"""
from __future__ import annotations
import os, struct, sys
from pathlib import Path

# json (24 ms), shutil (11 ms) and hashlib (9 ms) are imported at their call
# sites, not here. This runs on EVERY Bash/Write/Edit call, and the common
# path — nothing touched a guarded file — must not pay for a module it never
# uses. Same reason the ledger below is tab-separated text rather than JSON.

ROOT = Path(os.environ.get('IW_GUARD_ROOT') or Path(__file__).resolve().parents[1]).resolve()
BACKUPS = ROOT / '.claude' / 'backups'
KEEP_SNAPSHOTS = 8
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


# ── integrity checks ───────────────────────────────────────────
# Each returns a list of failure strings. Empty means intact — the same
# contract the in-page self-check suites use.

def check_html(path: Path, min_bytes: int, must_contain: list[bytes], min_scripts: int) -> list[str]:
    if not path.is_file():
        return ['missing']
    data = path.read_bytes()
    fail = []
    if len(data) < min_bytes:
        fail.append(f'truncated: {len(data)} bytes, expected at least {min_bytes}')
        return fail  # everything below would just restate this
    if not data.lstrip()[:15].lower().startswith(b'<!doctype html'):
        fail.append('does not start with <!doctype html>')
    if not data.rstrip().endswith(b'</html>'):
        fail.append('does not end with </html> - write cut short')
    for needle in must_contain:
        if needle not in data:
            fail.append('missing required marker: ' + needle.decode('utf-8', 'replace'))
    scripts = data.count(b'<script')
    if scripts < min_scripts:
        fail.append(f'only {scripts} <script> tags, expected at least {min_scripts}')
    return fail


def check_png(path: Path, min_bytes: int, cell: int = 128) -> list[str]:
    if not path.is_file():
        return ['missing']
    size = path.stat().st_size
    if size < min_bytes:
        return [f'truncated: {size} bytes, expected at least {min_bytes}']
    with path.open('rb') as handle:
        head = handle.read(33)
        handle.seek(-12, os.SEEK_END)
        tail = handle.read(12)
    fail = []
    if not head.startswith(PNG_MAGIC):
        fail.append('not a PNG (bad magic)')
        return fail
    width, height = struct.unpack('>II', head[16:24])
    if width % cell or height % cell:
        fail.append(f'{width}x{height} is not a whole number of {cell}px cells')
    if b'IEND' not in tail:
        fail.append('no IEND chunk - encode cut short')
    return fail


def check_text(path: Path, min_bytes: int, header: bytes) -> list[str]:
    if not path.is_file():
        return ['missing']
    size = path.stat().st_size
    if size < min_bytes:
        return [f'truncated: {size} bytes, expected at least {min_bytes}']
    with path.open('rb') as handle:
        if not handle.read(len(header)) == header:
            return ['header row changed or file rewritten']
    return []


# Floors are set well below the real sizes: they catch truncation and
# half-writes without needing an update every time a row is added.
GUARDED = {
    'index.html': lambda p: check_html(
        p, 3_000_000,
        [b'id="iw-embedded-items"', b'icon-manifest.', b'IWIconSpritesV2'], 20),
    'item_icons_atlas.png': lambda p: check_png(p, 5_000_000),
    'gear_icons_atlas.png': lambda p: check_png(p, 5_000_000),
    'item_icons_cells.csv': lambda p: check_text(p, 40_000, b'index,row,column'),
    'item_icons_index.csv': lambda p: check_text(p, 200_000, b'item_id,name,category'),
    'gear_icons_manifest.json': lambda p: check_text(p, 40_000, b'{'),
}
# Snapshotting is limited to files that are small, hand-edited and
# irreplaceable. The atlases are large and rebuildable from their sources;
# they are checked but not copied, so the hook stays cheap.
SNAPSHOT = ['index.html', 'item_icons_cells.csv', 'item_icons_index.csv']


def verify(names: list[str] | None = None) -> dict:
    todo = names if names is not None else list(GUARDED)
    return {name: GUARDED[name](ROOT / name) for name in todo}


# ── change detection ───────────────────────────────────────────
# The hook runs on every Bash/Write/Edit call, and almost none of them touch a
# guarded file. Re-reading 4 MB and hashing it each time costs ~115 ms; a
# (size, mtime) ledger of the last VERIFIED-CLEAN state cuts that to a few
# stat() calls. It fails safe: any difference at all, however it arose, drops
# through to the full byte-level check.

STATE = BACKUPS / 'guard-state.tsv'


def load_state() -> dict:
    try:
        rows = STATE.read_text(encoding='utf-8').splitlines()
        return {n: s for n, _, s in (r.partition('\t') for r in rows if '\t' in r)}
    except OSError:
        return {}


def save_state(state: dict) -> None:
    try:
        BACKUPS.mkdir(parents=True, exist_ok=True)
        body = ''.join(f'{n}\t{s}\n' for n, s in sorted(state.items()))
        tmp = STATE.with_suffix('.tmp')
        tmp.write_text(body, encoding='utf-8')  # guard-ok: writes the temp file, not the ledger
        os.replace(tmp, STATE)
    except OSError:
        pass  # a lost ledger only costs speed on the next run, never safety


def stamp(path: Path) -> str:
    """Identity of a file as the ledger records it. '-' means absent, which
    never equals a recorded stamp, so a deleted file always re-checks."""
    try:
        info = path.stat()
        return f'{info.st_size}:{info.st_mtime_ns}'
    except OSError:
        return '-'


def changed_since_verified(state: dict) -> list[str]:
    return [name for name in GUARDED if state.get(name) != stamp(ROOT / name)]


# ── snapshots ──────────────────────────────────────────────────

def digest(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def snapshots_for(name: str) -> list[Path]:
    return sorted(BACKUPS.glob(name + '.*.bak'))


def snapshot(name: str) -> str | None:
    """Copy ROOT/name into .claude/backups if its content is new. Returns the
    new snapshot's name, or None if an identical one already exists."""
    import shutil, tempfile, time
    source = ROOT / name
    if not source.is_file():
        return None
    existing = snapshots_for(name)
    current = digest(source)
    if existing and digest(existing[-1]) == current:
        return None
    BACKUPS.mkdir(parents=True, exist_ok=True)
    when = time.strftime('%Y%m%d-%H%M%S')
    target = BACKUPS / f'{name}.{when}-{current[:8]}.bak'
    handle, tmp = tempfile.mkstemp(dir=str(BACKUPS), suffix='.tmp')
    os.close(handle)
    shutil.copyfile(source, tmp)
    os.replace(tmp, target)
    for stale in snapshots_for(name)[:-KEEP_SNAPSHOTS]:
        stale.unlink(missing_ok=True)
    return target.name


def restore(name: str) -> str:
    import shutil, tempfile
    existing = snapshots_for(name)
    if not existing:
        return 'no snapshot available'
    newest = existing[-1]
    handle, tmp = tempfile.mkstemp(dir=str(ROOT), prefix=name + '.', suffix='.tmp')
    os.close(handle)
    shutil.copyfile(newest, tmp)
    os.replace(tmp, ROOT / name)
    return 'restored from ' + newest.name


# ── self-test ──────────────────────────────────────────────────

def self_test() -> list[str]:
    """Break each check on purpose. A gate nobody has seen fail is not a gate."""
    import tempfile
    fail = []

    def expect(label: str, problems: list[str], want_damage: bool):
        if bool(problems) != want_damage:
            fail.append(f'{label}: got {problems!r}, expected '
                        + ('a failure' if want_damage else 'no failures'))

    with tempfile.TemporaryDirectory() as box:
        d = Path(box)
        good_html = (b'<!doctype html>\n<script id="iw-embedded-items">[]</script>'
                     + b'<script>x</script>' * 25
                     + b'icon-manifest.abcdef123456.json IWIconSpritesV2\n'
                     + b'<!--' + b'.' * 3_000_000 + b'-->\n</html>\n')
        html = d / 'index.html'
        html.write_bytes(good_html)  # guard-ok: throwaway fixture in a temp dir
        expect('intact html', check_html(html, 3_000_000, [b'id="iw-embedded-items"'], 20), False)

        html.write_bytes(b'')  # guard-ok: throwaway fixture in a temp dir
        expect('0-byte html (the 2026-09-04 failure)',
               check_html(html, 3_000_000, [b'id="iw-embedded-items"'], 20), True)

        html.write_bytes(good_html[:len(good_html) // 2])  # guard-ok: throwaway fixture in a temp dir
        expect('half-written html', check_html(html, 3_000_000, [b'id="iw-embedded-items"'], 20), True)

        html.write_bytes(good_html.replace(b'id="iw-embedded-items"', b'id="gone"'))  # guard-ok: throwaway fixture in a temp dir
        expect('html missing its payload tag',
               check_html(html, 3_000_000, [b'id="iw-embedded-items"'], 20), True)

        html.write_bytes(good_html.replace(b'</html>', b''))  # guard-ok: throwaway fixture in a temp dir
        expect('html with no closing tag',
               check_html(html, 3_000_000, [b'id="iw-embedded-items"'], 20), True)

        png = d / 'atlas.png'
        body = PNG_MAGIC + b'\0\0\0\rIHDR' + struct.pack('>II', 1280, 6144) + b'\0' * 5_000_100
        png.write_bytes(body + b'\0\0\0\0IEND\xaeB`\x82')  # guard-ok: throwaway fixture in a temp dir
        expect('intact png', check_png(png, 5_000_000), False)
        png.write_bytes(body)  # guard-ok: throwaway fixture in a temp dir
        expect('png with no IEND', check_png(png, 5_000_000), True)
        png.write_bytes(PNG_MAGIC + b'\0\0\0\rIHDR' + struct.pack('>II', 1280, 6100)  # guard-ok: throwaway fixture in a temp dir
                        + b'\0' * 5_000_100 + b'IEND')
        expect('png with a partial cell row', check_png(png, 5_000_000), True)
        png.write_bytes(b'')  # guard-ok: throwaway fixture in a temp dir
        expect('0-byte png', check_png(png, 5_000_000), True)

        csv = d / 'rows.csv'
        csv.write_bytes(b'index,row,column\r\n' + b'x' * 40_000)  # guard-ok: throwaway fixture in a temp dir
        expect('intact csv', check_text(csv, 40_000, b'index,row,column'), False)
        csv.write_bytes(b'')  # guard-ok: throwaway fixture in a temp dir
        expect('0-byte csv', check_text(csv, 40_000, b'index,row,column'), True)
        csv.write_bytes(b'wrong,header,here\r\n' + b'x' * 40_000)  # guard-ok: throwaway fixture in a temp dir
        expect('csv with a mangled header', check_text(csv, 40_000, b'index,row,column'), True)

        expect('missing file', check_html(d / 'nope.html', 1, [], 0), True)
    return fail


# ── entry point ────────────────────────────────────────────────

def damaged(report: dict) -> dict:
    return {k: v for k, v in report.items() if v}


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else '--check'

    import json

    if mode == '--self-test':
        problems = self_test()
        print(json.dumps({'checks_exercised': 12, 'failures': problems}, indent=2))
        return 1 if problems else 0

    if mode == '--restore':
        broken = damaged(verify())
        if not broken:
            print('nothing to restore - all guarded files are intact')
            return 0
        for name in broken:
            print(f'{name}: {restore(name)}')
        STATE.unlink(missing_ok=True)  # a restored file needs re-verifying
        still = damaged(verify())
        print('remaining problems:', json.dumps(still) if still else 'none')
        return 1 if still else 0

    # --check always looks at everything. The hook modes look only at what the
    # ledger says has moved since it was last confirmed intact.
    hook_mode = mode in ('--guard', '--snapshot')
    state = load_state() if hook_mode else {}
    touched = changed_since_verified(state) if hook_mode else list(GUARDED)
    report = verify(touched)
    broken = damaged(report)

    if broken:
        # ASCII only: this goes to a Windows console whose stderr is cp1252,
        # and a mojibake'd warning reads as noise exactly when it must not.
        lines = ['GUARDED FILE DAMAGED - stop and repair before doing anything else.', '']
        for name, problems in broken.items():
            lines.append(f'  {name}: ' + '; '.join(problems))
            snaps = snapshots_for(name)
            lines.append('    newest snapshot: ' + (snaps[-1].name if snaps else 'NONE'))
        lines += ['', 'Restore with:', '  python tools/guard_working_files.py --restore',
                  'or, if no snapshot exists:', '  git restore <file>', '',
                  'Do NOT continue editing. See the "Never patch index.html by '
                  'rewriting the whole file" section of CLAUDE.md.']
        sys.stderr.write('\n'.join(lines) + '\n')
        return 2 if mode == '--guard' else 1

    if hook_mode:
        taken = {n: s for n in touched if n in SNAPSHOT and (s := snapshot(n))}
        # Only record a file as verified AFTER it passed, so a damaged file is
        # re-reported on every subsequent call until someone fixes it.
        for name in touched:
            mark = stamp(ROOT / name)
            if mark:
                state[name] = mark
        save_state(state)
        if taken and mode == '--snapshot':
            print('snapshotted: ' + ', '.join(taken))
        return 0

    print(json.dumps({'root': str(ROOT), 'status': 'ok', 'checked': sorted(report)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
