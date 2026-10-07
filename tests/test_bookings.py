import pytest

from bookings import service
from schedule.service import create_class


def make_class(capacity=2):
    return create_class("Spinning", "Marta", "2026-10-10 18:00", 45, capacity)


def statuses(class_id):
    return {b["member_email"]: b["status"] for b in service.list_bookings(class_id)}


@pytest.mark.parametrize(
    "confirmed_count, capacity, expected",
    [(0, 2, "confirmed"), (1, 2, "confirmed"), (2, 2, "waitlisted"), (3, 2, "waitlisted")],
)
def test_decide_status(confirmed_count, capacity, expected):
    assert service.decide_status(confirmed_count, capacity) == expected


def test_bookings_are_confirmed_until_class_is_full():
    class_id = make_class(capacity=2)
    assert service.book_class(class_id, "Ana", "ana@test.com") == "confirmed"
    assert service.book_class(class_id, "Luis", "luis@test.com") == "confirmed"
    assert service.book_class(class_id, "Sofia", "sofia@test.com") == "waitlisted"


def test_booking_unknown_class_is_rejected():
    with pytest.raises(ValueError, match="Class not found"):
        service.book_class(999, "Ana", "ana@test.com")


@pytest.mark.parametrize("name, email", [("  ", "ana@test.com"), ("Ana", "not-an-email")])
def test_invalid_member_details_are_rejected(name, email):
    class_id = make_class()
    with pytest.raises(ValueError):
        service.book_class(class_id, name, email)


def test_same_email_cannot_book_twice_ignoring_case():
    class_id = make_class()
    service.book_class(class_id, "Ana", "ana@test.com")
    with pytest.raises(ValueError, match="already have a booking"):
        service.book_class(class_id, "Ana", "ANA@test.com")


def test_member_can_book_again_after_cancelling():
    class_id = make_class()
    service.book_class(class_id, "Ana", "ana@test.com")
    booking_id = service.list_bookings(class_id)[0]["id"]
    service.cancel_booking(booking_id)
    assert service.book_class(class_id, "Ana", "ana@test.com") == "confirmed"


def test_cancelling_confirmed_promotes_earliest_waitlisted():
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


def test_cancelling_waitlisted_promotes_nobody():
    class_id = make_class(capacity=1)
    service.book_class(class_id, "Ana", "ana@test.com")
    service.book_class(class_id, "Luis", "luis@test.com")
    luis_id = service.list_bookings(class_id)[1]["id"]

    assert service.cancel_booking(luis_id) is None
    assert statuses(class_id)["ana@test.com"] == "confirmed"


def test_cancelling_with_empty_waitlist_promotes_nobody():
    class_id = make_class(capacity=2)
    service.book_class(class_id, "Ana", "ana@test.com")
    ana_id = service.list_bookings(class_id)[0]["id"]
    assert service.cancel_booking(ana_id) is None


def test_cancelling_twice_or_missing_booking_is_rejected():
    class_id = make_class()
    service.book_class(class_id, "Ana", "ana@test.com")
    ana_id = service.list_bookings(class_id)[0]["id"]
    service.cancel_booking(ana_id)
    with pytest.raises(ValueError):
        service.cancel_booking(ana_id)
    with pytest.raises(ValueError):
        service.cancel_booking(999)