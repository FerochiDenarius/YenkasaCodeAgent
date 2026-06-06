from __future__ import annotations

import contextvars
import json
import logging
from datetime import datetime
from datetime import timezone
from typing import Any


request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def get_request_id() -> str:
    return request_id_context.get()


def set_request_id(request_id: str):
    return request_id_context.set(request_id)


def reset_request_id(token) -> None:
    request_id_context.reset(token)


def log_structured(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "request_id": get_request_id(),
        **fields,
    }
    logger.log(level, json.dumps(payload, default=str, separators=(",", ":")))
