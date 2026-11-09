"""Production logging setup for RateMyPic.

Configures standard timestamps, log levels (INFO, WARNING, ERROR),
and module names so every log is easy to read and trace.
"""

import logging
import os
import sys


def setup_logging() -> None:
    """Set up clean, production-ready logging format."""
    # Read log level from environment (default: INFO)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
