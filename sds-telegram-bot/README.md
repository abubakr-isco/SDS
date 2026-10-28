# SDS Trucking — Telegram Bot

Customer-facing Telegram bot for **SDS** (*Moving America Forward.*): service information, a
10-step freight quote request wizard, request status lookup, contact details, and an
administrator interface for handling quote requests.

**Stack:** Python 3.12+ · aiogram 3 · PostgreSQL · SQLAlchemy 2 (async) · Alembic · Pydantic · pytest · Docker

> The bot never pretends to book, dispatch or track freight. Quote requests are recorded for the SDS
> team to review; shipment tracking replies honestly that it isn't available until a real tracking
> system is integrated (see [Tracking](#shipment-tracking)).

---

## Features

**Customers** (private chats only)

| | |
|---|---|
| `/start` | Welcome + main menu: 🚛 Our Services · 📋 Request a Freight Quote · 📍 Track a Shipment · ☎️ Contact SDS · ℹ️ About SDS |
| `/help`, `/cancel` | Help; cancel any conversation and return to the menu |
| `/quote`, `/track`, `/contact` | Shortcuts (also in Telegram's command menu) |
| Quote wizard | Name → company (or *Individual*) → email → phone (typed with country code, or *Share my phone number*) → pickup city/state/ZIP → delivery → pickup date → freight type → weight in lb (or *Not sure*) → details (or *Skip*) → review with **Submit / Edit / Cancel** → confirmation with a request ID such as `SDS-Q-2026-0001` |
| Status lookup | Customers can check **their own** quote requests by ID from "Track a Shipment" |

Every step has **Back** and **Cancel**; invalid answers get a specific explanation and the step is
repeated; abandoned forms expire after 60 minutes of inactivity.

**Administrators**

| | |
|---|---|
| `/admin` | Dashboard: New requests · Recent requests · Statistics · Retry notifications |
| `/requests [status]` | Recent requests, optionally filtered (`/requests new`) |
| `/request SDS-Q-2026-0001` | Request card: change status (optionally notifying the customer), add internal note, assign to an admin, message the customer, view history |
| `/stats` | Counts by status, last 7/30 days, customers |

Statuses: New · Under Review · Awaiting Customer Information · Quoted · Accepted · In Progress ·
Completed · Cancelled. Every change is written to `quote_request_events`.

---

## Website form → Telegram

The SDS website's quote form posts to this bot's built-in HTTP endpoint, `POST /api/quote`
(served by the same process as the bot, port `WEB_PORT`, default 8080). Each website request:

1. is validated with the same rules as the bot wizard (field errors are shown next to the form fields),
2. is saved as a quote request with source **🌐 Website form** and its own ID (`SDS-Q-2026-0007`),
3. is sent to every active administrator in Telegram, with name, phone, email, route and freight,
4. is managed like any other request (`/request …`, status, notes, assignment). Website customers are
   not on Telegram, so "notify/message customer" is replaced by a reminder to call or email them.

The website never sees the bot token. Protection: browser origins limited to `WEBSITE_ALLOWED_ORIGINS`,
5 saved requests per hour per IP (`WEBSITE_QUOTES_PER_HOUR_PER_IP`), honeypot field, 16 KB body limit,
idempotency key (a resubmitted form never creates a second request).

Website side: set `VITE_QUOTE_ENDPOINT` (e.g. `https://bot.sdsuzinc.com/api/quote`) when building the
site. Bot side: set `WEBSITE_ALLOWED_ORIGINS=https://www.sdsuzinc.com,https://sdsuzinc.com`.
Locally: `VITE_QUOTE_ENDPOINT=http://localhost:8080/api/quote` (site `.env.local`) and
`WEBSITE_ALLOWED_ORIGINS=http://localhost:5180`.

## Quick start (macOS, local)

Requirements: Python 3.12+, PostgreSQL 14+ (`brew install postgresql@16 && brew services start postgresql@16`).

```bash
cd sds-telegram-bot
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

createuser sds_bot --pwprompt          # choose a password
createdb sds_bot --owner sds_bot

cp .env.example .env                   # then edit: BOT_TOKEN, DATABASE_URL, ADMIN_TELEGRAM_IDS
alembic upgrade head                   # create the schema
python -m app.cli check-config         # sanity-check settings and content
python -m app                          # start the bot (long polling); Ctrl+C to stop
```

For local work set `ENVIRONMENT=development` to see setup warnings for content that isn't configured
yet (they are hidden from customers in production).

## Create the bot in BotFather

1. In Telegram, open **@BotFather** → `/newbot`.
2. Name: **SDS Trucking**. Username: try **SDS_TruckBot** (must end in `bot`; if taken, choose another).
3. BotFather replies with the **token**. Treat it like a password: put it only in `.env` (or your
   server's secret store). Never commit it, paste it in chats or screenshots. If it leaks, use
   `/revoke` in BotFather and update `.env`.
4. Optional polish in BotFather: `/setdescription`, `/setabouttext`, `/setuserpic` (SDS logo).
   The command menu is set automatically when the bot starts.
5. `/setjoingroups` → **Disable** (the bot is for private chats and ignores groups).

## Administrator setup

1. Each admin sends **/myid** to the bot (or messages @userinfobot) to get their numeric Telegram user ID.
2. Put the IDs in `.env`: `ADMIN_TELEGRAM_IDS=123456789,987654321`. They are created/re-activated
   in the `administrators` table at startup.
3. Admins must press **Start** in the bot once — Telegram doesn't let bots message users who haven't.
4. Manage admins from the server:

```bash
python -m app.cli add-admin 123456789 --name "Dispatch — Maria"
python -m app.cli remove-admin 123456789     # deactivates immediately; history is kept
python -m app.cli list-admins
```

(With Docker: `docker compose exec bot python -m app.cli list-admins`.)
Removing an admin who is still listed in `ADMIN_TELEGRAM_IDS` re-activates them on the next restart —
remove them from `.env` too.

## Company content

Everything customers read about SDS lives in **`config/company.toml`** — contact details, About
text, services and freight types. Only confirmed information belongs there.

- **Services are proposed categories and ship disabled.** Set `enabled = true` only for services SDS
  management confirms. Disabled services are hidden from customers (and can't be quoted via forged
  buttons).
- Empty contact fields are hidden from customers. Contact fields can also be overridden at runtime
  without a redeploy: `python -m app.cli set-setting contact.website https://www.example.com`
  (keys: `contact.phone`, `contact.email`, `contact.website`, `contact.office_hours`, `contact.office_address`).
- Restart the bot after editing the TOML file.

## Configuration reference

All settings come from environment variables / `.env` (see `.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `BOT_TOKEN` | — (required) | Token from @BotFather |
| `DATABASE_URL` | — (required) | `postgresql+asyncpg://user:pass@host:5432/db` |
| `ADMIN_TELEGRAM_IDS` | empty | Comma-separated admin user IDs |
| `ENVIRONMENT` | `production` | `development` shows setup warnings |
| `TIMEZONE` | `America/Chicago` | Company timezone for dates and "today" |
| `LOG_LEVEL` / `LOG_FORMAT` | `INFO` / `json` | Logging |
| `DATA_RETENTION_DAYS` | `730` | Delete completed/cancelled requests (and customers with none left) after N days; `0` disables |
| `QUOTE_SESSION_TIMEOUT_MINUTES` | `60` | Abandoned quote forms expire |
| `QUOTE_SUBMISSIONS_PER_HOUR` | `3` | Per-customer submission limit |
| `TRACKING_LOOKUPS_PER_10_MINUTES` | `10` | Per-customer lookup limit (prevents ID enumeration) |
| `NOTIFICATION_RETRY_INTERVAL_SECONDS` / `NOTIFICATION_MAX_ATTEMPTS` | `120` / `10` | Admin notification retries |
| `WEB_ENABLED` / `WEB_HOST` / `WEB_PORT` | `true` / `127.0.0.1` / `8080` | Website form endpoint |
| `WEBSITE_ALLOWED_ORIGINS` | empty | Website origins allowed to submit (empty = none in production) |
| `WEB_TRUST_PROXY` | `false` | Use `X-Forwarded-For` for rate limiting (only behind your proxy) |
| `WEBSITE_QUOTES_PER_HOUR_PER_IP` | `5` | Website submissions per IP per hour |
| `TRACKING_PROVIDER` | `none` | Shipment tracking backend |

---

## How it works

```
app/
├── main.py              entry point: settings, DB wait, admin sync, polling, background loops
├── cli.py               admin/ops commands (python -m app.cli ...)
├── bot.py               Bot + Dispatcher factory (routers, middlewares) — polling or webhook
├── config.py            Pydantic settings from env
├── company.py           config/company.toml loader
├── context.py           AppContext injected into handlers as `ctx`
├── texts.py             all customer/admin copy (user input always HTML-escaped)
├── database/            models.py, session.py, repositories/
├── handlers/            start, services, quote, tracking, contact, admin, errors, fallback
├── keyboards/           inline/reply keyboards + callback data
├── middlewares/         throttling (flood control), quote session timeout
├── services/            quotes, notifications, admin, tracking, contact, retention
├── states/              FSM state groups
└── utils/               validation, logging (redaction), formatting, rate limiting
```

**Quote submission** (`services/quotes.py`) is one database transaction that upserts the customer,
allocates the public ID, inserts the request and its `created` event, and inserts one
`admin_notifications` row per active admin (transactional outbox). The customer sees the
confirmation **only after the commit succeeds**; on any failure they are told plainly that nothing
was submitted, their answers are kept, and they can tap Submit again.

- **Request IDs** — `SDS-Q-<year>-<n>` from a per-year counter row incremented with
  `UPDATE … RETURNING` (row-locked, so concurrent submissions can't collide), backed by a UNIQUE
  constraint.
- **Duplicate submissions** — the review screen carries a random submission key stored with the
  request under a UNIQUE constraint; double taps and retries return the already-saved request.
- **Admin notifications** — sent after the commit, separately from the database work. Each
  notification is claimed atomically before sending, so the immediate send, the retry loop and the
  dashboard's *Retry notifications* never deliver the same one twice. Failures are recorded
  (`forbidden`, `network`, …) and retried every 2 minutes up to 10 attempts. (If the process dies
  between Telegram accepting a message and the database recording it, that one notification can be
  repeated after 5 minutes — at-least-once delivery.)

### Database schema

`customers`, `quote_requests`, `quote_request_events`, `administrators`, `company_settings`, plus
`quote_request_counters` (ID sequence) and `admin_notifications` (outbox). Foreign keys with
cascading deletes for customer data, indexes on lookup columns, CHECK constraints on status/event
columns. Schema changes go through Alembic (`migrations/versions/`); tables are never created at
runtime.

### Shipment tracking

`services/tracking.py` defines the `TrackingProvider` interface. With `TRACKING_PROVIDER=none`
(the only option today) the bot answers:
*"Shipment tracking is not currently available through this bot. Please contact SDS for an update."*

To integrate a TMS/carrier API, implement `lookup(reference, telegram_user_id)` so that it:
queries the authorized source; returns `NOT_FOUND` when this user isn't allowed to see the shipment
(never revealing that it exists); and returns only the latest **confirmed** status and its timestamp.
Register it in `build_tracking_provider()`. `tests/test_tracking.py` contains a fake provider that
shows the expected behavior.

### Security & privacy

- Secrets only from environment; `.env` is git- and docker-ignored; `.env.example` holds placeholders.
- Admin authorization on **every** admin update (filter) **and** inside each service transaction;
  revoked admins lose access immediately; forged callback buttons are rejected.
- Customers can only look up their own requests; lookups are rate-limited.
- All SQL through SQLAlchemy with bound parameters (`hide_parameters=True` keeps values out of errors).
- Input validated and length-limited; output HTML-escaped.
- Logs are JSON with emails, phone numbers, tokens, DB passwords and SQL parameters redacted; handlers
  never log message contents. Users never see stack traces or database errors.
- Flood control (20 actions / 10 s per user), hourly quote limit, lookup limit.
- Data minimization: only the fields the quote needs; retention purge runs daily
  (`python -m app.cli purge-expired --dry-run` to preview).
- In-progress quote forms live in memory (`MemoryStorage`) and are lost on restart — nothing
  half-finished is ever written to the database. For multi-instance deployments switch to
  aiogram's `RedisStorage` in `bot.create_dispatcher`.

---

## Tests

```bash
pytest                    # SQLite, isolated temp database per test — no setup needed
ruff check . && ruff format --check .

# Same suite against PostgreSQL (dedicated, disposable database — tables are dropped/recreated):
createdb sds_bot_test
TEST_DATABASE_URL=postgresql+asyncpg://localhost/sds_bot_test pytest
```

The PostgreSQL run adds true concurrency tests (parallel submissions get unique IDs; parallel
double-taps create one request) and a migration test (upgrade → no drift from the models →
downgrade → upgrade). Telegram is fully mocked (`tests/harness.py`): updates are fed to the real
dispatcher and outgoing API calls are recorded; no network or real credentials are used.

## Deployment

See **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — Docker Compose and systemd on Ubuntu, backups,
log rotation, updates, restore, and switching to webhooks.
