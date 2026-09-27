import logging

import requests

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10


def send_card(webhook_url: str, payload: dict) -> None:
    try:
        response = requests.post(webhook_url, json=payload, timeout=_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException:
        logger.exception("Failed to send Google Chat notification")
