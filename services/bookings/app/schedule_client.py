"""The only place bookings talks to the schedule service."""
import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

log = logging.getLogger(__name__)


class ScheduleUnavailable(Exception):
    """The schedule service is down, too slow, or answered with an error."""


def get_class(class_id):
    """Return the class as a dict, None if it does not exist, or raise ScheduleUnavailable."""
    base_url = os.environ.get("SCHEDULE_URL", "http://localhost:8001")
    timeout = float(os.environ.get("SCHEDULE_TIMEOUT_SECONDS", "2"))
    try:
        with urlopen(f"{base_url}/api/classes/{class_id}", timeout=timeout) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return None
        log.warning("Schedule service answered %s for class %s", error.code, class_id)
        raise ScheduleUnavailable(f"schedule answered {error.code}") from error
    except (URLError, TimeoutError, OSError, ValueError) as error:
        log.warning("Schedule service unreachable for class %s: %s", class_id, error)
        raise ScheduleUnavailable(str(error)) from error
