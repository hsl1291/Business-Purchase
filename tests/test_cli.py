from bizbuy import cli
from bizbuy.resources import default_path


def test_help_lists_commands(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    for cmd in ("init", "run", "value", "update", "fieldmap"):
        assert cmd in out


def test_unknown_command_returns_2(capsys):
    assert cli.main(["nope"]) == 2


def test_init_creates_workspace_and_never_overwrites(tmp_path):
    ws = tmp_path / "ws"
    assert cli.main(["init", str(ws)]) == 0
    cfg = ws / "config" / "scoring.yaml"
    assert cfg.exists()
    assert (ws / "samples" / "deals").is_dir()
    assert (ws / "data" / "raw").is_dir()

    cfg.write_text("# my edits\n")
    (ws / "samples" / "sample_pnl.yaml").write_text("# mine\n")
    cli.main(["init", str(ws)])
    assert cfg.read_text() == "# my edits\n"
    assert (ws / "samples" / "sample_pnl.yaml").read_text() == "# mine\n"


def test_default_path_prefers_workspace_copy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert "resources" in default_path("scoring.yaml")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "scoring.yaml").write_text("x")
    assert default_path("scoring.yaml") == "config/scoring.yaml".replace("/", __import__("os").sep)


def test_run_end_to_end_with_bundled_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cli.main(["init", "."])
    assert cli.main(["run", "samples/sample_raw_licenses.csv", "--out-dir", "out"]) == 0
    assert (tmp_path / "out" / "ranked_with_estimate.csv").exists()
    assert cli.main(["value", "samples/sample_pnl.yaml"]) == 0
