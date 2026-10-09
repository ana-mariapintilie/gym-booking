import os
from flask import Flask

from db import init_db
from schedule.schema import SCHEMA as SCHEDULE_SCHEMA
from bookings.schema import SCHEMA as BOOKINGS_SCHEMA
from schedule.routes import schedule_bp
from bookings.routes import bookings_bp
from schedule.service import seed_classes_if_empty

app = Flask(__name__)
init_db([SCHEDULE_SCHEMA, BOOKINGS_SCHEMA])
seed_classes_if_empty()
app.register_blueprint(schedule_bp)
app.register_blueprint(bookings_bp)

@app.route("/")
def home():
    return "Gym booking app is running"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)