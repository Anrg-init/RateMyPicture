# RateMyPic 📸

RateMyPic is a full-featured, production-ready Telegram bot built with **Python 3.12**, **Aiogram 3**, and **Async SQLAlchemy (PostgreSQL + asyncpg)**. It allows users to upload photos, receive ratings (1–5 stars) and comments, express emoji reactions, and engage in private 1-on-1 direct messaging (DMs) with local and global discovery matching.

---

## 🌟 Core Features

- **Age & Terms Gatekeeping**: Strictly 18+ onboarding with multilingual Terms of Service confirmation.
- **3-Tier Rating Waterfall Algorithm**:
  1. *Tier 1 (Local Preferred)*: Matches preferred target gender in the user's home country.
  2. *Tier 2 (Global Preferred)*: Matches preferred target gender worldwide if local posts are exhausted.
  3. *Tier 3 (Global Fallback)*: Shows all remaining active posts to guarantee an uninterrupted feed.
- **5-Photo Gatekeeper**: Rater incentive loop requiring users to rate at least 5 photos before unlocking post publishing.
- **Dynamic Emoji Reactions**: Interactive reaction buttons (🔥, ❤️, 😍, 👏, 💯) with live count toggling.
- **Private Direct Messaging (DM)**: Users can send a private message to photo owners with instant Telegram notification and inline one-click replies.
- **Internationalization (i18n)**: Fully localized in 5 languages:
  - 🇬🇧 English (`en`)
  - 🇷🇺 Russian (`ru`)
  - 🇪🇸 Spanish (`es`)
  - 🇧🇷 Portuguese (`pt`)
  - 🇮🇩 Indonesian (`id`)
- **Admin Dashboard (`/stats`)**: Secure analytics view for admins displaying active users, posts, ratings, comments, DMs, and demographic breakdowns.
- **Retention & Milestone Alerts**: Automated background notifications for user milestones and inactive re-engagement.

---

## 🗂️ Project Structure & Navigation

```text
ratemypic/
├── alembic.ini                   # Alembic database migration configuration
├── pyproject.toml                # Project metadata, scripts, and dependencies (uv)
├── uv.lock                       # Deterministic dependency lockfile
├── .env.example                  # Environment configuration template
├── README.md                     # Project overview and navigation guide
│
├── src/ratemypic/                # Core application package
│   ├── main.py                   # CLI entrypoint; initializes logging and event loop
│   ├── bot.py                    # Bot polling startup, error handlers, and commands registration
│   ├── database.py               # Async SQLAlchemy engine, session management, and connection pooling
│   ├── models.py                 # Declarative SQLAlchemy ORM models and database constraints
│   ├── services.py               # Business logic, database queries, and matching algorithms
│   ├── keyboards.py              # Telegram inline keyboard generators with localized labels
│   ├── notifications.py          # Background notification engine and retention reminder loop
│   ├── i18n.py                   # Internationalization helper (JSON catalog loader)
│   ├── logging_config.py         # Production log formatting configuration
│   ├── terms.py                  # Terms of service copy across all supported languages
│   │
│   ├── handlers/                 # Modular Aiogram routers
│   │   ├── __init__.py           # Master router aggregating all feature routers
│   │   ├── registration.py       # Onboarding flow: language, age, terms, gender, location
│   │   ├── menu.py               # Main menu, profile view, and quick navigation
│   │   ├── rating.py             # Feed viewing, 1-5 star ratings, comments, emoji reactions
│   │   ├── posts.py              # Multi-photo upload flow, caption handling, and photo count checks
│   │   ├── edit.py               # Profile editing, post management, and account deletion
│   │   ├── dm.py                 # Direct messaging compose flow, inbox, and reply routing
│   │   └── admin.py              # Admin metrics dashboard (/stats command)
│   │
│   └── i18n/                     # Translation catalog JSON files
│       ├── en.json
│       ├── es.json
│       ├── id.json
│       ├── pt.json
│       └── ru.json
│
├── migrations/                   # Alembic migrations directory
│   ├── env.py                    # Migration execution environment
│   └── versions/                 # Versioned migration scripts (0001 to 0011)
│
├── scripts/                      # Developer tools, seed scripts, and demo assets (gitignored)
│   └── seed_clean_demo.py        # Demo dataset generator with verified profiles
│
└── tests/                        # Comprehensive automated unittest test suite
    ├── test_admin.py             # Admin handler and permissions tests
    ├── test_database.py          # Database session and connection tests
    ├── test_dm.py                # Direct messaging workflow tests
    ├── test_edit.py              # Profile and post editing tests
    ├── test_i18n.py              # Translation strings and key completeness tests
    ├── test_keyboards.py         # Inline keyboard markup tests
    ├── test_menu.py              # Main menu and profile navigation tests
    ├── test_notifications.py     # Notification triggers and milestone tests
    ├── test_post_upload.py       # Post upload and 5-photo gatekeeper tests
    ├── test_rating.py            # Rating feed and reaction interaction tests
    ├── test_registration.py      # Onboarding and registration validation tests
    └── test_services.py          # Database services and query helper tests
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.12+
- PostgreSQL 15+
- [uv](https://github.com/astral-sh/uv) (fast Python package manager)

### 2. Environment Setup
Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Telegram Bot API token obtained from [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | PostgreSQL connection URL (e.g. `postgresql+asyncpg://user:pass@localhost:5432/ratemypic`) |
| `ADMIN_ID` | Numeric Telegram user ID of the administrator for `/stats` access |
| `LOG_LEVEL` | *(Optional)* Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |
| `DB_POOL_SIZE` | *(Optional)* Connection pool size (default: `15`) |
| `DB_MAX_OVERFLOW` | *(Optional)* Maximum overflow connections (default: `20`) |

### 3. Database Migrations
Apply all schema migrations:

```bash
uv run alembic upgrade head
```

### 4. Running the Bot
Start the bot using the configured script entrypoint:

```bash
uv run ratemypic
```

Or run directly via python:

```bash
uv run python -m ratemypic.main
```

---

## 🧪 Testing

The repository uses Python's standard `unittest` framework with full coverage across all handlers, services, and models.

Run the entire test suite:

```bash
uv run python -m unittest discover -s tests
```

---

## 🤖 Telegram Bot Commands

| Command | Description |
|---|---|
| `/start` | Launches onboarding for new users or opens the main menu for registered users |
| `/menu` | Opens the main menu navigation |
| `/profile` | Displays your current profile, stats, photos, and settings |
| `/language` | Opens language selection menu |
| `/edit` | Opens profile and post editing, target preferences, or account deletion |
| `/cancel` | Aborts the current action and returns to the main menu |
| `/terms` | Displays the Terms of Service |
| `/stats` | *(Admin only)* Displays system-wide real-time metrics and analytics |

---

## 🛡️ Architecture & Design Principles

1. **Telegram File IDs**: Photo bytes are never saved on disk or in the database; only Telegram `file_id` references are stored, ensuring minimal storage footprint and high performance.
2. **Session Scoping**: All database operations use `session_scope()` context manager with automatic rollback on error and proper connection release.
3. **Cascading Safety**: User account deletion safely cleans up their personal records while preserving anonymized metrics and aggregate statistics for platform integrity.
