"""Logging setup shared by backend, ML modules and the Streamlit frontend."""
from __future__ import annotations

import logging
import warnings
from logging.handlers import RotatingFileHandler

from config.settings import settings

_CONFIGURED = False


def setup_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    # numpy 2.x + macOS Accelerate emit spurious FP-flag warnings on matmul although results are finite.
    warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)
    root = logging.getLogger()
    root.setLevel(settings.log_level)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.addHandler(console)
    try:
        settings.log_dir.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(settings.log_dir / "app.log", maxBytes=2_000_000, backupCount=3)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except OSError:  # read-only filesystem etc. - console logging is enough
        pass
    for noisy in ("urllib3", "sentence_transformers", "transformers", "numba", "matplotlib", "httpx", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
