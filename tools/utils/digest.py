# Copyright (c) 2015-2018 ACSONE SA/NV
# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)

from __future__ import annotations

import hashlib
from pathlib import Path


def compute_digest(manifest_path, fragments_dir, relative_to, extra: str = "") -> str:
    h = hashlib.sha256()
    relative_to = Path(relative_to)
    files = [Path(manifest_path)]
    fragments_dir = Path(fragments_dir)
    if fragments_dir.is_dir():
        files += sorted(
            p
            for p in fragments_dir.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts
        )
    for path in files:
        h.update(path.relative_to(relative_to).as_posix().encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    h.update(extra.encode())
    return f"sha256:{h.hexdigest()}"
