# disk-alert

A Docker-based tool that monitors disk usage on a Linux server and sends
notifications to **Google Chat** whenever usage crosses a configured threshold.
While an alert stays unresolved, the tool sends periodic reminders based on a
**cron expression**.

## Features

- Monitors the `/` filesystem by default, with additional paths configurable via `EXTRA_FILESYSTEM`.
- Global threshold via `.env`, with optional per-disk overrides (`DISK_THRESHOLD_OVERRIDES`).
- Sends Google Chat card notifications for:
  - **Breach** — usage crosses the threshold (⚠️).
  - **Reminder** — alert is still unresolved, sent on a cron schedule (🔔).
  - **Resolved** — usage drops back below the threshold (✅).
- Runs as a Docker container, reading host disk stats through a read-only bind mount.

## Project structure

```
disk-alert/
├── app/
│   ├── main.py           # main loop, message formatting, entrypoint
│   ├── config.py         # read & validate configuration from .env
│   ├── disk_monitor.py   # read disk usage via shutil.disk_usage
│   ├── notifier.py       # send messages to the Google Chat webhook
│   ├── scheduler.py      # compute the next reminder time from the cron expression
│   └── state.py          # in-memory state per disk (active/resolved)
├── .github/workflows/
│   └── docker-build.yml  # builds & pushes the image to GHCR
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── .dockerignore
```

## 1. Create a Google Chat webhook

1. Open the target Google Chat space.
2. Click the space name → **Apps & integrations** → **Manage webhooks**.
3. Create a new webhook, give it a name (e.g. `disk-alert`), then copy its URL.
4. Set that URL as `GOOGLE_CHAT_WEBHOOK_URL` in your `.env` file.

## 2. Configure `.env`

```bash
cp .env.example .env
```

Edit `.env` as needed:

| Variable | Description | Default |
|---|---|---|
| `GOOGLE_CHAT_WEBHOOK_URL` | Google Chat webhook URL (required) | - |
| `EXTRA_FILESYSTEM` | Additional paths to watch besides `/` (default), as they appear on the **host** (comma-separated) | empty |
| `DISK_THRESHOLD_PERCENT` | Default alert threshold (%) | `80` |
| `DISK_THRESHOLD_OVERRIDES` | Per-path threshold overrides, JSON, e.g. `{"/var": 90}` | `{}` |
| `CHECK_INTERVAL_SECONDS` | Disk check interval (seconds) | `60` |
| `REMINDER_CRON` | Cron expression for reminders while an alert stays unresolved. Leave empty to disable | `0 * * * *` |
| `HOSTNAME_LABEL` | Server label shown in alert messages | container hostname |
| `HOST_MOUNT_PREFIX` | Prefix where the host filesystem is mounted inside the container | `/hostfs` |
| `SEND_STARTUP_MESSAGE` | Send a confirmation message on container start | `true` |

`REMINDER_CRON` examples:
- `0 * * * *` → reminder every hour.
- `*/15 * * * *` → reminder every 15 minutes.
- `0 8,20 * * *` → reminder at 08:00 and 20:00 every day.

## 3. Build & run with Docker

```bash
docker compose up -d --build
```

`docker-compose.yml` bind-mounts the host root filesystem (`/`) to `/hostfs` inside
the container as **read-only**, so `EXTRA_FILESYSTEM` must use paths as seen on the
host (e.g. `/home`, `/var`), not paths inside the container.

View logs:

```bash
docker compose logs -f disk-alert
```

Stop:

```bash
docker compose down
```

### Using the prebuilt image from GHCR

Every push to `main`/`master` builds and publishes the image via
[.github/workflows/docker-build.yml](.github/workflows/docker-build.yml) to
`ghcr.io/sydque/disk-alert:latest`. To pull that image instead of building
locally, remove the `build: .` line from `docker-compose.yml` and run:

```bash
docker compose pull && docker compose up -d
```

## How alerts & reminders work

1. Every `CHECK_INTERVAL_SECONDS`, the tool reads usage for `/` and every path in `EXTRA_FILESYSTEM`.
2. If usage ≥ threshold and the alert wasn't already active → send a breach alert, mark it **active**.
3. While the alert stays **active**, each time the `REMINDER_CRON` schedule fires → send a reminder
   with how long the alert has been unresolved.
4. When usage drops back below the threshold → send a resolved message and deactivate the alert.

## Running without Docker (optional, for development)

```bash
pip install -r requirements.txt
cp .env.example .env   # set HOST_MOUNT_PREFIX= (empty) and EXTRA_FILESYSTEM to local paths
python -m app.main
```
