from datetime import date

import pytest

from tasktrack.models import Task, ValidationError, parse_date


def test_parse_date_reads_iso_dates():
    assert parse_date("2025-03-01") == date(2025, 3, 1)
    assert parse_date(" 2024-02-29 ") == date(2024, 2, 29)


def test_parse_date_rejects_what_is_not_a_date():
    for text in ("2025-02-30", "2023-02-29", "2025-13-01", "01/03/2025", "2025-3-1", "tomorrow", ""):
        with pytest.raises(ValidationError):
            parse_date(text)


def test_a_task_round_trips_through_its_record():
    task = Task(7, "Pay rent", due=date(2025, 3, 1), priority="high", tags=["home", "bills"],
                created=date(2025, 2, 20))
    record = task.to_dict()
    assert record["id"] == 7 and record["title"] == "Pay rent"
    assert record["due"] == "2025-03-01" and record["created"] == "2025-02-20"
    assert record["completed"] is None and record["done"] is False
    assert record["tags"] == ["home", "bills"]
    assert Task.from_dict(record) == task


def test_a_task_cleans_its_tags_and_checks_its_fields():
    assert Task(1, "  Pay rent ").title == "Pay rent"
    assert Task(1, "Pay rent", tags=["Home", " bills", "#home", ""]).tags == ["home", "bills"]
    with pytest.raises(ValidationError):
        Task(1, "   ")
    with pytest.raises(ValidationError):
        Task(1, "Pay rent", priority="urgent")
    with pytest.raises(ValidationError):
        Task.from_dict({"title": "no id"})
