from datetime import datetime
from typing import Optional

from croniter import croniter


def next_reminder_time(cron_expr: str, base: datetime) -> Optional[datetime]:
    """Return the next reminder timestamp after `base`, or None if reminders are disabled."""
    if not cron_expr:
        return None
    return croniter(cron_expr, base).get_next(datetime)
