import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_add_then_list_shows_one_line_per_task(cli):
    status, out, _ = cli("add", "Pay rent", "--due", "2025-03-01", "--priority", "high",
                         "--tag", "Home", "--tag", "bills")
    assert (status, out) == (0, "Added task 1: Pay rent\n")
    assert cli("add", "Call plumber")[0] == 0
    status, out, _ = cli("list")
    assert status == 0
    assert out.splitlines() == [
        "  1 [!] 2025-03-01 high   Pay rent #home #bills",
        "  2 [ ] -          normal Call plumber",
    ]


def test_list_filters_and_sorts(cli):
    cli("add", "Write report", "--due", "2025-04-02", "--tag", "work")
    cli("add", "Book flights", "--due", "2025-03-20", "--priority", "high", "--tag", "travel")
    cli("add", "Tidy desk", "--priority", "low", "--tag", "work")
    assert [line.split()[0] for line in cli("list", "--sort", "due")[1].splitlines()] == ["2", "1", "3"]
    assert [line.split()[0] for line in cli("list", "--tag", "work")[1].splitlines()] == ["1", "3"]
    assert cli("list", "--priority", "high")[1] == "  2 [ ] 2025-03-20 high   Book flights #travel\n"
    assert cli("list", "--tag", "home")[:2] == (0, "No tasks.\n")


def test_done_completes_a_task_and_may_be_repeated(cli, store_path):
    cli("add", "Pay rent", "--due", "2025-03-20")
    assert cli("done", "1")[:2] == (0, "Completed task 1: Pay rent\n")
    saved = store_path.read_text()
    record = json.loads(saved)["tasks"][0]
    assert record["done"] is True and record["completed"] == "2025-03-14"
    assert cli("done", "1")[:2] == (0, "Task 1 is already done\n")
    assert store_path.read_text() == saved
    assert cli("list")[1] == "No tasks.\n"
    assert cli("list", "--all")[1] == "  1 [x] 2025-03-20 normal Pay rent\n"


def test_rm_deletes_a_task(cli, store_path):
    cli("add", "Pay rent")
    cli("add", "Call plumber")
    assert cli("rm", "1")[:2] == (0, "Removed task 1: Pay rent\n")
    assert [record["id"] for record in json.loads(store_path.read_text())["tasks"]] == [2]
    assert cli("add", "Buy milk")[1] == "Added task 3: Buy milk\n"


def test_errors_exit_with_status_2_and_leave_the_store_alone(cli, store_path):
    cli("add", "Pay rent")
    saved = store_path.read_text()
    for argv in (
        ["done", "9"],
        ["rm", "9"],
        ["add", "Dentist", "--due", "2025-02-30"],
        ["add", "Dentist", "--due", "next week"],
        ["add", "Dentist", "--priority", "urgent"],
        ["add", "   "],
        ["list", "--sort", "title"],
    ):
        status, out, err = cli(*argv)
        assert status == 2, argv
        assert out == "" and err.strip(), argv
        assert store_path.read_text() == saved, argv


def test_runs_as_a_module(tmp_path):
    command = [sys.executable, "-m", "tasktrack", "--file", str(tmp_path / "work.json")]
    added = subprocess.run(command + ["add", "Pay rent"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert (added.returncode, added.stdout) == (0, "Added task 1: Pay rent\n")
    missing = subprocess.run(command + ["done", "5"], cwd=REPO_ROOT, capture_output=True, text=True)
    assert missing.returncode == 2 and missing.stdout == "" and missing.stderr.strip()
