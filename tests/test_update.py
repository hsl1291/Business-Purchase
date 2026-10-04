import subprocess

import pytest

from bizbuy import update


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


@pytest.fixture
def repos(tmp_path):
    """A 'remote' repo and an install cloned from it."""
    remote = tmp_path / "remote"
    remote.mkdir()
    git(remote, "init", "-q", "-b", "main")
    git(remote, "config", "user.email", "t@t")
    git(remote, "config", "user.name", "t")
    (remote / "requirements.txt").write_text("pandas\n")
    (remote / "code.py").write_text("v = 1\n")
    git(remote, "add", ".")
    git(remote, "commit", "-qm", "v1")
    install = tmp_path / "install"
    subprocess.run(["git", "clone", "-q", str(remote), str(install)], check=True)
    return remote, install


def push_change(remote, name="code.py", text="v = 2\n"):
    (remote / name).write_text(text)
    git(remote, "commit", "-qam", "change")


def test_up_to_date(repos):
    _, install = repos
    assert "Already up to date" in update.update_git_install(install)


def test_check_only_reports_without_pulling(repos):
    remote, install = repos
    push_change(remote)
    assert "1 update(s) available" in update.update_git_install(install, check_only=True)
    assert (install / "code.py").read_text() == "v = 1\n"


def test_pull_applies_update_without_reinstalling_unchanged_deps(repos, monkeypatch):
    remote, install = repos
    push_change(remote)
    calls = []
    real_run = subprocess.run
    monkeypatch.setattr(update.subprocess, "run", lambda *a, **k: calls.append(a) or real_run(*a, **k))
    msg = update.update_git_install(install)
    assert "Updated 1 commit" in msg
    assert (install / "code.py").read_text() == "v = 2\n"
    assert not any("pip" in c[0] for c in calls)


def test_pull_reinstalls_when_requirements_change(repos, monkeypatch):
    remote, install = repos
    push_change(remote, "requirements.txt", "pandas\nrequests\n")
    real_run = subprocess.run
    pip_calls = []

    def fake_run(cmd, *a, **k):
        if "pip" in cmd:
            pip_calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0)
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(update.subprocess, "run", fake_run)
    update.update_git_install(install)
    assert pip_calls and "-r" in pip_calls[0]


def test_refuses_when_install_has_local_edits(repos):
    remote, install = repos
    push_change(remote)
    (install / "code.py").write_text("my hack\n")
    with pytest.raises(update.UpdateError, match="local code edits"):
        update.update_git_install(install)
    assert (install / "code.py").read_text() == "my hack\n"


def test_version_string(repos):
    _, install = repos
    assert "main @" in update.current_version(install)


def test_quiet_check_reports_behind(repos):
    remote, install = repos
    push_change(remote)
    assert update.updates_available_quietly(install) == 1


def test_quiet_check_never_raises(tmp_path):
    (tmp_path / ".git").mkdir()  # looks like a git install but isn't valid
    assert update.updates_available_quietly(tmp_path) is None


# ---------------------------------------------------------------- auto_update

def test_auto_update_pulls_when_behind(repos):
    remote, install = repos
    push_change(remote)
    msg = update.auto_update(install)
    assert msg and msg.startswith("Updated to the latest version")
    assert (install / "code.py").read_text() == "v = 2\n"


def test_auto_update_silent_when_current(repos):
    _, install = repos
    assert update.auto_update(install) is None


def test_auto_update_never_raises_when_github_unreachable(repos):
    _, install = repos
    git(install, "remote", "set-url", "origin", str(install.parent / "does-not-exist"))
    msg = update.auto_update(install)
    assert msg.startswith("Couldn't check GitHub")
    assert (install / "code.py").read_text() == "v = 1\n"


def test_auto_update_skips_dirty_install(repos):
    remote, install = repos
    push_change(remote)
    (install / "code.py").write_text("my hack\n")
    assert "local code edits" in update.auto_update(install)
    assert (install / "code.py").read_text() == "my hack\n"


def test_auto_update_follows_new_default_branch(repos):
    """Feature branch merged to a new default branch and deleted: installs follow."""
    remote, install = repos
    git(remote, "checkout", "-q", "-b", "trunk")
    push_change(remote, text="v = 3\n")
    git(remote, "branch", "-q", "-D", "main")
    msg = update.auto_update(install)
    assert msg and "trunk @" in msg
    assert (install / "code.py").read_text() == "v = 3\n"
    assert update.auto_update(install) is None  # and stays put afterwards


def test_gui_respects_auto_update_setting(tmp_path, monkeypatch):
    from bizbuy.gui import auto_update_enabled

    monkeypatch.delenv("BIZBUY_NO_AUTO_UPDATE", raising=False)
    assert auto_update_enabled(tmp_path) is True  # default on, no settings file
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "app.yaml").write_text("auto_update: false\n")
    assert auto_update_enabled(tmp_path) is False
    (tmp_path / "config" / "app.yaml").write_text("auto_update: true\n")
    monkeypatch.setenv("BIZBUY_NO_AUTO_UPDATE", "1")
    assert auto_update_enabled(tmp_path) is False
