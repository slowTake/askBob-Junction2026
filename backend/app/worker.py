"""Ingest worker: `python -m app.worker`.

Started from code (not the `rq worker --url ...` CLI) so the Valkey URL, which
contains a password, never shows up in the process list.
"""

import logging
from datetime import UTC, datetime

from rq import Worker

from app.db import init_db
from app.ingest.jobs import on_work_horse_killed
from app.ingest.recovery import requeue_stranded
from app.valkey import INGEST_QUEUE, get_redis

log = logging.getLogger(__name__)

# How often RQ looks for jobs whose worker died (they are then marked failed). Its
# default is 10 minutes; a dead worker's job heartbeat expires after about 90 s.
MAINTENANCE_INTERVAL_S = 60


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    init_db()
    try:
        requeue_stranded(datetime.now(UTC))
    except Exception:
        log.exception("could not check for documents whose ingest job was lost")
    Worker(
        [INGEST_QUEUE],
        connection=get_redis(),
        work_horse_killed_handler=on_work_horse_killed,
        maintenance_interval=MAINTENANCE_INTERVAL_S,
    ).work(with_scheduler=False)


if __name__ == "__main__":
    main()
