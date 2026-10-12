# Odoo Developer Tools

Modern, lightweight and extensible command line tools for the Odoo development workflow.
Everything lives under one command, `odt`; each tool is a subcommand.

| Command | What it does |
|---|---|
| `odt gen-addon-readme` | Generate `README.rst` and `static/description/index.html` for Odoo addons from `readme/` fragments |

## Requirements

* Python 3.8 or newer
* `git` (recommended): used to detect the repository URL and branch
* `pandoc` 2.15 or newer: only needed for Markdown fragments (`sudo apt install pandoc`)

## Installation

From a clone (recommended for development):

```bash
git clone https://github.com/afxadev/odoo-developer-tools.git
cd odoo-developer-tools
python3 -m venv env
. env/bin/activate
pip install -e .
```

Directly from GitHub, without cloning:

```bash
pip install git+https://github.com/afxadev/odoo-developer-tools.git
```

Or as an isolated command-line tool, available in every terminal:

```bash
pipx install git+https://github.com/afxadev/odoo-developer-tools.git
```

Check the installation:

```bash
odt --version
odt --help
```

> **Notes**
> * Editable installs (`-e`) need pip 21.3 or newer: `python -m pip install --upgrade pip`.
> * The version comes from git tags (`hatch-vcs`). Without git metadata, for example a downloaded
>   zip, the version is `0.0.0`; this does not affect how the tools work.
> * Add `env/` to your `.gitignore`.

## Usage

```bash
odt [--config FILE] COMMAND [OPTIONS]
```

