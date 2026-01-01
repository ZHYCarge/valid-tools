import logging
import logging.config
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict


class RangeRotatingFileHandler(RotatingFileHandler):
    def __init__(self, filename: str, maxBytes: int = 0, **kwargs) -> None:
        super().__init__(filename, maxBytes=maxBytes, backupCount=0, **kwargs)
        self._range_start = self._initial_start_date()

    def _initial_start_date(self) -> datetime:
        if os.path.exists(self.baseFilename) and os.path.getsize(self.baseFilename) > 0:
            ts = os.path.getctime(self.baseFilename)
            return datetime.fromtimestamp(ts)
        return datetime.now()

    def _range_name(self, start: datetime, end: datetime) -> str:
        base = os.path.basename(self.baseFilename)
        prefix = base[:-4] if base.endswith(".log") else base
        return f"{prefix}-{start:%Y%m%d}-{end:%Y%m%d}.log"

    def doRollover(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None
        if os.path.exists(self.baseFilename) and os.path.getsize(self.baseFilename) > 0:
            end_date = datetime.now()
            target = os.path.join(
                os.path.dirname(self.baseFilename),
                self._range_name(self._range_start, end_date),
            )
            os.replace(self.baseFilename, target)
        self._range_start = datetime.now()
        if not self.delay:
            self.stream = self._open()


def _log_max_bytes() -> int:
    value = os.environ.get("LOG_MAX_BYTES", "5242880")
    try:
        return max(0, int(value))
    except ValueError:
        return 5242880


def build_logging_config(logs_dir: str) -> Dict:
    os.makedirs(logs_dir, exist_ok=True)
    app_log = os.path.join(logs_dir, "app.log")
    error_log = os.path.join(logs_dir, "error.log")
    access_log = os.path.join(logs_dir, "access.log")
    ops_log = os.path.join(logs_dir, "ops.log")
    max_bytes = _log_max_bytes()

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s"
            },
        },
        "handlers": {
            "app_file": {
                "()": "app.utils.logging_config.RangeRotatingFileHandler",
                "filename": app_log,
                "formatter": "standard",
                "encoding": "utf-8",
                "maxBytes": max_bytes,
            },
            "error_file": {
                "()": "app.utils.logging_config.RangeRotatingFileHandler",
                "filename": error_log,
                "formatter": "standard",
                "encoding": "utf-8",
                "maxBytes": max_bytes,
            },
            "access_file": {
                "()": "app.utils.logging_config.RangeRotatingFileHandler",
                "filename": access_log,
                "formatter": "standard",
                "encoding": "utf-8",
                "maxBytes": max_bytes,
            },
            "ops_file": {
                "()": "app.utils.logging_config.RangeRotatingFileHandler",
                "filename": ops_log,
                "formatter": "standard",
                "encoding": "utf-8",
                "maxBytes": max_bytes,
            },
        },
        "loggers": {
            "app": {"handlers": ["app_file"], "level": "INFO"},
            "ops": {"handlers": ["ops_file"], "level": "INFO"},
            "uvicorn.error": {"handlers": ["error_file"], "level": "INFO"},
            "uvicorn.access": {"handlers": ["access_file"], "level": "INFO"},
        },
        "root": {"handlers": ["app_file"], "level": "INFO"},
    }


def configure_logging(logs_dir: str) -> None:
    logging.config.dictConfig(build_logging_config(logs_dir))


def close_log_handlers(target_path: str) -> None:
    loggers = [logging.getLogger()]
    loggers.extend(
        [logger for logger in logging.root.manager.loggerDict.values() if hasattr(logger, "handlers")]
    )
    for logger in loggers:
        handlers = getattr(logger, "handlers", [])
        for handler in list(handlers):
            filename = getattr(handler, "baseFilename", None)
            if filename and os.path.abspath(filename) == os.path.abspath(target_path):
                try:
                    handler.close()
                finally:
                    try:
                        logger.removeHandler(handler)
                    except Exception:
                        pass
