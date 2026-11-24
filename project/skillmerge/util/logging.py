from __future__ import annotations

import logging
import re
import sys

_KEY_PATTERN = re.compile(r"(?i)(api[_\-]?key|authorization|x-skillmerge-token)(\s*[:=]\s*)([^\s,;\"']+)")
_SK_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}\b")
_TOKEN_PATTERN = re.compile(r"\b[0-9a-f]{64}\b")


def redact(text: str) -> str:
    if not text:
        return text
    text = _KEY_PATTERN.sub(lambda m: m.group(1) + m.group(2) + "***", text)
    text = _SK_PATTERN.sub("sk-***", text)
    return _TOKEN_PATTERN.sub("***", text)


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact(super().format(record))


def get_logger(name: str = "skillmerge") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger