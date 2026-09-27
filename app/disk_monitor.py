import os
import shutil
from dataclasses import dataclass


@dataclass
class DiskUsage:
    path: str
    total: int
    used: int
    free: int
    percent: float


def get_disk_usage(path: str, host_mount_prefix: str) -> DiskUsage:
    """Read usage for a path as it exists on the HOST, resolved through the
    read-only bind mount available inside the container."""
    real_path = _resolve_path(path, host_mount_prefix)
    usage = shutil.disk_usage(real_path)
    percent = (usage.used / usage.total * 100) if usage.total else 0.0
    return DiskUsage(path=path, total=usage.total, used=usage.used, free=usage.free, percent=percent)


def _resolve_path(path: str, host_mount_prefix: str) -> str:
    if not host_mount_prefix:
        return path
    return os.path.join(host_mount_prefix, path.lstrip("/")) or host_mount_prefix
