from __future__ import annotations

import importlib
from importlib import metadata
from pathlib import Path
from typing import Iterator

import click

from . import __version__

BUILTIN_COMMANDS = ("tools.gen_addon_readme",)


def _iter_commands() -> Iterator[click.Command]:
    for module_name in BUILTIN_COMMANDS:
        yield importlib.import_module(module_name).command
    try:
        eps = metadata.entry_points(group="odt.commands")
    except TypeError:  # python < 3.10
        eps = metadata.entry_points().get("odt.commands", [])
    for ep in eps:
        yield ep.load()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Config file shared by all subcommands (default: ./.odt.yaml if present).",
)
@click.version_option(__version__, prog_name="odt")
@click.pass_context
def main(ctx, config):
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


for _command in _iter_commands():
    main.add_command(_command)
