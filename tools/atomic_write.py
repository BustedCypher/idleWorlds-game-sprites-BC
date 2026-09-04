#!/usr/bin/env python3
"""The only sanctioned way for a tool in this repo to overwrite a file.

`open(path, 'w')` — and everything built on it, including `Path.write_text`,
`Path.write_bytes` and `PIL.Image.save(path)` — truncates the target the
instant it opens it, BEFORE the encoder has looked at a single byte. Any later
failure (an unencodable character, a full disk, a killed process) therefore
leaves a 0-byte or half-written file where your only copy used to be. There is
no rollback and no warning.

That is not hypothetical: on 2026-09-04 it emptied `index.html`, all 4 MB of
it, during a nine-line edit. See the "Never patch index.html by rewriting the
whole file" section of CLAUDE.md.

Serialise to memory, then `os.replace()` a sibling temp file into position.
os.replace is atomic on Windows and POSIX alike: a reader sees the old file or
the new one, never neither.

`tests/test_no_unsafe_writes.py` enforces that every writing tool comes
through here.
"""
from __future__ import annotations
import os, tempfile
from pathlib import Path


def replace_atomically(path: str | Path, data: bytes) -> None:
    """Replace `path`'s contents with `data`, all-or-nothing."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError('replace_atomically takes bytes; encode first so an '
                        'encoding failure happens before the file is touched')
    path = Path(path)
    handle, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(handle, 'wb') as out:  # guard-ok: writes the temp file, not the target
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_text_atomically(path: str | Path, text: str, encoding: str = 'utf-8') -> None:
    """Encode first, then replace. The encode is what usually fails, and doing
    it up front means a failure costs you nothing."""
    replace_atomically(path, text.encode(encoding))
