import json
from datetime import date

import pytest

from tasktrack.store import Store, StoreError, TaskNotFound


def test_a_missing_file_is_an_empty_store_until_it_is_saved(store_path):
    store = Store.load(store_path)
    assert len(store) == 0 and store.next_id == 1
    assert not store_path.exists()
    store.save()
    assert json.loads(store_path.read_text())["tasks"] == []


def test_save_then_load_gives_the_same_tasks(store_path):
    store = Store.load(store_path)
    store.add("Pay rent", due=date(2025, 3, 1), priority="high", tags=["home", "bills"],
              created=date(2025, 2, 20))
    store.add("Call plumber").complete(date(2025, 2, 22))
    store.save()
    loaded = Store.load(store_path)
    assert loaded.tasks == store.tasks
    assert loaded.next_id == 3
    assert loaded.get(1).due == date(2025, 3, 1)
    assert loaded.get(2).done and loaded.get(2).completed == date(2025, 2, 22)


def test_ids_are_never_reused(store_path):
    store = Store.load(store_path)
    for title in ("one", "two", "three"):
        store.add(title)
    assert store.remove(3).title == "three"
    store.save()
    reloaded = Store.load(store_path)
    assert reloaded.add("four").id == 4
    with pytest.raises(TaskNotFound):
        reloaded.get(3)


def test_save_leaves_only_the_store_file(tmp_path):
    path = tmp_path / "nested" / "tasks.json"
    store = Store.load(path)
    store.add("Pay rent")
    store.save()
    store.add("Call plumber")
    store.save()
    assert [entry.name for entry in path.parent.iterdir()] == ["tasks.json"]
    assert len(json.loads(path.read_text())["tasks"]) == 2


def test_unusable_files_raise_store_error(store_path):
    for content in (
        "{not json",
        "[]",
        '{"version": 99, "next_id": 1, "tasks": []}',
        '{"version": 1, "next_id": 2, "tasks": [{"id": 1}]}',
    ):
        store_path.write_text(content)
        with pytest.raises(StoreError):
            Store.load(store_path)
