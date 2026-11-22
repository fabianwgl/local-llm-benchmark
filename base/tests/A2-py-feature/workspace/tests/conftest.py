import pytest

from tasktrack.cli import main

TODAY = "2025-03-14"


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setenv("TASKTRACK_TODAY", TODAY)


@pytest.fixture
def store_path(tmp_path):
    return tmp_path / "tasks.json"


@pytest.fixture
def cli(store_path, capsys):
    """Run the command line in-process against store_path; returns (exit status, stdout, stderr)."""

    def run(*argv):
        try:
            status = main(["--file", str(store_path), *argv])
        except SystemExit as exc:
            status = exc.code
        captured = capsys.readouterr()
        return status, captured.out, captured.err

    return run
