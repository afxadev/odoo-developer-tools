# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)
# Copyright (c) 2018 ACSONE SA/NV
# Copyright (c) 2018 GRAP (http://www.grap.coop)
from __future__ import annotations

import posixpath
import re
from typing import Dict
from urllib.parse import urljoin

TARGETS = ("internal", "repo", "custom")
INTERNAL_IMAGE_PREFIX = "/{addon_name}/"
RAW_IMAGE_PREFIXES = {
    "github": "https://raw.githubusercontent.com/{org_name}/{repo_name}/{branch}/{addon_name}/",
    "gitlab": "{repo_url}/-/raw/{branch}/{addon_name}/",
    "bitbucket": "{repo_url}/raw/{branch}/{addon_name}/",
    "gitea": "{repo_url}/raw/branch/{branch}/{addon_name}/",
}


def normalize_target(target: str = "", prefix_image_url: str = "") -> str:
    target = target or ("custom" if prefix_image_url else "internal")
    if target not in TARGETS:
        raise ValueError(f"Unknown target {target!r} (choose from {', '.join(TARGETS)})")
    if target == "custom" and not prefix_image_url:
        raise ValueError("target 'custom' requires prefix_image_url")
    return target


def resolve_image_prefix(target: str = "", prefix_image_url: str = "", provider: str = "") -> str:
    target = normalize_target(target, prefix_image_url)
    if target == "internal":
        return INTERNAL_IMAGE_PREFIX
    if target == "repo":
        if provider not in RAW_IMAGE_PREFIXES:
            raise ValueError(
                "target 'repo' needs a repo_url on github, gitlab, bitbucket or gitea "
                f"(detected provider: {provider or 'none'}). For a self-hosted server set "
                "'provider', or use target 'custom'"
            )
        return RAW_IMAGE_PREFIXES[provider]
    return prefix_image_url


IMAGE_RE = re.compile(
    r"^(?P<head>\s*\.\.\s+(?:\|[^|\n]+\|\s+)?(?:figure|image)::\s+)"
    r"(?P<path>\S.*?)(?P<tail>\s*)$"
)
_ABSOLUTE_RE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.-]*:|/)")


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def is_absolute(path: str) -> bool:
    return bool(_ABSOLUTE_RE.match(path))


def resolve_local(path: str, fragments_dir: str = "readme") -> str:
    resolved = posixpath.normpath(posixpath.join(fragments_dir, path))
    if resolved.startswith(".."):
        resolved = path.replace("../", "")
    return resolved


def rewrite_image_path(path: str, prefix_image_url: str, context: Dict[str, str], fragments_dir="readme") -> str:
    if is_absolute(path):
        return path
    relative = resolve_local(path, fragments_dir)
    if not prefix_image_url:
        return relative
    prefix = prefix_image_url.format_map(_Safe(context))
    if not prefix.endswith("/"):
        prefix += "/"
    return urljoin(prefix, relative)


def rewrite_fragment_images(text: str, prefix_image_url: str, context: Dict[str, str], fragments_dir="readme") -> str:
    out = []
    for line in text.splitlines(keepends=True):
        m = IMAGE_RE.match(line)
        if m:
            new_path = rewrite_image_path(
                m.group("path"), prefix_image_url, context, fragments_dir
            )
            line = f"{m.group('head')}{new_path}{m.group('tail')}"
        out.append(line)
    return "".join(out)
