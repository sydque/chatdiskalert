import logging
import signal
import time
from datetime import datetime, timedelta

from app.config import Config, load_config
from app.disk_monitor import DiskUsage, get_disk_usage
from app.notifier import send_card
from app.scheduler import next_reminder_time
from app.state import AlertState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

_running = True


def _handle_shutdown(signum, frame):
    global _running
    logger.info("Received signal %s, shutting down...", signum)
    _running = False


def _format_bytes(num_bytes: int) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if value < 1024:
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{value:.1f}EB"


def _format_duration(delta: timedelta) -> str:
    total_seconds = max(int(delta.total_seconds()), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _card_payload(
    config: Config, card_id: str, title: str, fields: list, status_color: str, status_text: str
) -> dict:
    widgets = [{"decoratedText": {"topLabel": label, "text": text}} for label, text in fields]
    widgets.append(
        {
            "decoratedText": {
                "topLabel": "Status",
                "text": f'<font color="{status_color}"><b>{status_text}</b></font>',
            }
        }
    )
    header = {"title": title}
    return {
        "cardsV2": [
            {
                "cardId": card_id,
                "card": {
                    "header": header,
                    "sections": [{"header": "Detail Disk", "widgets": widgets}],
                },
            }
        ]
    }


def _breach_payload(config: Config, usage: DiskUsage, threshold: float) -> dict:
    return _card_payload(
        config,
        card_id="chatdiskalert-breach",
        title="\u26A0\uFE0F Disk Alert",
        fields=[
            ("Host", config.hostname_label),
            ("Path", usage.path),
            ("Usage", f"<b>{usage.percent:.1f}%</b> (threshold: {threshold:.1f}%)"),
            ("Used / Total", f"{_format_bytes(usage.used)} / {_format_bytes(usage.total)}"),
            ("Free", _format_bytes(usage.free)),
        ],
        status_color="#ff5555",
        status_text="BREACH",
    )


def _resolved_payload(config: Config, usage: DiskUsage, threshold: float, duration: timedelta) -> dict:
    return _card_payload(
        config,
        card_id="chatdiskalert-resolved",
        title="\u2705 Disk Alert Resolved",
        fields=[
            ("Host", config.hostname_label),
            ("Path", usage.path),
            ("Usage", f"<b>{usage.percent:.1f}%</b> (threshold: {threshold:.1f}%)"),
            ("Unresolved For", _format_duration(duration)),
        ],
        status_color="#33cc66",
        status_text="RESOLVED",
    )


def _reminder_payload(config: Config, path: str, percent: float, threshold: float, duration: timedelta) -> dict:
    return _card_payload(
        config,
        card_id="chatdiskalert-reminder",
        title="\U0001F514 Disk Alert Reminder",
        fields=[
            ("Host", config.hostname_label),
            ("Path", path),
            ("Usage", f"<b>{percent:.1f}%</b> (threshold: {threshold:.1f}%)"),
            ("Unresolved Since", _format_duration(duration)),
        ],
        status_color="#ffaa00",
        status_text="STILL UNRESOLVED",
    )


def _startup_payload(config: Config) -> dict:
    return _card_payload(
        config,
        card_id="chatdiskalert-startup",
        title="\u2139\uFE0F Disk Alert Started",
        fields=[("Host", config.hostname_label), ("Watching", ", ".join(config.disk_paths))],
        status_color="#4285f4",
        status_text="STARTED",
    )


def _check_disks(config: Config, states: dict) -> None:
    for path, state in states.items():
        try:
            usage = get_disk_usage(path, config.host_mount_prefix)
        except OSError:
            logger.exception("Failed to read disk usage for %s", path)
            continue

        threshold = config.threshold_for(path)
        state.last_percent = usage.percent
        now = datetime.now()

        if usage.percent >= threshold and not state.active:
            state.active = True
            state.triggered_at = now
            state.next_reminder_at = next_reminder_time(config.reminder_cron, now)
            logger.warning("Disk %s breached threshold: %.1f%% >= %.1f%%", path, usage.percent, threshold)
            send_card(config.webhook_url, _breach_payload(config, usage, threshold))
        elif usage.percent < threshold and state.active:
            duration = now - state.triggered_at
            logger.info("Disk %s resolved: %.1f%% < %.1f%%", path, usage.percent, threshold)
            send_card(config.webhook_url, _resolved_payload(config, usage, threshold, duration))
            state.active = False
            state.triggered_at = None
            state.next_reminder_at = None


def _check_reminders(config: Config, states: dict) -> None:
    if not config.reminder_cron:
        return

    now = datetime.now()
    for path, state in states.items():
        if not state.active or state.next_reminder_at is None or now < state.next_reminder_at:
            continue

        duration = now - state.triggered_at
        threshold = config.threshold_for(path)
        logger.info("Sending reminder for %s (unresolved for %s)", path, _format_duration(duration))
        send_card(
            config.webhook_url,
            _reminder_payload(config, path, state.last_percent, threshold, duration),
        )
        state.next_reminder_at = next_reminder_time(config.reminder_cron, now)


def main() -> None:
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    config = load_config()
    states = {path: AlertState(path=path) for path in config.disk_paths}

    logger.info(
        "Starting chatdiskalert: paths=%s default_threshold=%.1f%% interval=%ss reminder_cron=%r",
        config.disk_paths,
        config.default_threshold,
        config.check_interval_seconds,
        config.reminder_cron or "disabled",
    )

    if config.send_startup_message:
        send_card(config.webhook_url, _startup_payload(config))

    while _running:
        _check_disks(config, states)
        _check_reminders(config, states)
        time.sleep(config.check_interval_seconds)

    logger.info("chatdiskalert stopped")


if __name__ == "__main__":
    main()
