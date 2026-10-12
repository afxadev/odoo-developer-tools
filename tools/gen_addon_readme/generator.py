# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)
# Copyright (c) 2018 ACSONE SA/NV
# Copyright (c) 2018 GRAP (http://www.grap.coop)

from __future__ import annotations

import hashlib
import json
import re
import warnings

from dataclasses import dataclass, field
from docutils.core import publish_string
from jinja2 import Environment
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple

from . import fragments as frag
from .badges import build_badges
from .settings import Settings
from .images import (
    normalize_target,
    resolve_image_prefix,
    rewrite_fragment_images,
)

from tools.utils.digest import compute_digest
from tools.utils.manifest import (
    NoManifestFound,
    find_addons,
    get_manifest_path,
    read_manifest,
)
from tools.utils.repo import (
    RepoInfo,
    branch_from_version,
    detect_default_branch,
    detect_git_branch,
    detect_git_remote,
    parse_repo_url,
)

DEFAULT_TEMPLATE_RST = Path(__file__).resolve().parent.parent / "templates" / "gen_addon_readme.rst.j2"
GENERATED_MARKER = "odt-gen-addon-readme"

# from pypa/readme_renderer: safe rendering settings
warnings.filterwarnings(
    "ignore", message=".*writer_name.*", category=PendingDeprecationWarning
)

RST2HTML_SETTINGS = {
    "file_insertion_enabled": False,
    "halt_level": 2,
    "math_output": "MathJax",
    "raw_enabled": False,
    "smart_quotes": True,
    "syntax_highlight": "short",
    "xml_declaration": False,
    "output_encoding": "utf-8",
}


@dataclass
class RunResult:
    generated: List[Path] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    errors: List[Tuple[str, str]] = field(default_factory=list)


def _iter_addons(settings: Settings) -> Iterator[Tuple[str, Path, dict]]:
    seen = set()

    def emit(name, path, manifest):
        key = Path(path).resolve()
        if key not in seen:
            seen.add(key)
            yield name, Path(path), manifest

    if settings.addons_dir:
        for item in find_addons(settings.addons_dir):
            yield from emit(*item)
    for addon_dir in settings.addon_dirs:
        addon_dir = Path(addon_dir)
        try:
            manifest = read_manifest(addon_dir)
        except NoManifestFound:
            continue
        yield from emit(addon_dir.resolve().name, addon_dir, manifest)
    if not settings.addons_dir and not settings.addon_dirs:
        cwd = Path.cwd()
        if get_manifest_path(cwd):
            yield from emit(cwd.name, cwd, read_manifest(cwd))
        else:
            for item in find_addons(cwd):
                yield from emit(*item)


def _resolve_repo(
    settings: Settings, manifest: dict, cwd: Path, internal: bool
) -> RepoInfo:
    url = settings.repo_url or detect_git_remote(cwd)
    default = settings.default_branch or detect_default_branch(cwd) or "main"
    if settings.branch:
        branch = settings.branch
    elif internal:  # internal docs always follow the main branch
        branch = default
    else:
        branch = (
            detect_git_branch(cwd)
            or branch_from_version(manifest.get("version", ""))
            or default
        )
    return parse_repo_url(url, branch, settings.provider)


def _authors(manifest: dict) -> List[str]:
    value = manifest.get("author", "")
    if isinstance(value, (list, tuple)):
        return [str(a).strip() for a in value if str(a).strip()]
    return [a.strip() for a in str(value).split(",") if a.strip()]


def render_readme(
    env: Environment,
    template_text: str,
    addon_name: str,
    addon_dir: Path,
    manifest: dict,
    settings: Settings,
    repo: RepoInfo,
    source_digest: str,
    fragments_format: Optional[str],
    image_prefix: str = "",
) -> str:
    image_ctx = {
        "addon_name": addon_name,
        "branch": repo.branch,
        "org_name": repo.org_name,
        "repo_name": repo.repo_name,
        "repo_url": repo.url,
    }
    fragments: Dict[str, str] = {}
    for name in frag.FRAGMENTS:
        text = frag.load_fragment_rst(str(addon_dir), name, settings.fragments_dir)
        if text:
            fragments[name] = rewrite_fragment_images(
                text, image_prefix, image_ctx, settings.fragments_dir
            )
    status = str(manifest.get("development_status", "Beta")).lower()
    context = dict(
        addon_name=addon_name,
        authors=_authors(manifest),
        badges=build_badges(manifest, status, repo, addon_name, settings.extra_badges),
        branch=repo.branch,
        fragments=fragments,
        manifest=manifest,
        org_name=repo.org_name,
        repo_name=repo.repo_name,
        repo_url=repo.url,
        repo_provider=repo.provider,
        has_repo=repo.has_repo,
        tree_url=repo.tree_url(addon_name),
        issues_url=repo.issues_url(),
        new_issue_url=repo.new_issue_url(addon_name),
        provider_label=repo.provider_label,
        development_status=status,
        source_digest=source_digest,
        level3_underline="~" if fragments_format == ".rst" else "-",
        prefix_image_url=image_prefix,
        target=settings.target or "",
    )
    text = env.from_string(template_text).render(**context)
    return text.rstrip("\n") + "\n"


