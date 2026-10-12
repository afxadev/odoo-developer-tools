# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)
# Copyright (c) 2018 ACSONE SA/NV
# Copyright (c) 2018 GRAP (http://www.grap.coop)

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

Badge = Tuple[str, Optional[str], str]  # (image, target, alt)

_SHIELDS = "https://img.shields.io/badge"

LICENSE_URLS = {
    "AGPL-3": "http://www.gnu.org/licenses/agpl-3.0-standalone.html",
    "LGPL-3": "http://www.gnu.org/licenses/lgpl-3.0-standalone.html",
    "GPL-3": "http://www.gnu.org/licenses/gpl-3.0-standalone.html",
    "GPL-2": "http://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html",
    "OPL-1": "https://www.odoo.com/documentation/master/legal/licenses.html",
    "OEEL-1": "https://www.odoo.com/documentation/master/legal/licenses.html",
}

MATURITY = {
    "mature": ("Mature", "brightgreen"),
    "production/stable": ("Production%2FStable", "green"),
    "beta": ("Beta", "yellow"),
    "alpha": ("Alpha", "red"),
}


def _esc(text: str) -> str:
    return text.replace("-", "--").replace("_", "__").replace(" ", "%20")


def license_badge(license_name: Optional[str]) -> Optional[Badge]:
    if not license_name:
        return None
    return (
        f"{_SHIELDS}/license-{_esc(license_name)}-blue.png",
        LICENSE_URLS.get(license_name),
        f"License: {license_name}",
    )


def maturity_badge(status: str) -> Optional[Badge]:
    if status not in MATURITY:
        return None
    label, color = MATURITY[status]
    return (f"{_SHIELDS}/maturity-{label}-{color}.png", None, label.replace("%2F", "/"))


def repo_badge(repo) -> Optional[Badge]:
    if not repo.has_repo:
        return None
    label = _esc(f"{repo.org_name}/{repo.repo_name}").replace("/", "%2F")
    logo = "?logo=github" if repo.provider == "github" else (
        "?logo=gitlab" if repo.provider == "gitlab" else ""
    )
    return (
        f"{_SHIELDS}/{repo.provider if repo.provider != 'other' else 'repo'}-{label}"
        f"-lightgray.png{logo}",
        repo.url,
        f"{repo.org_name}/{repo.repo_name}",
    )


def build_badges(manifest: Dict, status: str, repo, addon_name: str, extra: List[Dict]) -> List[Badge]:
    badges: List[Badge] = []
    for badge in (
        maturity_badge(status),
        license_badge(manifest.get("license")),
        repo_badge(repo),
    ):
        if badge:
            badges.append(badge)
    ctx = {
        "addon_name": addon_name,
        "branch": repo.branch,
        "branch_dashed": repo.branch.replace(".", "-"),
        "org_name": repo.org_name,
        "repo_name": repo.repo_name,
        "repo_url": repo.url,
    }
    for item in extra or []:
        image = item.get("image")
        if image:
            badges.append(
                (
                    _fmt(image, ctx),
                    _fmt(item.get("target") or "", ctx) or None,
                    _fmt(item.get("alt") or "", ctx),
                )
            )
    return badges


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _fmt(text: str, ctx: Dict) -> str:
    return text.format_map(_Safe(ctx))
