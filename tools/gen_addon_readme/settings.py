# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)
# Copyright (c) 2018 ACSONE SA/NV
# Copyright (c) 2018 GRAP (http://www.grap.coop)
from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.utils.config import load_entries

CONFIG_SECTION = "addon_readme"
SHARED_KEYS = ("repo_url", "provider", "branch", "default_branch", "prefix_image_url", "extra_badges")
PATH_KEYS = ("addons_dir", "addon_dirs", "template_file")
ALIASES = {"template_file_name": "template_file", "template_filename": "template_file"}


@dataclass
class Settings:
    addons_dir: Optional[Path] = None
    addon_dirs: List[Path] = field(default_factory=list)
    template_file: Optional[Path] = None
    repo_url: str = ""
    branch: str = ""
    default_branch: str = ""  # main branch (used by target=internal); default: detected
    target: str = ""  # internal | repo | custom ("" = custom if prefix_image_url else internal)
    provider: str = ""  # github | gitlab | bitbucket | gitea ("" = guess from repo_url host)
    prefix_image_url: str = ""  # only for target=custom
    fragments_dir: str = "readme"
    gen_html: bool = True
    check_rst: bool = True
    keep_source_digest: bool = False
    if_source_changed: bool = False
    convert_fragments_to_markdown: bool = False
    extra_badges: List[Dict[str, str]] = field(default_factory=list)


def build_settings(config_path: Optional[Path], cli: Dict[str, Any]) -> List[Settings]:
    cli = {k: v for k, v in cli.items() if v is not None and v != ()}
    if "addon_dirs" in cli:
        cli["addon_dirs"] = list(cli["addon_dirs"])
    entries = load_entries(
        config_path,
        CONFIG_SECTION,
        fields=[f.name for f in fields(Settings)],
        shared_keys=SHARED_KEYS,
        path_keys=PATH_KEYS,
        aliases=ALIASES,
    )
    return [Settings(**{**entry, **cli}) for entry in entries]
