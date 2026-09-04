"""Static gate: no tool may truncate a repo file it is trying to edit.

The 2026-09-04 incident emptied index.html because a script did
`Path.write_text()` on it — a call that truncates the target before the
encoder has looked at the payload, so the mid-write exception destroyed 4 MB
and wrote nothing back. `tools/atomic_write.py` is the fix; this test is what
stops the pattern coming back the next time someone is in a hurry.

Two rules over tools/ and tests/, both AST-based so they cannot be fooled by
formatting:

  1. No truncating write (`open(..., 'w')`, `Path.write_text`,
     `Path.write_bytes`, `Image.save(<a path>)`). Route through
     `replace_atomically` / `write_text_atomically` instead.
  2. No text read or write without an explicit `encoding=`. The locale default
     is cp1252 on Windows and cannot even decode index.html, which holds 219
     literal emoji — which is why every tool in this repo had to be run under
     PYTHONUTF8=1 to work at all until this gate found them.

A genuinely safe site — writing a temp file, or a brand-new content-addressed
artefact — is allowed with a trailing `# guard-ok: <why>` comment. That is
deliberately noisy: it forces the author to say out loud that a failed write
there destroys nothing.
"""
from __future__ import annotations
import ast, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# tests/ is in scope too: test_repository_icon_contract.py carried the same
# missing-encoding bug, which is why every tool had to be run with
# PYTHONUTF8=1 on Windows to work at all.
SCANNED = [ROOT / 'tools', ROOT / 'tests']
ALLOW_MARKER = '# guard-ok'
TRUNCATING_METHODS = {'write_text', 'write_bytes'}
ENCODING_SENSITIVE = {'read_text', 'write_text'}


def python_sources() -> list[Path]:
    return sorted(p for d in SCANNED for p in d.glob('*.py')
                  if not p.name.startswith('_'))


def marked_ok(lines: list[str], node: ast.AST) -> bool:
    """True when the escape hatch sits on the call's own line, on the line that
    opens a multi-line call, or on the line immediately above it. The line
    above is allowed because several of these tools pack a whole statement
    into 140 characters, where a trailing comment would be unreadable — and,
    worse, where appending one can silently comment out the rest of the
    statement. That is not hypothetical: doing exactly that to this repo's
    audit-file write dropped `runtime['audit_path']` from the manifest."""
    span = {getattr(node, 'lineno', 0), getattr(node, 'end_lineno', 0),
            getattr(node, 'lineno', 0) - 1}
    return any(ALLOW_MARKER in lines[n - 1] for n in span if 0 < n <= len(lines))


def call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ''


def keyword(node: ast.Call, name: str):
    return next((k.value for k in node.keywords if k.arg == name), None)


def positional(node: ast.Call, index: int):
    return node.args[index] if len(node.args) > index else None


def literal(node) -> str:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else ''


def is_file_open(node: ast.Call) -> bool:
    """`open(p)` and `p.open()` open files. `Image.open(p)` does not — nor does
    anything else called on a capitalised receiver, which by convention is a
    class or module rather than a path object."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == 'open'
    if isinstance(func, ast.Attribute) and func.attr == 'open':
        receiver = func.value
        return not (isinstance(receiver, ast.Name) and receiver.id[:1].isupper())
    return False


def open_mode(node: ast.Call) -> str:
    """Mode is the 2nd positional for builtin `open(file, mode)` but the 1st
    for `Path.open(mode)`. Reading the wrong slot makes every `p.open('rb')`
    look like a text write."""
    slot = 1 if isinstance(node.func, ast.Name) else 0
    return literal(keyword(node, 'mode') or positional(node, slot)) or 'r'


def looks_like_a_path(node: ast.AST) -> bool:
    """Rough but conservative: a string literal, a Path division, or a name
    that reads like a filename. A BytesIO/StringIO buffer matches none."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return True
    if isinstance(node, ast.Name):
        return any(w in node.id.lower() for w in ('path', 'file', 'dest', 'target', 'out'))
    if isinstance(node, ast.Attribute):
        return any(w in node.attr.lower() for w in ('path', 'file'))
    return False


def scan(path: Path) -> tuple[list[str], list[str]]:
    source = path.read_text(encoding='utf-8')
    lines = source.splitlines()
    tree = ast.parse(source)
    # Sites inside the sanctioned helper are the implementation of the rule,
    # not a violation of it.
    sanctioned = {n for fn in ast.walk(tree)
                  if isinstance(fn, ast.FunctionDef)
                  and fn.name in ('replace_atomically', 'write_text_atomically')
                  for n in ast.walk(fn)}

    truncating, unencoded = [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or node in sanctioned or marked_ok(lines, node):
            continue
        name = call_name(node)
        where = f'{path.name}:{node.lineno}'

        opening = is_file_open(node)
        mode = open_mode(node) if opening else ''

        if name in TRUNCATING_METHODS:
            truncating.append(f'{where}  .{name}() truncates its target')
        elif opening and ('w' in mode or 'a' in mode):
            truncating.append(f'{where}  open(..., {mode!r}) truncates its target')
        elif name == 'save' and node.args and looks_like_a_path(node.args[0]):
            truncating.append(f'{where}  .save(<path>) truncates its target; '
                              'encode to a BytesIO and replace_atomically instead')

        # Binary handles carry no encoding, so only text I/O is in scope.
        text_io = name in ENCODING_SENSITIVE or (opening and 'b' not in mode)
        if text_io and keyword(node, 'encoding') is None:
            unencoded.append(f'{where}  {name}() with no encoding= '
                             '(the locale default is cp1252 on Windows, which '
                             'cannot even decode index.html)')
    return truncating, unencoded


class NoUnsafeWrites(unittest.TestCase):
    def test_no_truncating_writes(self):
        found = [problem for path in python_sources() for problem in scan(path)[0]]
        self.assertEqual(found, [], '\n  ' + '\n  '.join(found) if found else '')

    def test_no_unencoded_text_io(self):
        found = [problem for path in python_sources() for problem in scan(path)[1]]
        self.assertEqual(found, [], '\n  ' + '\n  '.join(found) if found else '')

    def test_the_gate_actually_catches_the_2026_09_04_pattern(self):
        """A check nobody has watched fail is not a check."""
        import tempfile
        with tempfile.TemporaryDirectory() as box:
            bad = Path(box) / 'oops.py'
            bad.write_text(  # guard-ok: throwaway fixture in a temp dir
                'from pathlib import Path\n'
                'def edit(p):\n'
                "    s = Path(p).read_text(encoding='utf-8')\n"
                "    Path(p).write_text(s + 'x', encoding='utf-8')\n"
                "    open(p, 'w').write('again')\n"
                "    img.save(atlas_path)\n",
                encoding='utf-8')
            truncating, _ = scan(bad)
        self.assertEqual(len(truncating), 3,
                         'expected write_text, open(w) and save(path) to be caught, '
                         f'got: {truncating}')

    def test_the_escape_hatch_works_and_is_explicit(self):
        import tempfile
        with tempfile.TemporaryDirectory() as box:
            ok = Path(box) / 'fine.py'
            ok.write_text(  # guard-ok: throwaway fixture in a temp dir
                'from pathlib import Path\n'
                'def edit(tmp):\n'
                "    Path(tmp).write_text('x', encoding='utf-8')  # guard-ok: temp file\n",
                encoding='utf-8')
            truncating, unencoded = scan(ok)
        self.assertEqual(truncating, [])
        self.assertEqual(unencoded, [])


if __name__ == '__main__':
    unittest.main()