`--config` (or `./odt.yaml`, picked up automatically) is shared by all commands. See
[Configuration file](#configuration-file).

## README Generator

To provide a high quality README for our modules we generate them automatically.
The sections of the final README are organized in **fragments**: small `.rst` (or `.md`) files
inside a `readme` folder of the module.

### Fragments

Only `DESCRIPTION` is required; a module without `readme/DESCRIPTION.rst|md` is skipped.
All fragments of one module must use the same format (`.rst` or `.md`, not mixed).

| Fragment | Section in the final README |
|---|---|
| `DESCRIPTION` | Introduction (no heading), shown below the badges |
| `CONTEXT` | Use Cases / Context |
| `INSTALL` | Installation |
| `CONFIGURE` | Configuration |
| `USAGE` | Usage |
| `DEVELOP` | Development |
| `ROADMAP` | Known issues / Roadmap |
| `HISTORY` | Changelog |
| `CONTRIBUTORS` | Credits → Contributors |
| `CREDITS` | Credits → Other credits |

Everything else comes from the manifest: `name`, `version`, `author`, `license`,
`maintainers` and `development_status` (alpha, beta, ...) produce the title, the badges, the
authors and the maintainers. The Bug Tracker section and the "part of the ... project" line
appear when a repository URL is known.

### Example

To generate the final README for the module `auth_keycloak`:

```
auth_keycloak/
├── __manifest__.py
├── readme/
│   ├── DESCRIPTION.rst
│   ├── INSTALL.rst
│   ├── USAGE.rst
│   ├── CONTRIBUTORS.rst
│   └── HISTORY.rst
└── static/description/        # images referenced from the fragments
```

```bash
odt gen-addon-readme \
    --addon-dir auth_keycloak \
    --repo-url https://github.com/acme/server-auth \
    --branch 16.0 \
    --target repo
```

The result is a valid `README.rst` in the root of the module (checked with docutils, so it
renders on PyPI and GitHub) and `static/description/index.html` for the Odoo Apps page.
A hand-written `index.html` is never overwritten.

For many modules at once:

```bash
odt gen-addon-readme --addons-dir ./addons
```

The repository organisation and name are read from `--repo-url`, so it works for your own
organisation too; there is no separate `--org-name` option.

### Images and `target`

`target` says **where the README will be read**. It decides how relative images in the
fragments (`.. image::`, `.. figure::`, Markdown images) are rewritten and which branch is
used in links. Image paths are resolved relative to the fragment, so
`../static/description/a.png` becomes `static/description/a.png` inside the module.

| `target` | Image result | Branch used in links |
|---|---|---|
| `internal` (default) | `/<addon_name>/static/description/a.png`, served by Odoo | main branch (`main` / `master`) |
| `repo` | raw-file URL of your git host (see below) | current branch |
| `custom` | `<prefix_image_url>/static/description/a.png` | current branch |

Images that are already absolute (`https://…`, `http://…`, `data:…`, `/abs`) are always kept
as they are. Without `target`, setting `prefix_image_url` implies `custom`.

Raw URL used by `repo`, by git host (detected from the hostname of `repo_url`):

| Host | Image URL |
|---|---|
| GitHub | `https://raw.githubusercontent.com/<org>/<repo>/<branch>/<addon>/<path>` |
| GitLab (subgroups and self-hosted too) | `<repo_url>/-/raw/<branch>/<addon>/<path>` |
| Bitbucket | `<repo_url>/raw/<branch>/<addon>/<path>` |
| Gitea, Forgejo, Codeberg | `<repo_url>/raw/branch/<branch>/<addon>/<path>` |

Links to the module folder and to the issue tracker follow the host as well. For a self-hosted
server whose hostname does not reveal the software, set it explicitly:
`--provider gitlab`. Raw URLs of private repositories are not visible to anonymous readers.

How the branch is chosen:

* **Current branch**: `--branch`, else the git branch, else derived from the manifest version
  (`16.0.1.0.0` → `16.0`), else the main branch.
* **Main branch** (`internal`): `--branch`, else `--default-branch`, else `origin/HEAD`, else
  `main` or `master` if it exists, else `main`.

```bash
odt gen-addon-readme                                   # internal
odt gen-addon-readme --target repo                     # GitHub / GitLab / Bitbucket / Gitea
odt gen-addon-readme --target repo --provider gitlab   # self-hosted GitLab
odt gen-addon-readme --target custom \
    --prefix-image-url 'https://cdn.example.com/{addon_name}/'
```

`internal` relies on Odoo serving `/<module>/static/...`, so keep images under `static/`.
For a repository with one branch per Odoo version, prefer `repo` so that links follow the branch.

### Configuration file

Instead of repeating options, put them in `odt.yaml` (picked up automatically from the current
folder, or pass `odt --config FILE ...`). A complete, commented example is in
[`odt.yaml`](odt.yaml):

```yaml
repo_url: https://github.com/acme/my-addons
addon_readme:
  - addons_dir: .
    target: repo
```

* Precedence: built-in defaults < config file < command line.
* An empty value means "not set". An empty value on the command line, such as
  `--prefix-image-url ""`, deliberately overrides the file.
* `addon_readme` may be a list: each entry is a separate run.
* Keep every option indented under the `- `. A key written at the top level is not part of the
  entry and is ignored.

### Options

| Option | Description |
|---|---|
| `-c, --config FILE` | Config file (default: `./odt.yaml`) |
| `--addons-dir DIR` | Directory containing several addons |
| `--addon-dir DIR` | One addon directory (repeatable) |
| `--repo-url URL` | Repository URL (default: git remote `origin`) |
| `--provider NAME` | `github`, `gitlab`, `bitbucket` or `gitea`, for self-hosted servers |
| `--branch NAME` | Branch used in links |
| `--default-branch NAME` | Main branch used by `--target internal` |
| `--target NAME` | `internal` (default), `repo` or `custom` |
| `--prefix-image-url URL` | Image prefix for `custom`; placeholders `{addon_name}` `{branch}` `{org_name}` `{repo_name}` `{repo_url}` |
| `--template-file FILE` | Custom Jinja2 template |
| `--print-default-template` | Print the built-in template and exit |
| `--fragments-dir NAME` | Fragments folder inside each addon (default: `readme`) |
| `--gen-html / --no-gen-html` | Generate `static/description/index.html` (default: on) |
| `--check-rst / --no-check-rst` | Validate the generated RST (default: on) |
| `--if-source-changed` | Skip addons whose manifest, fragments or settings did not change |
| `--keep-source-digest` | Keep the digest already in `README.rst` (fewer merge conflicts) |
| `--convert-fragments-to-markdown` | Convert `.rst` fragments to `.md` (needs pandoc) |

Behaviour worth knowing:

* The digest stored in `README.rst` covers the manifest, all fragments **and** the settings
  and template, so `--if-source-changed` also reacts to a changed target, repository or template.
* One failing module does not stop the others; the exit code is 1 if any module failed, which
  makes the command usable in CI.

### Custom template

```bash
odt gen-addon-readme --print-default-template > my_readme.rst.j2
odt gen-addon-readme --template-file my_readme.rst.j2
```

Variables available in the template: `addon_name`, `manifest`, `authors`, `badges`,
`fragments`, `branch`, `org_name`, `repo_name`, `repo_url`, `repo_provider`, `provider_label`,
`has_repo`, `tree_url`, `issues_url`, `new_issue_url`, `development_status`, `source_digest`,
`level3_underline`, `prefix_image_url` and `target`.

Keep the "generated by odt-gen-addon-readme" comment in your template: it is how the generator
tells its own `index.html` apart from one written by hand.

### Coming from `oca-gen-addon-readme`

| OCA | `odt gen-addon-readme` |
|---|---|
| `--repo-name=server-auth --org-name=OCA` | `--repo-url=https://github.com/OCA/server-auth` |
| `--branch=10.0` | `--branch=10.0` |
| `--addon-dir=auth_keycloak` | `--addon-dir=auth_keycloak` |

The fragment names and the layout of the `readme` folder are the same. The template is generic
(no OCA-specific badges or banners); use `extra_badges` or a custom template for those.

## Project layout

```
tools/
├── cli.py                  # `odt` command group, discovers subcommands
├── config.py               # shared odt.yaml loader
├── utils/                  # manifest, repository information, digest
├── templates/              # Jinja2 templates
└── gen_addon_readme/       # one package per subcommand: click command, settings
                            # (options and config section), generator, ...
```

A new command is a new package under `tools/` that exposes a click `command`; register it in
`BUILTIN_COMMANDS` in `tools/cli.py` and read its config section with
`tools.config.load_entries`.

## Development

```bash
pip install -e '.[dev]'
pytest
```

The tests run in temporary folders and need `git`. See `pyproject.toml` for the build setup
(`hatchling` + `hatch-vcs`; tag a release with `git tag v0.1.0`).

## License

[AGPL-3.0](https://www.gnu.org/licenses/agpl-3.0.html)

## Credits & Acknowledgments

This project was inspired by the core concepts of the
[OCA maintainer-tools](https://github.com/OCA/maintainer-tools). We extend our deepest
gratitude to the [Odoo Community Association (OCA)](https://github.com/OCA) for its
exceptional documentation standards and open-source ecosystem.