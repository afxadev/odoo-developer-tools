# License AGPLv3 (https://www.gnu.org/licenses/agpl-3.0-standalone.html)
# Copyright (c) 2018 ACSONE SA/NV
# Copyright (c) 2018 GRAP (http://www.grap.coop)

from __future__ import annotations

import functools
import os
import re
from typing import Dict, Optional

FRAGMENTS_DIR = "readme"

FRAGMENTS: Dict[str, int] = {
    "DESCRIPTION": 2,
    "CONTEXT": 2,
    "INSTALL": 2,
    "CONFIGURE": 2,
    "USAGE": 2,
    "ROADMAP": 2,
    "DEVELOP": 2,
    "CONTRIBUTORS": 3,
    "CREDITS": 3,
    "HISTORY": 2,
}

PANDOC_MARKDOWN_FORMAT = "gfm-raw_html-gfm_auto_identifiers"

class FragmentError(Exception):
    pass

class FragmentHeadingValidationError(ValueError):
    pass

@functools.lru_cache(maxsize=None)
def _pypandoc():
    try:
        import pypandoc
    except ImportError as exc:
        raise FragmentError(
            "Markdown fragments need pypandoc: pip install 'odt-gen-addon-readme[markdown]'"
        ) from exc
    pypandoc.ensure_pandoc_installed(delete_installer=True)
    return pypandoc


def fragment_filename(addon_dir, name, ext, fragments_dir=FRAGMENTS_DIR) -> str:
    return os.path.join(addon_dir, fragments_dir, name + ext)


def fragment_exists(addon_dir, name, fragments_dir=FRAGMENTS_DIR) -> bool:
    return any(
        os.path.exists(fragment_filename(addon_dir, name, ext, fragments_dir))
        for ext in (".rst", ".md")
    )


def get_fragments_format(addon_dir, fragments_dir=FRAGMENTS_DIR) -> Optional[str]:
    found = None
    for name in FRAGMENTS:
        rst = os.path.exists(fragment_filename(addon_dir, name, ".rst", fragments_dir))
        md = os.path.exists(fragment_filename(addon_dir, name, ".md", fragments_dir))
        if rst and md:
            raise FragmentError(
                f"Both .md and .rst found for {name} in {addon_dir}. Remove one."
            )
        this = ".rst" if rst else ".md" if md else None
        if this is None:
            continue
        if found and this != found:
            raise FragmentError(
                f"Both .md and .rst fragments found in {addon_dir}/{fragments_dir}. "
                "Use the same format for all fragments."
            )
        found = this
    return found


def validate_markdown_headings(md_text: str, filename: str) -> None:
    lines = md_text.splitlines()
    current_level = 0

    for line_num, line in enumerate(lines, start=1):
        match = re.match(r'^(#{1,6})\s+(.*)', line.strip())
        if match:
            level = len(match.group(1))
            heading_title = match.group(2)
            hashes = '#' * level

            if current_level == 0 and level > 2:
                raise FragmentHeadingValidationError(
                    f"[{filename}:{line_num}] Invalid initial heading level!\n"
                    f"  Found: {hashes} '{heading_title}' (Level {level})\n"
                    f"  Expected: Level 1 (#) or Level 2 (##).\n"
                    f"  Reason: Starting directly with Level 3+ causes RST title style skipping."
                )

            if current_level > 0 and level > current_level + 1:
                prev_hashes = '#' * current_level
                raise FragmentHeadingValidationError(
                    f"[{filename}:{line_num}] Heading level skipped!\n"
                    f"  Previous: {prev_hashes} (Level {current_level})\n"
                    f"  Found: {hashes} '{heading_title}' (Level {level})\n"
                    f"  Reason: Cannot skip from Level {current_level} to Level {level}."
                )

            current_level = level


def validate_rst_headings(rst_text: str, filename: str) -> None:
    lines = rst_text.splitlines()
    styles_seen = []

    for line_num, line in enumerate(lines, start=1):
        strip_line = line.strip()
        if strip_line and len(strip_line) >= 3 and len(set(strip_line)) == 1:
            char = strip_line[0]
            if char in "=-~`':\"^_*+#<>":
                if line_num > 1 and lines[line_num - 2].strip():
                    title_text = lines[line_num - 2].strip()
                    
                    if char not in styles_seen:
                        styles_seen.append(char)
                        
                    current_level = styles_seen.index(char) + 1

                    if len(styles_seen) == 1 and current_level > 2:
                        raise FragmentHeadingValidationError(
                            f"[{filename}:{line_num - 1}] Invalid initial RST adornment style!\n"
                            f"  Title: '{title_text}'\n"
                            f"  Underline: '{strip_line}' (Char: '{char}')\n"
                            f"  Reason: Heading style starts too deep for a fragment."
                        )


def load_fragment_rst(addon_dir, name, fragments_dir=FRAGMENTS_DIR) -> Optional[str]:
    rst = fragment_filename(addon_dir, name, ".rst", fragments_dir)
    md = fragment_filename(addon_dir, name, ".md", fragments_dir)
    if os.path.exists(rst):
        with open(rst, encoding="utf8") as f:
            text = f.read()
        validate_rst_headings(text, rst)
    elif os.path.exists(md):
        with open(md, encoding="utf8") as f:
            raw_md = f.read()
        validate_markdown_headings(raw_md, md)

        text = _pypandoc().convert_file(
            md,
            to="rst",
            format=PANDOC_MARKDOWN_FORMAT,
            extra_args=[f"--shift-heading-level-by={FRAGMENTS[name] - 2}", "--sandbox"],
        )
    else:
        return None
    if not text.strip():
        return None
    return text if text.endswith("\n") else text + "\n"


def convert_fragments_to_md(addon_dir, fragments_dir=FRAGMENTS_DIR) -> None:
    for name in FRAGMENTS:
        rst = fragment_filename(addon_dir, name, ".rst", fragments_dir)
        md = fragment_filename(addon_dir, name, ".md", fragments_dir)
        if not os.path.exists(rst) or os.path.exists(md):
            continue
        _pypandoc().convert_file(
            rst,
            to=PANDOC_MARKDOWN_FORMAT,
            format="rst",
            outputfile=md,
            extra_args=["--shift-heading-level=1", "--sandbox"],
        )
        os.remove(rst)
