import pytest

from app import service
from app.schedule_client import ScheduleUnavailable


@pytest.fixture
def make_class(schedule):
    def make(class_id=1, capacity=2):
        schedule.classes[class_id] = {"id": class_id, "name": "Spinning", "capacity": capacity}
        return class_id
    return make


def statuses(class_id):
    return {b["member_email"]: b["status"] for b in service.list_bookings(class_id)}


@pytest.mark.parametrize(
    "confirmed_count, capacity, expected",
    [(0, 2, "confirmed"), (1, 2, "confirmed"), (2, 2, "waitlisted"), (3, 2, "waitlisted")],
)
def test_decide_status(confirmed_count, capacity, expected):
    assert service.decide_status(confirmed_count, capacity) == expected


def test_bookings_are_confirmed_until_class_is_full(make_class):
    class_id = make_class(capacity=2)
    assert service.book_class(class_id, "Ana", "ana@test.com") == "confirmed"
    assert service.book_class(class_id, "Luis", "luis@test.com") == "confirmed"
    assert service.book_class(class_id, "Sofia", "sofia@test.com") == "waitlisted"


def test_booking_unknown_class_is_rejected(schedule):
    with pytest.raises(ValueError, match="Class not found"):
        service.book_class(999, "Ana", "ana@test.com")


def test_booking_while_schedule_is_down_saves_nothing(make_class, schedule):
    class_id = make_class()
    schedule.down = True
    with pytest.raises(ScheduleUnavailable):
        service.book_class(class_id, "Ana", "ana@test.com")
    assert service.list_bookings(class_id) == []


def test_cancelling_works_while_schedule_is_down(make_class, schedule):
    class_id = make_class(capacity=1)
    service.book_class(class_id, "Ana", "ana@test.com")
    service.book_class(class_id, "Luis", "luis@test.com")
    schedule.down = True
    ana_id = service.list_bookings(class_id)[0]["id"]
    service.cancel_booking(ana_id)
    assert statuses(class_id)["luis@test.com"] == "confirmed"


@pytest.mark.parametrize("name, email", [("  ", "ana@test.com"), ("Ana", "not-an-email")])
def test_invalid_member_details_are_rejected(make_class, name, email):
    class_id = make_class()
    with pytest.raises(ValueError):
        service.book_class(class_id, name, email)


def test_same_email_cannot_book_twice_ignoring_case(make_class):
    class_id = make_class()
    service.book_class(class_id, "Ana", "ana@test.com")
    with pytest.raises(ValueError, match="already have a booking"):
        service.book_class(class_id, "Ana", "ANA@test.com")


def test_member_can_book_again_after_cancelling(make_class):
    class_id = make_class()
    service.book_class(class_id, "Ana", "ana@test.com")
    booking_id = service.list_bookings(class_id)[0]["id"]
    service.cancel_booking(booking_id)
    assert service.book_class(class_id, "Ana", "ana@test.com") == "confirmed"


def test_cancelling_confirmed_promotes_earliest_waitlisted(make_class):
    class_id = make_class(capacity=1)
    service.book_class(class_id, "Ana", "ana@test.com")
    service.book_class(class_id, "Luis", "luis@test.com")
    service.book_class(class_id, "Sofia", "sofia@test.com")
    ana_id = service.list_bookings(class_id)[0]["id"]

    promoted_id = service.cancel_booking(ana_id)

    assert statuses(class_id) == {
        "ana@test.com": "cancelled",
        "luis@test.com": "confirmed",
        "sofia@test.com": "waitlisted",
    }
    assert promoted_id == service.list_bookings(class_id)[1]["id"]


def test_cancelling_waitlisted_promotes_nobody(make_class):
    class_id = make_class(capacity=1)
    service.book_class(class_id, "Ana", "ana@test.com")
    service.book_class(class_id, "Luis", "luis@test.com")
    luis_id = service.list_bookings(class_id)[1]["id"]

    assert service.cancel_booking(luis_id) is None
    assert statuses(class_id)["ana@test.com"] == "confirmed"


def test_cancelling_with_empty_waitlist_promotes_nobody(make_class):
    class_id = make_class(capacity=2)
    service.book_class(class_id, "Ana", "ana@test.com")
    ana_id = service.list_bookings(class_id)[0]["id"]
    assert service.cancel_booking(ana_id) is None


def test_cancelling_twice_or_missing_booking_is_rejected(make_class):
    class_id = make_class()
    service.book_class(class_id, "Ana", "ana@test.com")
    ana_id = service.list_bookings(class_id)[0]["id"]
    service.cancel_booking(ana_id)
    with pytest.raises(ValueError):
        service.cancel_booking(ana_id)
    with pytest.raises(ValueError):
        service.cancel_booking(999)
