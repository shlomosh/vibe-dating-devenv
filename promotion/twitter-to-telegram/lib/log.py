"""Timestamped logging shared across the app.

Every potentially-blocking step logs *before* and *after* it runs, so when a task
hangs the last line in CloudWatch pinpoints exactly which operation stalled
(download, upload, or S3 Files mount I/O).
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger("promotion")


def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )
