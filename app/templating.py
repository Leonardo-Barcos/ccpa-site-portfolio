"""Jinja2 environment plus Brazilian date formatting filters."""

import logging
from datetime import UTC, date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi.templating import Jinja2Templates

from . import site_content
from .config import settings
from .paths import TEMPLATES_DIR

log = logging.getLogger("ccpa.templates")

MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)  # fmt: skip
SHORT_MONTHS = (
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
)  # fmt: skip


def _para_timezone():
    """Timezone of Pará state.

    Windows ships no IANA timezone database (and slim Docker images do not
    either), which is why `tzdata` is a dependency. If it is still missing we
    fall back to a fixed UTC-3 rather than refusing to start: Brazil dropped
    daylight saving time in 2019, so the result is identical.
    """
    try:
        return ZoneInfo("America/Belem")
    except (ZoneInfoNotFoundError, KeyError):
        log.warning("tzdata missing — falling back to a fixed UTC-3 offset.")
        return timezone(timedelta(hours=-3), "America/Belem")


TZ = _para_timezone()

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _local(value: datetime) -> datetime:
    """Naive datetimes are treated as UTC, which is how they are stored."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(TZ)


def long_date(value: datetime | date | None) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        value = _local(value)
    return f"{value.day} de {MONTHS[value.month - 1]} de {value.year}"


def short_date(value: datetime | date | None) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        value = _local(value)
    return f"{value.day:02d}/{value.month:02d}/{value.year}"


def day_number(value: datetime | date | None) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        value = _local(value)
    return f"{value.day:02d}"


def short_month(value: datetime | date | None) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        value = _local(value)
    return SHORT_MONTHS[value.month - 1]


def clock(value: datetime | None) -> str:
    if not value:
        return ""
    return _local(value).strftime("%Hh%M").replace("h00", "h")


def datetime_input(value: datetime | None) -> str:
    """Format accepted by <input type="datetime-local">."""
    if not value:
        return ""
    return _local(value).strftime("%Y-%m-%dT%H:%M")


templates.env.filters["long_date"] = long_date
templates.env.filters["short_date"] = short_date
templates.env.filters["day_number"] = day_number
templates.env.filters["short_month"] = short_month
templates.env.filters["clock"] = clock
templates.env.filters["datetime_input"] = datetime_input

templates.env.globals["site"] = site_content
templates.env.globals["app_name"] = settings.app_name
templates.env.globals["base_url"] = settings.base_url
templates.env.globals["year"] = datetime.now(TZ).year
