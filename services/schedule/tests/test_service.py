import pytest

from app import service


def make_class(**overrides):
    data = {
        "name": "Yoga",
        "instructor": "Marta",
        "starts_at": "2026-10-10 18:00",
        "duration_minutes": 60,
        "capacity": 10,
    }
    data.update(overrides)
    return service.create_class(**data)


def test_create_class_is_listed():
    class_id = make_class()
    classes = service.list_classes()
    assert len(classes) == 1
    assert classes[0]["id"] == class_id
    assert classes[0]["name"] == "Yoga"
    assert classes[0]["starts_at"] == "2026-10-10 18:00"
    assert classes[0]["room"] == "Main studio"


def test_classes_are_listed_by_start_time():
    make_class(name="Late", starts_at="2026-10-10 20:00")
    make_class(name="Early", starts_at="2026-10-10 08:00")
    names = [c["name"] for c in service.list_classes()]
    assert names == ["Early", "Late"]


def test_name_instructor_and_room_are_trimmed():
    make_class(name="  Boxing  ", instructor=" Leo ", room=" Studio 2 ")
    saved = service.list_classes()[0]
    assert (saved["name"], saved["instructor"], saved["room"]) == ("Boxing", "Leo", "Studio 2")


@pytest.mark.parametrize(
    "overrides",
    [
        {"name": "   "},
        {"instructor": ""},
        {"room": " "},
        {"starts_at": "tomorrow"},
        {"duration_minutes": 0},
        {"capacity": 0},
    ],
)
def test_invalid_class_is_rejected_and_not_saved(overrides):
    with pytest.raises(ValueError):
        make_class(**overrides)
    assert service.list_classes() == []


def test_get_class():
    class_id = make_class(capacity=12)
    found = service.get_class(class_id)
    assert found["capacity"] == 12
    assert found["name"] == "Yoga"


def test_get_missing_class_is_none():
    assert service.get_class(999) is None
