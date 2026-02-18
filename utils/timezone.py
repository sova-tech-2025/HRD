from datetime import datetime
from zoneinfo import ZoneInfo

MOSCOW_TZ = ZoneInfo("Europe/Moscow")


def moscow_now() -> datetime:
    """Текущее время в МСК (naive datetime без tzinfo)."""
    return datetime.now(MOSCOW_TZ).replace(tzinfo=None)