def check_rst(text: str) -> None:
    """Raise if docutils reports any warning/error."""
    publish_string(
        source=text, writer_name="html4css1", settings_overrides=RST2HTML_SETTINGS
    )


def render_index_html(
    readme_filename: Path, text: str, title: Optional[str]
) -> bytes:
    overrides = dict(RST2HTML_SETTINGS)
    if title:
        overrides["title"] = title
    html = publish_string(
        source=text,
        source_path=str(readme_filename),
        writer_name="html4css1",
        settings_overrides=overrides,
    )
    # keep diffs quiet: drop the docutils version
    html = re.sub(rb"(<meta.*generator.*Docutils)\s*[\d.]+", rb"\1", html)
    if GENERATED_MARKER.encode() not in html:
        html = html.replace(
            b"</head>", f"<!-- {GENERATED_MARKER} -->\n</head>".encode(), 1
        )
    return html


def _write_if_changed(path: Path, data: bytes) -> bool:
    if path.is_file() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def _digest_in_file(readme: Path) -> Optional[str]:
    if not readme.is_file():
        return None
    m = re.search(r"!! source digest: (sha256:\w+)", readme.read_text(encoding="utf8"))
    return m.group(1) if m else None


def run(
    settings: Settings, log: Callable[[str], None] = lambda msg: None
) -> RunResult:
    result = RunResult()
    template_path = Path(settings.template_file or DEFAULT_TEMPLATE_RST)
    template_text = template_path.read_text(encoding="utf8")
    template_hash = hashlib.sha256(template_text.encode()).hexdigest()
    env = Environment(autoescape=False, keep_trailing_newline=True)
    target = normalize_target(settings.target, settings.prefix_image_url)  # fail fast

    for addon_name, addon_dir, manifest in _iter_addons(settings):
        try:
            if settings.convert_fragments_to_markdown:
                frag.convert_fragments_to_md(str(addon_dir), settings.fragments_dir)
            if not frag.fragment_exists(str(addon_dir), "DESCRIPTION", settings.fragments_dir):
                result.skipped.append(f"{addon_name} (no {settings.fragments_dir}/DESCRIPTION)")
                continue

            repo = _resolve_repo(settings, manifest, Path(addon_dir), target == "internal")
            image_prefix = resolve_image_prefix(
                target, settings.prefix_image_url, repo.provider
            )
            readme = Path(addon_dir) / "README.rst"
            extra = json.dumps(
                [template_hash, image_prefix, repo.url, repo.branch,
                 settings.extra_badges],
                sort_keys=True,
            )
            digest = compute_digest(
                get_manifest_path(addon_dir),
                Path(addon_dir) / settings.fragments_dir,
                relative_to=addon_dir,
                extra=extra,
            )
            existing = _digest_in_file(readme)
            if settings.if_source_changed and existing == digest:
                result.skipped.append(f"{addon_name} (unchanged)")
                continue
            if settings.keep_source_digest and existing:
                digest = existing

            text = render_readme(
                env, template_text, addon_name, Path(addon_dir), manifest, settings,
                repo, digest, frag.get_fragments_format(str(addon_dir), settings.fragments_dir),
                image_prefix,
            )
            if settings.check_rst:
                check_rst(text)
            if _write_if_changed(readme, text.encode("utf8")):
                log(f"  wrote {readme}")
            result.generated.append(readme)

            if settings.gen_html and manifest.get("preloadable", True):
                index = Path(addon_dir) / "static" / "description" / "index.html"
                if index.is_file() and GENERATED_MARKER.encode() not in index.read_bytes():
                    log(f"  kept manual {index}")
                    continue
                html = render_index_html(readme, text, manifest.get("name"))
                if _write_if_changed(index, html):
                    log(f"  wrote {index}")
                result.generated.append(index)
        except Exception as exc:  # keep going with the other addons
            result.errors.append((addon_name, f"{type(exc).__name__}: {exc}"))
    return result
