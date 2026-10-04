import os
from flask import Flask

from db import init_db
from schedule.schema import SCHEMA as SCHEDULE_SCHEMA
from bookings.schema import SCHEMA as BOOKINGS_SCHEMA

app = Flask(__name__)
init_db([SCHEDULE_SCHEMA, BOOKINGS_SCHEMA])


@app.route("/")
def home():
    return "Gym booking app is running"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)