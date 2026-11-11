import os
from urllib.parse import unquote, urlparse

import pymssql


def connect(database_url=None, autocommit=False):
    url = urlparse(database_url or os.environ["DATABASE_URL"])
    return pymssql.connect(
        server=url.hostname,
        port=url.port or 1433,
        user=unquote(url.username),
        password=unquote(url.password),
        database=url.path.lstrip("/"),
        login_timeout=5,
        timeout=5,
        autocommit=autocommit,
    )
