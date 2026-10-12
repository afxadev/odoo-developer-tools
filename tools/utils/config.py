# Copyright (c) 2015-2018 ACSONE SA/NV
# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import yaml

DEFAULT_CONFIG_NAME = ".odt.yaml"


def find_default_config(cwd: Optional[Path] = None) -> Optional[Path]:
    candidate = (cwd or Path.cwd()) / DEFAULT_CONFIG_NAME
    return candidate if candidate.is_file() else None


def is_blank(value: Any) -> bool:
    if isinstance(value, (list, tuple, dict, str)):
        return len(value) == 0
    return value is None


def read_yaml(path: Path) -> Dict[str, Any]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return data


def _clean(raw, base, fields, path_keys, aliases) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, value in raw.items():
        key = aliases.get(key, key)
        if key not in fields:
            raise ValueError(f"Unknown config key: {key!r}")
        if is_blank(value):
            continue
        if key in path_keys:
            if isinstance(value, (list, tuple)):
                value = [base / p for p in value]
            else:
                value = base / value
        out[key] = value
    return out


def load_entries(
    path: Optional[Path],
    section: str,
    *,
    fields: Iterable[str],
    shared_keys: Iterable[str] = (),
    path_keys: Iterable[str] = (),
    aliases: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    if path is None:
        return [{}]
    path = Path(path)
    data = read_yaml(path)
    fields, path_keys, aliases = set(fields), set(path_keys), aliases or {}
    base = path.parent
    shared = _clean(
        {k: data[k] for k in shared_keys if k in data}, base, fields, path_keys, aliases
    )
    raw = data.get(section) or {}
    entries = raw if isinstance(raw, list) else [raw]
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: '{section}' entries must be mappings")
        merged = dict(shared)
        merged.update(_clean(entry, base, fields, path_keys, aliases))
        result.append(merged)
    return result or [dict(shared)]
