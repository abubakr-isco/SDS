# Deployment guide

The bot uses **long polling** for Telegram (outbound only). The one inbound service is the website
quote endpoint (`/api/quote`, port 8080 on localhost), which must be published over **HTTPS** through
a reverse proxy — see [Website form endpoint](#website-form-endpoint-https). PostgreSQL is never
exposed to the internet.

Choose **A (Docker Compose, recommended)** or **B (systemd + native PostgreSQL)**.

---

## Ubuntu VPS baseline (both options)

Ubuntu 22.04/24.04, 1 vCPU / 1 GB RAM is plenty.

```bash
sudo apt update && sudo apt upgrade -y
sudo adduser --disabled-password --gecos "" sds          # unprivileged service user
sudo ufw allow OpenSSH && sudo ufw enable                # 80/443 are opened later for the website endpoint
sudo timedatectl set-timezone America/Chicago            # optional: match TIMEZONE for log reading
```

Copy the project to `/opt/sds-telegram-bot` (git clone or `rsync -a --exclude .venv --exclude .env`),
then `sudo chown -R sds:sds /opt/sds-telegram-bot`.

Create the secrets file **on the server** (never copy your laptop's `.env` through chat/email):

```bash
cd /opt/sds-telegram-bot
sudo -u sds cp .env.example .env
sudo -u sds chmod 600 .env
sudo -u sds nano .env       # BOT_TOKEN, POSTGRES_PASSWORD / DATABASE_URL, ADMIN_TELEGRAM_IDS
```

Generate a strong database password with `openssl rand -base64 24 | tr -d '/+='`.

---

## A. Docker Compose (recommended)

```bash
# Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker

cd /opt/sds-telegram-bot
docker compose up -d --build        # starts PostgreSQL, runs migrations, starts the bot
docker compose logs -f bot          # look for "bot starting"
docker compose exec bot python -m app.cli check-config
```

`docker-compose.yml` sets `DATABASE_URL` for the bot itself (host `db`), publishes **no** ports, and
caps container logs at 5 × 10 MB. Company content (`config/company.toml`) is mounted read-only, so
edit it on the host and `docker compose restart bot`.

### Update / restart safely

```bash
cd /opt/sds-telegram-bot
./deploy/backup.sh                         # back up first
git pull                                   # or rsync the new release
docker compose up -d --build bot           # rebuilds, runs `alembic upgrade head`, restarts
docker compose logs --tail=50 bot
```

Restarts are safe: pending admin notifications are delivered on startup. Customers in the middle of
a quote form lose their unsaved answers (nothing partial is ever stored) and can start again.

---

## B. systemd + native PostgreSQL

```bash
sudo apt install -y python3.12 python3.12-venv postgresql
sudo -u postgres createuser sds_bot --pwprompt
sudo -u postgres createdb sds_bot --owner sds_bot
# PostgreSQL listens on localhost only by default — keep it that way.

cd /opt/sds-telegram-bot
sudo -u sds python3.12 -m venv .venv
sudo -u sds .venv/bin/pip install -r requirements.txt
# In .env: DATABASE_URL=postgresql+asyncpg://sds_bot:<password>@localhost:5432/sds_bot
sudo -u sds .venv/bin/alembic upgrade head
sudo -u sds .venv/bin/python -m app.cli check-config

sudo cp deploy/sds-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sds-bot
journalctl -u sds-bot -f
```

The unit runs migrations before each start, restarts on failure, and runs with systemd hardening.

### Update / restart safely

```bash
cd /opt/sds-telegram-bot
sudo USE_DOCKER=0 ./deploy/backup.sh
sudo -u sds git pull
sudo -u sds .venv/bin/pip install -r requirements.txt
sudo systemctl restart sds-bot          # ExecStartPre applies new migrations
journalctl -u sds-bot -n 50
```

---

## Website form endpoint (HTTPS)

The website (served over HTTPS) can only call an HTTPS endpoint. Point a subdomain such as
`bot.sdsuzinc.com` at the VPS, then use Caddy, which obtains and renews certificates automatically:

```bash
sudo ufw allow 80,443/tcp
sudo apt install -y caddy
sudo tee /etc/caddy/Caddyfile >/dev/null <<'CADDY'
bot.sdsuzinc.com {
    handle /api/quote {
        reverse_proxy 127.0.0.1:8080
    }
    handle /healthz {
        reverse_proxy 127.0.0.1:8080
    }
    respond 404
}
CADDY
sudo systemctl reload caddy
```

In `.env`: `WEBSITE_ALLOWED_ORIGINS=https://www.sdsuzinc.com,https://sdsuzinc.com` and
`WEB_TRUST_PROXY=true` (Caddy sets `X-Forwarded-For`). Restart the bot. Build the website with
`VITE_QUOTE_ENDPOINT=https://bot.sdsuzinc.com/api/quote`. Check: `curl https://bot.sdsuzinc.com/healthz`.

## Backups

`deploy/backup.sh` writes a compressed `pg_dump` to `/var/backups/sds-bot` (mode 600) and keeps
14 days.

```bash
sudo crontab -e
# Docker:   15 3 * * *  /opt/sds-telegram-bot/deploy/backup.sh >> /var/log/sds-bot-backup.log 2>&1
# systemd:  15 3 * * *  USE_DOCKER=0 /opt/sds-telegram-bot/deploy/backup.sh >> /var/log/sds-bot-backup.log 2>&1
```

Copy backups off the server (e.g. `rclone` to encrypted object storage) — a backup on the same disk
does not survive losing the VPS. Backups contain customer contact details; store them accordingly.

**Restore** (test this once before you need it):

```bash
# Docker
docker compose stop bot
docker compose exec -T db pg_restore -U sds_bot -d sds_bot --clean --if-exists < /var/backups/sds-bot/sds_bot-YYYYMMDD-HHMMSS.dump
docker compose start bot
# Native
sudo systemctl stop sds-bot
sudo -u postgres pg_restore -d sds_bot --clean --if-exists /var/backups/sds-bot/sds_bot-....dump
sudo systemctl start sds-bot
```

## Logs and log rotation

- Logs are single-line JSON on stdout with personal data redacted.
- Docker: rotated by the `json-file` options in `docker-compose.yml` (5 × 10 MB).
- systemd: journald. Cap its size with `SystemMaxUse=500M` in `/etc/systemd/journald.conf`.
- Backup log: `sudo cp deploy/logrotate-sds-bot /etc/logrotate.d/sds-bot`.

## Operations cheat sheet

```bash
python -m app.cli list-admins | add-admin <id> --name "..." | remove-admin <id>
python -m app.cli retry-notifications
python -m app.cli purge-expired --dry-run
python -m app.cli set-setting contact.office_hours "Mon–Fri, 7 AM – 6 PM CT"
```

Prefix with `docker compose exec bot` (Docker) or `sudo -u sds .venv/bin/` (systemd).

## Switching to webhooks (optional, later)

Only needed for high traffic or multiple instances. `app/bot.py` builds the Dispatcher independently
of the transport, so you can serve it with `aiogram.webhook.aiohttp_server.SimpleRequestHandler`
behind HTTPS (nginx/Caddy), call `bot.set_webhook(url, secret_token=...)`, and replace
`dp.start_polling` in `app/main.py`. With several instances, also switch FSM storage to Redis.
