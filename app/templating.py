"""Jinja2 environment with the helpers templates need."""
from datetime import date, datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

import config

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _fmt_dt(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%b %d, %H:%M")
    if isinstance(value, date):
        return value.strftime("%b %d, %Y")
    return str(value or "")


def _dim_label(dim: str) -> str:
    return dim.replace("_", " ").capitalize()


templates.env.filters["dt"] = _fmt_dt
templates.env.filters["dim"] = _dim_label
templates.env.filters["topic"] = config.topic_label
templates.env.globals.update(
    DOMAINS=config.DOMAINS,
    TOPICS=config.TOPICS,
    DIFFICULTIES=config.DIFFICULTIES,
    MODELS=config.MODELS,
)
