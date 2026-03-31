"""Structured file logging. One log file per source per run.

Log path: logs/{pipeline}/{region}/{country}/{source}/{date}/{datetime}.log
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s — %(message)s"
LOG_DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"


def setup_logger(
    pipeline: str,
    region: str,
    country: str,
    source: str,
    logs_dir: Path = Path("logs"),
    level: int = logging.DEBUG,
) -> logging.Logger:
    """Create a file logger at logs/{pipeline}/{region}/{country}/{source}/{date}/{datetime}.log.

    Also attaches a stderr handler at INFO level for terminal visibility.
    Returns a named logger: po.{pipeline}.{source}
    """
    now = datetime.now(tz=timezone.utc)
    log_dir = logs_dir / pipeline / region / country / source / now.strftime("%Y-%m-%d")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{now.strftime('%Y%m%dT%H%M%SZ')}.log"

    logger = logging.getLogger(f"po.{pipeline}.{source}")
    logger.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FMT))
        logger.addHandler(fh)

        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FMT))
        logger.addHandler(sh)

    return logger
