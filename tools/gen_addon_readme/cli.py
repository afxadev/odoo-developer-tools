# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)
# Copyright (c) 2018 ACSONE SA/NV
# Copyright (c) 2018 GRAP (http://www.grap.coop)
from __future__ import annotations

import click
import sys

from pathlib import Path

from tools.utils.config import find_default_config
from tools.utils.repo import PROVIDERS

from .generator import DEFAULT_TEMPLATE_RST, run
from .images import TARGETS
from .settings import build_settings


def _print_template(ctx, _param, value):
    if value and not ctx.resilient_parsing:
        click.echo(DEFAULT_TEMPLATE_RST.read_text(encoding="utf8"), nl=False)
        ctx.exit()

@click.command("gen-addon-readme", context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config", "-c",
    "config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Config file (default: the one given to `odt`, else ./.odt.yaml)."
)
@click.option(
    "--addons-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing several addons."
)
@click.option(
    "--addon-dir",
    "addon_dirs",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="One addon directory (repeatable)."
)
@click.option(
    "--repo-url",
    help="Repository URL, e.g. https://github.com/acme/my-addons (default: git remote 'origin')."
)
@click.option(
    "--branch", 
    help="Branch/version used in links (default: git branch, else derived from manifest version)."
)
@click.option(
    "--default-branch", 
    help="Main branch (used by --target internal). Default: origin/HEAD, else main/master."
)
@click.option(
    "--target",
    type=click.Choice(TARGETS),
    help=(
        "Where the README is read: internal (default; images /<addon>/<path>, "
        "main branch), repo (raw URL of the git host, current branch) or custom "
        "(needs --prefix-image-url)."
    )
)
@click.option(
    "--provider",
    type=click.Choice(PROVIDERS),
    help="Git host software, for self-hosted servers whose hostname does not reveal it (default: guessed from repo_url)."
)
@click.option(
    "--prefix-image-url",
    help=(
        "Image prefix for --target custom (implies it). "
        "Placeholders: {addon_name} {branch} {org_name} {repo_name} {repo_url}."
    )
)
@click.option(
    "--template-file",
    "--template-filename",
    "template_file",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Custom Jinja2 template (see --print-default-template)."
)
@click.option(
    "--fragments-dir", 
    help="Fragments folder inside each addon (default: readme)."
)
@click.option(
    "--gen-html/--no-gen-html",
    default=None,
    help="Generate static/description/index.html (default: on)."
)
@click.option(
    "--check-rst/--no-check-rst",
    default=None,
    help="Validate generated RST with docutils (default: on)."
)
@click.option(
    "--keep-source-digest",
    is_flag=True,
    default=None,
    help="Keep the existing digest in README.rst (fewer merge conflicts)."
)
@click.option(
    "--if-source-changed",
    "--if-fragments-changed",
    "if_source_changed",
    is_flag=True,
    default=None,
    help="Only regenerate when manifest, fragments or settings changed."
)
@click.option(
    "--convert-fragments-to-markdown",
    is_flag=True,
    default=None,
    help="Convert .rst fragments to .md (needs pypandoc)."
)
@click.option(
    "--print-default-template",
    is_flag=True,
    expose_value=False,
    is_eager=True,
    callback=_print_template,
    help="Print the built-in template and exit."
)
@click.pass_context
def gen_addon_readme(ctx, config, **cli):
    """
    Generate README.rst from fragments.

    Do nothing if readme/DESCRIPTION(.rst|.md) is absent, otherwise overwrite
    existing README.rst with content generated from the template,
    fragments (DESCRIPTION(.rst|.md), USAGE(.rst|.md), etc) and the addon manifest.
    """
    config = config or (ctx.obj or {}).get("config") or find_default_config()
    try:
        all_settings = build_settings(config, cli)
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc))

    failed = False
    for settings in all_settings:
        result = run(settings, log=click.echo)
        for name in result.skipped:
            click.echo(f"  skipped {name}")
        for name, message in result.errors:
            click.secho(f"  ERROR {name}: {message}", fg="red", err=True)
            failed = True
        n = len([p for p in result.generated if p.name == "README.rst"])
        click.echo(f"{n} README generated")
    sys.exit(1 if failed else 0)



