# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LLM 安全事件推送系统 - A multi-source data aggregation system for LLM security events. It crawls security events from multiple platforms, classifies and filters them intelligently, and pushes them to subscribed users via a browser extension.

## Common Commands

### Backend (FastAPI)

```bash
cd backend

# Setup
python -m venv venv
source venv/Scripts/activate  # Windows
pip install -r requirements.txt

# Database migrations
alembic upgrade head
alembic revision --autogenerate -m "description"

# Seed database
python -m app.core.seed

# Development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
# or
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Extension (Chrome - Vue 3 + CRXJS)

```bash
cd extension
npm install
npm run dev      # Development with hot reload (port 5173)
npm run build    # Production build to dist/
```

Load unpacked extension from `extension/dist/` in Chrome.

### Admin Panel (Vue 3 + Element Plus)

```bash
cd admin
npm install
npm run dev      # Development at http://localhost:3000
npm run build    # Production build
```

Note: Admin panel proxies `/api/*` requests to `http://127.0.0.1:8000` in development.

### Quick Start (Windows)

```bash
dev-start.bat    # Starts backend, extension dev server, and admin panel
dev-stop.bat     # Stops all services
```

## Architecture

### Three-Tier Structure

1. **Backend** (`backend/`) - FastAPI REST API + WebSocket
2. **Extension** (`extension/`) - Chrome extension for end users
3. **Admin** (`admin/`) - Admin panel for system management

### Backend Architecture

```
backend/app/
├── api/
│   ├── v1/           # User-facing REST API endpoints
│   ├── admin/        # Admin-only endpoints
│   ├── deps.py       # Auth dependencies (get_current_user, get_current_admin)
│   └── websocket.py  # WebSocket event push
├── core/
│   ├── config.py     # Settings from .env
│   ├── database.py   # SQLAlchemy engine & session
│   ├── security.py   # JWT + bcrypt password hashing
│   └── exceptions.py # Custom exception handling
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic validation schemas
├── services/         # Business logic layer
│   ├── llm_service.py     # LLM API integration
│   ├── model_matcher.py   # AI model matching logic
│   ├── keyword_filter.py  # RSS keyword filtering (shared by crawler & admin API)
│   ├── nvd_collector.py   # NVD data collector
│   ├── aiid_collector.py  # AIID data collector
│   └── aivd_collector.py  # AIVD data collector
└── tasks/            # APScheduler scheduled jobs
    ├── scheduler.py      # Job configuration
    ├── rss_crawler.py    # RSS feed crawling (30 min)
    ├── historical_sync.py # Historical data sync (daily 3am)
    ├── event_pusher.py   # WebSocket push (1 min)
    ├── llm_rating.py     # LLM auto-rating (5 min)
    └── data_cleanup.py   # Cleanup old data (daily 4am)
```

### Authentication Flow

- JWT tokens with access/refresh pattern
- Access token: 30 min expiry (configurable)
- Refresh token: 7 days expiry
- Token type stored in payload (`"type": "access"` or `"type": "refresh"`)
- Use `get_current_user` dependency for protected endpoints
- Use `get_current_admin` for admin-only endpoints
- Use `get_optional_user` for endpoints that work with or without authentication

### Extension Architecture

Chrome Manifest V3 extension with:
- **Popup** (`src/popup/`) - Quick actions popup
- **Side Panel** (`src/sidepanel/`) - Main UI in browser side panel
- **Background** (`src/background/`) - Service worker for notifications
- **Shared** (`src/shared/`) - Common utilities and API client

### Database

- MySQL 8.0+ with SQLAlchemy ORM
- Key tables: users, models, categories, rss_sources, historical_events, rss_events, event_models, user_preferences, push_logs, system_configs, operation_logs

### External Data Sources

- **Historical**: NVD, AIID, AIVD (synced daily)
- **Real-time**: RSS feeds (crawled every 30 min)

## API Endpoints

- User API: `/api/v1/*` - auth, events, preferences, categories, models
- Admin API: `/api/admin/*` - config, rating, rss_sources, models, sync, logs
- WebSocket: `/ws/events?token=<jwt>` - real-time event push
- Health check: `/health`
- Docs: `/docs` (Swagger), `/redoc` (ReDoc)

## LLM Integration

- Uses OpenAI SDK compatible API (supports Tencent Cloud, SiliconFlow, etc.)
- Config in `.env`: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`
- Default base URL: `https://api.lkeap.cloud.tencent.com/coding/v3`
- Default model: `glm-5`
- Features: auto-classification, auto-rating (both toggleable via system config)

## NVD API Configuration

- NVD (National Vulnerability Database) API Key is optional but recommended
- Config: `NVD_API_KEY` in `.env` file
- **With API Key**: 0.6 second request interval (recommended for production)
- **Without API Key**: 6 second request interval (rate limited by NVD)
- Get your free API Key at: https://nvd.nist.gov/developers/request-an-api-key

## Development Notes

### RSS Data Keyword Filtering

- RSS events are keyword-filtered immediately upon database insertion
- Filter configuration stored in `system_configs` table: `filter_keywords` (JSON array), `keyword_filter_enabled` (bool)
- Admin UI shows only keyword-filtered RSS events by default (use `show_filtered=true` param to see all)
- NVD/AIID/AIVD data bypasses keyword filtering (they are AI security platforms by nature)
- Shared filtering logic in `services/keyword_filter.py` used by both crawler and admin API

### Extension Service Worker (Manifest V3)

- Service workers in Chrome Manifest V3 have no `window` object - use `setInterval` directly, not `window.setInterval`
- Dev mode uses HTTP imports from `localhost:5173`, which may cause service worker registration failures
- **Prefer production builds (`npm run build`) for testing the extension** - dev mode may have issues with service worker loading
- `host_permissions` in manifest must include `localhost:5173` for dev mode

### Password Hashing

Uses `bcrypt` directly (not passlib) due to compatibility issues. See `app/core/security.py`.

### Element Plus Icons

When importing icons from `@element-plus/icons-vue`, use correct names:
- `HomeFilled` not `Home`
- Reference: https://element-plus.org/en-US/component/icon.html

### Adding New API Endpoints

1. Create model in `models/`
2. Create schema in `schemas/`
3. Create service methods in `services/`
4. Create router in `api/v1/` or `api/admin/`
5. Register router in `api/v1/__init__.py` or `api/admin/__init__.py`

### CVSS Vulnerability Scoring

The system uses the `cvss` Python library for vulnerability severity scoring. NVD events include CVSS metrics (score, vector, severity). See `backend/app/services/nvd_collector.py` for collection and `backend/app/models/historical_event.py` for storage.

### Utility Scripts

- `backend/scripts/import_rss_sources.py` - Bulk import RSS sources from a file
- Root-level `requirements.txt` is a duplicate of `backend/requirements.txt` (minus `cvss`); use the backend one as authoritative.

### No Automated Tests or CI/CD

This project has no test framework or CI/CD pipeline. The `test/` directory contains manual test documentation only. If adding tests, set up `pytest` with `conftest.py` in `backend/`.

### Adding Scheduled Tasks

1. Create task file in `tasks/`
2. Add job function and trigger in `tasks/scheduler.py`

### SQLAlchemy Enum (CRITICAL)

**This has caused multiple bugs. Always follow these rules when using SQLAlchemy Enum:**

SQLAlchemy `Enum` columns default to using enum **member names** (e.g., `MEDIUM`) as database values, NOT enum **values** (e.g., `"medium"`). This causes `LookupError` when code passes string values.

**Correct usage:**
```python
class SeverityLevel(str, enum.Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# MUST use values_callable to store enum values (not member names)
severity = Column(
    Enum(SeverityLevel, values_callable=lambda obj: [e.value for e in obj]),
    comment="安全等级"
)
```

**Why this matters:**
- Without `values_callable`, SQLAlchemy stores `"MEDIUM"` in database
- But code everywhere passes `"medium"` (the enum value)
- Result: `LookupError: 'medium' is not among the defined enum values`

**When adding/modifying enum columns:**
1. Always add `values_callable=lambda obj: [e.value for e in obj]` to Column definition
2. Create migration to modify MySQL ENUM definition (use `ALTER TABLE ... MODIFY COLUMN`)
3. If data exists, also migrate existing values to lowercase
4. Check ALL enum columns in the project - models and schemas must use consistent values

**Current enum columns using this pattern:**
- `historical_events.severity` and `historical_events.severity_source`
- `rss_events.severity` and `rss_events.severity_source`

## Communication Preference

- Claude should use **English** for internal thinking and reasoning
- Claude should use **Chinese (中文)** when providing prompts, summaries, or any output directed to the user
