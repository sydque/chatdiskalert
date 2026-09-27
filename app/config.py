import json
import os
import socket
from dataclasses import dataclass
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    webhook_url: str
    disk_paths: List[str]
    default_threshold: float
    threshold_overrides: Dict[str, float]
    check_interval_seconds: int
    reminder_cron: str
    hostname_label: str
    host_mount_prefix: str
    send_startup_message: bool

    def threshold_for(self, path: str) -> float:
        return self.threshold_overrides.get(path, self.default_threshold)


def _parse_bool(value, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def load_config() -> Config:
    webhook_url = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise ValueError("GOOGLE_CHAT_WEBHOOK_URL environment variable is required")

    # "/" is always monitored; EXTRA_FILESYSTEM adds further paths on top of it.
    extra_filesystem = [p.strip() for p in os.environ.get("EXTRA_FILESYSTEM", "").split(",") if p.strip()]
    disk_paths = ["/"] + [p for p in extra_filesystem if p != "/"]

    try:
        default_threshold = float(os.environ.get("DISK_THRESHOLD_PERCENT", "80"))
    except ValueError as exc:
        raise ValueError("DISK_THRESHOLD_PERCENT must be a number") from exc

    overrides_raw = os.environ.get("DISK_THRESHOLD_OVERRIDES", "{}").strip() or "{}"
    try:
        threshold_overrides = {k: float(v) for k, v in json.loads(overrides_raw).items()}
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("DISK_THRESHOLD_OVERRIDES must be a valid JSON object of path -> number") from exc

    try:
        check_interval_seconds = int(os.environ.get("CHECK_INTERVAL_SECONDS", "60"))
    except ValueError as exc:
        raise ValueError("CHECK_INTERVAL_SECONDS must be an integer") from exc
    if check_interval_seconds <= 0:
        raise ValueError("CHECK_INTERVAL_SECONDS must be greater than 0")

    reminder_cron = os.environ.get("REMINDER_CRON", "").strip()

    hostname_label = os.environ.get("HOSTNAME_LABEL", "").strip() or socket.gethostname()

    host_mount_prefix = os.environ.get("HOST_MOUNT_PREFIX", "/hostfs").rstrip("/")

    send_startup_message = _parse_bool(os.environ.get("SEND_STARTUP_MESSAGE"), True)

    return Config(
        webhook_url=webhook_url,
        disk_paths=disk_paths,
        default_threshold=default_threshold,
        threshold_overrides=threshold_overrides,
        check_interval_seconds=check_interval_seconds,
        reminder_cron=reminder_cron,
        hostname_label=hostname_label,
        host_mount_prefix=host_mount_prefix,
        send_startup_message=send_startup_message,
    )
