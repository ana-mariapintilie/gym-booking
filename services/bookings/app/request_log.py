import logging
import time

from flask import g, request


def setup_logging(app, service_name):
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    # Our own line below replaces werkzeug's access log, so it is not printed twice.
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    log = logging.getLogger(service_name)

    @app.before_request
    def start_timer():
        g.started_at = time.perf_counter()

    @app.after_request
    def log_request(response):
        elapsed_ms = (time.perf_counter() - g.started_at) * 1000
        log.info("%s %s %s %.0fms", request.method, request.path,
                 response.status_code, elapsed_ms)
        return response
