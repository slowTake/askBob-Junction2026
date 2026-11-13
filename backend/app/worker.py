"""Ingest worker: `python -m app.worker`.

Started from code (not the `rq worker --url ...` CLI) so the Valkey URL, which
contains a password, never shows up in the process list.
"""

import logging

from rq import Worker

from app.db import init_db
from app.valkey import INGEST_QUEUE, get_redis


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    init_db()
    Worker([INGEST_QUEUE], connection=get_redis()).work(with_scheduler=False)


if __name__ == "__main__":
    main()
