import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from tools.cli import main as odt_main
from tools.gen_addon_readme.settings import build_settings
from tools.gen_addon_readme.images import (
    rewrite_fragment_images,
    rewrite_image_path,
)
from tools.utils.repo import branch_from_version, parse_repo_url


def main_invoke(runner, args):
    return runner.invoke(odt_main, ["gen-addon-readme", *args])


@pytest.fixture(autouse=True)
def _isolated_cwd(tmp_path, monkeypatch):
    """Never pick up the repo's own ./.odt.yaml or git remote."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)


CTX = {"addon_name": "my_addon", "branch": "16.0", "org_name": "acme", "repo_name": "r"}


@pytest.mark.parametrize(
    "path,prefix,expected",
    [
        ("../static/description/a.png", "", "static/description/a.png"),
        ("../static/description/a.png", "https://cdn/x", "https://cdn/x/static/description/a.png"),
        ("../static/description/a.png", "https://cdn/x/", "https://cdn/x/static/description/a.png"),
        ("shot.png", "https://cdn/x/", "https://cdn/x/readme/shot.png"),
        ("https://other/a.png", "https://cdn/x/", "https://other/a.png"),
        ("data:image/png;base64,AAAA", "https://cdn/x/", "data:image/png;base64,AAAA"),
        ("/abs/a.png", "https://cdn/x/", "/abs/a.png"),
        ("../../../evil.png", "", "evil.png"),
        (
            "../static/a.png", "https://h/{org_name}/{repo_name}/{branch}/{addon_name}/",
            "https://h/acme/r/16.0/my_addon/static/a.png"
        ),
    ],
)
def test_rewrite_image_path(path, prefix, expected):
    assert rewrite_image_path(path, prefix, CTX) == expected


def test_rewrite_fragment_images_only_touches_image_directives():
    text = ".. image:: ../static/a.png\n    :alt: ../static/a.png\n\ntext ../static/a.png\n.. |s| image:: b.png\n"
    out = rewrite_fragment_images(text, "https://cdn/", CTX)
    assert ".. image:: https://cdn/static/a.png\n" in out
    assert "    :alt: ../static/a.png" in out and "text ../static/a.png" in out
    assert ".. |s| image:: https://cdn/readme/b.png" in out


def test_repo_parsing():
    r = parse_repo_url("git@github.com:acme/my-addons.git", "16.0")
    assert (r.url, r.org_name, r.repo_name, r.provider) == (
        "https://github.com/acme/my-addons", "acme", "my-addons", "github")
    g = parse_repo_url("https://gitlab.com/a/b/c.git")
    assert g.org_name == "a/b" and g.tree_url("m").endswith("/-/tree//m")
    assert not parse_repo_url("").has_repo
    assert branch_from_version("16.0.1.0.0") == "16.0" and branch_from_version("1.0") == ""


def test_config_precedence_and_empty_values(tmp_path):
    cfg = tmp_path / ".odt.yaml"
    cfg.write_text(textwrap.dedent("""
        repo_url: https://github.com/a/b
        addon_readme:
          - template_file_name: ""
            prefix_image_url: https://cdn/
          - addons_dir: sub
            gen_html: false
    """))
    a, b = build_settings(cfg, {"gen_html": None, "addon_dirs": ()})
    assert a.repo_url == "https://github.com/a/b" and a.template_file is None
    assert a.prefix_image_url == "https://cdn/" and b.addons_dir == tmp_path / "sub"
    assert b.gen_html is False
    # CLI wins, and "" is a deliberate override
    (c, _) = build_settings(cfg, {"prefix_image_url": "", "repo_url": "https://x/y/z"})
    assert c.prefix_image_url == "" and c.repo_url == "https://x/y/z"


def test_unknown_config_key(tmp_path):
    cfg = tmp_path / ".odt.yaml"
    cfg.write_text("addon_readme:\n  nope: 1\n")
    with pytest.raises(ValueError):
        build_settings(cfg, {})


@pytest.fixture
def addon(tmp_path):
    d = tmp_path / "my_addon"
    (d / "readme").mkdir(parents=True)
    (d / "__manifest__.py").write_text('{"name": "My Addon", "version": "16.0.1.0.0", "license": "AGPL-3"}')
    (d / "readme" / "DESCRIPTION.rst").write_text("Hello.\n\n.. image:: ../static/description/b.png\n")
    return d


def test_end_to_end_custom_prefix_and_default(addon):
    runner = CliRunner()
    args = ["--addon-dir", str(addon), "--repo-url", "https://github.com/acme/r", "--branch", "16.0"]
    res = main_invoke(runner, args + ["--prefix-image-url", "https://cdn/{addon_name}/"])
    assert res.exit_code == 0, res.output
    readme = (addon / "README.rst").read_text()
    assert ".. image:: https://cdn/my_addon/static/description/b.png" in readme
    assert "https://github.com/acme/r/tree/16.0/my_addon" in readme

    res = main_invoke(runner, args)  # no target, no prefix -> internal
    assert res.exit_code == 0, res.output
    assert ".. image:: /my_addon/static/description/b.png" in (addon / "README.rst").read_text()
    assert 'src="/my_addon/static/description/b.png"' in (addon / "static/description/index.html").read_text()


def test_manual_index_html_is_never_overwritten(addon):
    index = addon / "static" / "description" / "index.html"
    index.parent.mkdir(parents=True)
    index.write_text("<html>manual</html>")
    assert main_invoke(CliRunner(), ["--addon-dir", str(addon)]).exit_code == 0
    assert index.read_text() == "<html>manual</html>"


def test_if_source_changed_detects_setting_change(addon):
    runner = CliRunner()
    base = ["--addon-dir", str(addon), "--if-source-changed", "--no-gen-html"]
    assert "1 README generated" in main_invoke(runner, base).output
    assert "0 README generated" in main_invoke(runner, base).output
    assert "1 README generated" in main_invoke(runner, base + ["--prefix-image-url", "https://cdn/"]).output


def test_invalid_rst_gives_nonzero_exit(addon):
    (addon / "readme" / "USAGE.rst").write_text("`unclosed\n")
    assert main_invoke(CliRunner(), ["--addon-dir", str(addon)]).exit_code == 1


def test_group_lists_subcommand_and_shared_config(addon, tmp_path):
    runner = CliRunner()
    assert "gen-addon-readme" in runner.invoke(odt_main, ["--help"]).output
    cfg = tmp_path / ".odt.yaml"
    cfg.write_text(
        f"repo_url: https://github.com/acme/r\nbranch: '16.0'\n"
        f"prefix_image_url: https://cdn/\naddon_readme:\n  addon_dirs: [{addon}]\n"
        "other_tool:\n  anything: 1\n"
    )
    res = runner.invoke(odt_main, ["--config", str(cfg), "gen-addon-readme", "--no-gen-html"])
    assert res.exit_code == 0, res.output
    assert "https://cdn/static/description/b.png" in (addon / "README.rst").read_text()


def test_standalone_alias_works_without_group():
    from tools.gen_addon_readme import command
    assert CliRunner().invoke(command, ["--help"]).exit_code == 0


# ---------------------------------------------------------------- targets
import subprocess

from tools.gen_addon_readme.images import resolve_image_prefix
from tools.utils.repo import detect_default_branch, detect_git_branch


def test_resolve_image_prefix():
    assert resolve_image_prefix() == "/{addon_name}/"  # default = internal
    assert resolve_image_prefix("internal", "https://ignored/") == "/{addon_name}/"
    assert resolve_image_prefix("", "https://cdn/") == "https://cdn/"  # implies custom
    assert resolve_image_prefix("custom", "https://cdn/") == "https://cdn/"
    assert resolve_image_prefix("repo", provider="github").startswith(
        "https://raw.githubusercontent.com/")
    for target in ("custom", "nope", "local", "github"):
        with pytest.raises(ValueError):
            resolve_image_prefix(target)
    with pytest.raises(ValueError):  # unknown / self-hosted host without provider
        resolve_image_prefix("repo", provider="other")
    with pytest.raises(ValueError):
        resolve_image_prefix("repo")


@pytest.mark.parametrize(
    "url,provider,raw",
    [
        (
            "https://github.com/acme/r",
            "github",
            "https://raw.githubusercontent.com/acme/r/16.0/my_addon/static/description/b.png"
        ),
        (
            "https://gitlab.com/acme/grp/r",
            "gitlab",
            "https://gitlab.com/acme/grp/r/-/raw/16.0/my_addon/static/description/b.png"
        ),
        (
            "git@bitbucket.org:acme/r.git",
            "bitbucket",
            "https://bitbucket.org/acme/r/raw/16.0/my_addon/static/description/b.png"
        ),
        (
            "https://codeberg.org/acme/r",
            "gitea",
            "https://codeberg.org/acme/r/raw/branch/16.0/my_addon/static/description/b.png"
        ),
    ],
)
def test_target_repo_builds_raw_url_per_provider(addon, url, provider, raw):
    res = _invoke(addon, "--target", "repo", "--repo-url", url)
    assert res.exit_code == 0, res.output
    # no git repo here -> branch derived from manifest version 16.0.1.0.0
    assert f".. image:: {raw}" in (addon / "README.rst").read_text()
    assert parse_repo_url(url).provider == provider


def test_self_hosted_needs_provider(addon):
    url = "https://git.mycompany.id/team/r"
    assert parse_repo_url(url).provider == "other"
    assert _invoke(addon, "--target", "repo", "--repo-url", url).exit_code == 1
    res = _invoke(addon, "--target", "repo", "--repo-url", url, "--provider", "gitlab")
    assert res.exit_code == 0, res.output
    text = (addon / "README.rst").read_text()
    assert ".. image:: https://git.mycompany.id/team/r/-/raw/16.0/my_addon/static/description/b.png" in text
    assert "https://git.mycompany.id/team/r/-/tree/16.0/my_addon" in text


@pytest.mark.parametrize(
    "url,tree,issues",
    [
        ("https://github.com/a/r", "https://github.com/a/r/tree/b/m", "https://github.com/a/r/issues"),
        ("https://gitlab.com/a/r", "https://gitlab.com/a/r/-/tree/b/m", "https://gitlab.com/a/r/-/issues"),
        ("https://bitbucket.org/a/r", "https://bitbucket.org/a/r/src/b/m", "https://bitbucket.org/a/r/issues"),
        ("https://codeberg.org/a/r", "https://codeberg.org/a/r/src/branch/b/m", "https://codeberg.org/a/r/issues"),
    ],
)
def test_provider_links(url, tree, issues):
    r = parse_repo_url(url, "b")
    assert r.tree_url("m") == tree and r.issues_url() == issues


def _invoke(addon, *extra):
    return main_invoke(CliRunner(), ["--addon-dir", str(addon), "--no-gen-html", *extra])


def test_target_internal_uses_module_path_and_default_branch(addon):
    res = _invoke(addon, "--target", "internal", "--repo-url", "https://github.com/acme/r", "--default-branch", "master", "--branch", "")
    assert res.exit_code == 0, res.output
    text = (addon / "README.rst").read_text()
    assert ".. image:: /my_addon/static/description/b.png" in text
    assert "https://github.com/acme/r/tree/master/my_addon" in text


def test_target_internal_ignores_current_branch_but_explicit_branch_wins(addon):
    res = _invoke(addon, "--target", "internal", "--repo-url", "https://github.com/acme/r", "--branch", "17.0")
    assert res.exit_code == 0
    assert "tree/17.0/my_addon" in (addon / "README.rst").read_text()


def test_target_repo_follows_current_branch_not_main(addon):
    res = _invoke(addon, "--target", "repo", "--repo-url", "https://github.com/acme/r", "--default-branch", "master")
    assert res.exit_code == 0, res.output
    text = (addon / "README.rst").read_text()
    assert "/acme/r/16.0/my_addon/" in text and "tree/16.0/my_addon" in text


def test_target_repo_requires_known_provider(addon):
    assert _invoke(addon, "--target", "repo").exit_code == 1  # no repo_url at all


def test_target_custom_requires_prefix(addon):
    assert _invoke(addon, "--target", "custom").exit_code != 0
    res = _invoke(addon, "--target", "custom", "--prefix-image-url", "https://cdn/x/")
    assert res.exit_code == 0
    assert ".. image:: https://cdn/x/static/description/b.png" in (addon / "README.rst").read_text()


def test_full_urls_are_kept_in_every_target(addon):
    (addon / "readme" / "DESCRIPTION.rst").write_text(
        ".. image:: https://x.test/a.png\n.. image:: http://x.test/b.png\n")
    for target in ("internal", "repo"):
        assert _invoke(addon, "--target", target, "--repo-url", "https://github.com/a/b").exit_code == 0
        text = (addon / "README.rst").read_text()
        assert ".. image:: https://x.test/a.png" in text and ".. image:: http://x.test/b.png" in text


def test_internal_html_uses_module_path(addon):
    res = main_invoke(CliRunner(), ["--addon-dir", str(addon), "--target", "internal"])
    assert res.exit_code == 0, res.output
    assert 'src="/my_addon/static/description/b.png"' in (addon / "static/description/index.html").read_text()


def _git_repo(path, branch, commit=True):
    env = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
        "PATH": __import__("os").environ["PATH"]
    }
    run = lambda *a: subprocess.run(["git", *a], cwd=path, env=env, check=True, capture_output=True)
    run("init", "-q")
    run("symbolic-ref", "HEAD", f"refs/heads/{branch}")
    if commit:
        (path / "f").write_text("x")
        run("add", "f")
        run("commit", "-qm", "init")
    return run


@pytest.mark.parametrize("name", ["main", "master"])
def test_detect_default_branch(tmp_path, name):
    _git_repo(tmp_path, name)
    assert detect_default_branch(tmp_path) == name
    assert detect_git_branch(tmp_path) == name


def test_branch_detection_edge_cases(tmp_path):
    run = _git_repo(tmp_path, "master")
    run("checkout", "-q", "-b", "16.0")
    assert detect_git_branch(tmp_path) == "16.0"
    assert detect_default_branch(tmp_path) == "master"
    run("checkout", "-q", "--detach")
    assert detect_git_branch(tmp_path) == ""
    empty = tmp_path / "empty"; empty.mkdir()
    _git_repo(empty, "develop", commit=False)
    assert detect_git_branch(empty) == "develop"  # unborn branch still has a name
    assert detect_default_branch(empty) == ""
