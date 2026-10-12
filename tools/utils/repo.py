# Copyright (c) 2015-2018 ACSONE SA/NV
# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote


PROVIDERS = ("github", "gitlab", "bitbucket", "gitea")
PROVIDER_LABELS = {
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
    "gitea": "Gitea",
}
_PROVIDER_HINTS = (
    ("github", ("github",)),
    ("gitlab", ("gitlab",)),
    ("bitbucket", ("bitbucket",)),
    ("gitea", ("gitea", "forgejo", "codeberg")),
)


def detect_provider(host: str) -> str:
    host = host.lower()
    for name, hints in _PROVIDER_HINTS:
        if any(hint in host for hint in hints):
            return name
    return "other"


@dataclass
class RepoInfo:
    url: str = ""
    org_name: str = ""
    repo_name: str = ""
    provider: str = ""
    branch: str = ""

    @property
    def has_repo(self) -> bool:
        return bool(self.url)

    @property
    def provider_label(self) -> str:
        return PROVIDER_LABELS.get(self.provider, "")

    def tree_url(self, addon_name: str) -> str:
        if not self.url:
            return ""
        path = f"{self.branch}/{addon_name}"
        if self.provider == "gitlab":
            return f"{self.url}/-/tree/{path}"
        if self.provider == "bitbucket":
            return f"{self.url}/src/{path}"
        if self.provider == "gitea":
            return f"{self.url}/src/branch/{path}"
        return f"{self.url}/tree/{path}"

    def issues_url(self) -> str:
        if not self.url:
            return ""
        return f"{self.url}{'/-' if self.provider == 'gitlab' else ''}/issues"

    def new_issue_url(self, addon_name: str) -> str:
        if not self.url:
            return ""
        if self.provider == "github":
            body = quote(
                f"module: {addon_name}\nversion: {self.branch}\n\n"
                "**Steps to reproduce**\n- ...\n\n"
                "**Current behavior**\n\n**Expected behavior**",
                safe="",
            )
            return f"{self.url}/issues/new?body={body}"
        return f"{self.issues_url()}/new"


_SCP_RE = re.compile(r"^(?:[\w.-]+@)?(?P<host>[\w.-]+):(?P<path>[^/].*)$")


def normalize_repo_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    if url.endswith(".git"):
        url = url[:-4]
    if "://" in url:
        scheme, rest = url.split("://", 1)
        rest = rest.split("@", 1)[-1] if scheme == "ssh" or "@" in rest.split("/")[0] else rest
        return "https://" + rest if scheme in ("ssh", "git") else f"{scheme}://{rest}"
    m = _SCP_RE.match(url)
    if m:
        return f"https://{m.group('host')}/{m.group('path')}"
    return url


def parse_repo_url(url: str, branch: str = "", provider: str = "") -> RepoInfo:
    """*provider* overrides the hostname guess (useful for self-hosted instances)."""
    url = normalize_repo_url(url)
    if not url:
        return RepoInfo(branch=branch)
    host_and_path = url.split("://", 1)[-1]
    host, _, path = host_and_path.partition("/")
    parts = [p for p in path.split("/") if p]
    repo_name = parts[-1] if parts else ""
    org_name = "/".join(parts[:-1])
    return RepoInfo(url, org_name, repo_name, provider or detect_provider(host), branch)


def _git(*args: str, cwd=None) -> Optional[str]:
    try:
        out = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 and out.stdout.strip() else None


def detect_git_remote(cwd=None) -> str:
    return _git("remote", "get-url", "origin", cwd=cwd) or ""


def detect_git_branch(cwd=None) -> str:
    return _git("symbolic-ref", "--short", "-q", "HEAD", cwd=cwd) or ""


def detect_default_branch(cwd=None) -> str:
    ref = _git("symbolic-ref", "--short", "-q", "refs/remotes/origin/HEAD", cwd=cwd)
    if ref:
        return ref.split("/", 1)[1] if "/" in ref else ref
    for name in ("main", "master"):
        for full in (f"refs/heads/{name}", f"refs/remotes/origin/{name}"):
            if _git("rev-parse", "--verify", "-q", full, cwd=cwd):
                return name
    return ""


def branch_from_version(version: str) -> str:
    parts = (version or "").split(".")
    return ".".join(parts[:2]) if len(parts) >= 4 else ""
