# -*- coding: utf-8 -*-
"""Action logging and uncaught-exception reports for XMD."""
import faulthandler
import json
import logging
import os
import sys
import threading
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOGGER = logging.getLogger("xmd")
_LOG_DIR = None
_REPORT_DIR = None
_FAULT_STREAM = None
_INSTALLED = False


def configure(app_dir):
    global _LOG_DIR, _REPORT_DIR, _FAULT_STREAM, _INSTALLED
    if _INSTALLED:
        return _LOGGER
    preferred = Path(app_dir) / "data" / "xmd"
    try:
        (preferred / "logs").mkdir(parents=True, exist_ok=True)
        (preferred / "crash_reports").mkdir(parents=True, exist_ok=True)
        root = preferred
    except OSError:
        local = os.environ.get("LOCALAPPDATA") or str(Path.home())
        root = Path(local) / "XMD" / "data" / "xmd"
        (root / "logs").mkdir(parents=True, exist_ok=True)
        (root / "crash_reports").mkdir(parents=True, exist_ok=True)
    _LOG_DIR = root / "logs"
    _REPORT_DIR = root / "crash_reports"
    _LOGGER.setLevel(logging.INFO)
    _LOGGER.propagate = False
    handler = RotatingFileHandler(
        _LOG_DIR / "actions.log", maxBytes=2 * 1024 * 1024,
        backupCount=5, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _LOGGER.addHandler(handler)
    _LOGGER.info("application.start app_dir=%r", str(app_dir))
    _FAULT_STREAM = open(_REPORT_DIR / "fatal-errors.log", "a", encoding="utf-8")
    try:
        faulthandler.enable(file=_FAULT_STREAM, all_threads=True)
    except (RuntimeError, OSError):
        pass
    sys.excepthook = _sys_exception_hook
    threading.excepthook = _thread_exception_hook
    sys.unraisablehook = _unraisable_exception_hook
    _INSTALLED = True
    return _LOGGER


def log_action(action, **details):
    payload = json.dumps(details, ensure_ascii=False, sort_keys=True, default=str)
    _LOGGER.info("action=%s details=%s", action, payload)


def log_error(action, **details):
    payload = json.dumps(details, ensure_ascii=False, sort_keys=True, default=str)
    _LOGGER.error("action=%s details=%s", action, payload)


def _write_crash_report(exc_type, exc_value, exc_tb, source):
    if _REPORT_DIR is None:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report = _REPORT_DIR / f"crash-{stamp}-{os.getpid()}.txt"
    formatted = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        report.write_text(
            "XMD crash report\n"
            f"Time: {datetime.now().astimezone().isoformat()}\n"
            f"Process: {os.getpid()}\n"
            f"Source: {source}\n"
            f"Python: {sys.version}\n"
            f"Platform: {sys.platform}\n\n"
            f"{formatted}", encoding="utf-8",
        )
        _LOGGER.critical("crash source=%s report=%s\n%s", source, report, formatted)
    except OSError:
        _LOGGER.exception("failed to save crash report from %s", source)
    return str(report)


def _sys_exception_hook(exc_type, exc_value, exc_tb):
    _write_crash_report(exc_type, exc_value, exc_tb, "main thread")
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def _thread_exception_hook(args):
    _write_crash_report(args.exc_type, args.exc_value, args.exc_traceback,
                        f"thread {args.thread.name if args.thread else 'unknown'}")
    if hasattr(threading, "__excepthook__"):
        threading.__excepthook__(args)


def _unraisable_exception_hook(args):
    _write_crash_report(args.exc_type, args.exc_value, args.exc_traceback,
                        f"unraisable {args.object!r}")
    if hasattr(sys, "__unraisablehook__"):
        sys.__unraisablehook__(args)
