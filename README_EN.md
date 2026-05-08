# LLM Security Event Push System

English | [中文](README.md)

A multi-source data aggregation system for LLM security events. It automatically crawls the latest LLM security incidents from multiple platforms, intelligently classifies and filters them, and pushes them to subscribed users via a browser extension — helping users stay up-to-date with the latest developments in LLM security.

## Features

### User Features
- Follow specific AI models (choose from a preset list)
- Follow specific security event categories
- Receive real-time security event push notifications (browser extension)
- View historical and recommended security events
- Unread event count

### System Features
- Scheduled automatic security event collection
- Multi-source data aggregation and storage
- Intelligent event classification (toggleable by admin)
- Severity assessment (LLM-powered auto-rating)
- Keyword filtering (for RSS data sources)
- WebSocket real-time push

### Admin Features
- Toggle LLM classification/rating
- Manually trigger rating and classification
- RSS source management (CRUD, validation, manual crawl)
- Preset model list management
- Event management (view, delete, batch delete)
- Data synchronization (NVD / AIID / AIVD)
- System configuration management

## Tech Stack

| Module | Technology |
|--------|------------|
| Backend Framework | FastAPI |
| Database | MySQL 8.0+ |
| ORM | SQLAlchemy 2.0+ |
| Database Migration | Alembic |
| Scheduler | APScheduler |
| Crawler | BeautifulSoup + Requests + Feedparser |
| LLM Integration | OpenAI SDK (compatible API) |
| Browser Extension | Vue 3 + Vite + CRXJS (Manifest V3) |
| Admin Panel | Vue 3 + Element Plus |
| Authentication | JWT (access/refresh token) |

## Project Structure

```
.
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API routes
│   │   │   ├── v1/            # User API
│   │   │   ├── admin/         # Admin API
│   │   │   ├── deps.py        # Auth dependencies
│   │   │   └── websocket.py   # WebSocket push
│   │   ├── core/              # Core modules
│   │   │   ├── config.py      # Configuration
│   │   │   ├── database.py    # Database connection
│   │   │   ├── security.py    # JWT + password hashing
│   │   │   └── exceptions.py  # Custom exceptions
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic validation schemas
│   │   ├── services/          # Business logic
│   │   │   ├── nvd_collector.py    # NVD data collector
│   │   │   ├── aiid_collector.py   # AIID data collector
│   │   │   ├── aivd_collector.py   # AIVD data collector
│   │   │   ├── llm_service.py      # LLM API integration
│   │   │   ├── model_matcher.py    # AI model matching
│   │   │   ├── keyword_filter.py   # RSS keyword filtering
│   │   │   └── html_cleaner.py     # HTML content cleaning
│   │   └── tasks/             # Scheduled tasks
│   │       ├── scheduler.py       # Task scheduler
│   │       ├── rss_crawler.py     # RSS crawler
│   │       ├── historical_sync.py # Historical data sync
│   │       ├── event_pusher.py    # Event push
│   │       ├── llm_rating.py      # LLM rating/classification
│   │       └── data_cleanup.py    # Data cleanup
│   ├── alembic/               # Database migrations
│   ├── .env.example           # Environment variable template
│   └── requirements.txt       # Python dependencies
│
├── extension/                  # Chrome extension (Manifest V3)
│   ├── src/
│   │   ├── popup/             # Popup page
│   │   ├── sidepanel/         # Side panel main UI
│   │   │   ├── views/         # Page components
│   │   │   └── components/    # Shared components
│   │   ├── background/        # Service Worker
│   │   └── shared/            # Shared modules
│   │       ├── api.ts         # API client
│   │       ├── websocket.ts   # WebSocket client
│   │       └── stores.ts      # Pinia state management
│   ├── package.json
│   └── vite.config.ts
│
└── admin/                      # Admin panel
    ├── src/
    │   ├── views/             # Page components
    │   ├── api/               # API client
    │   └── router/            # Router configuration
    ├── package.json
    └── vite.config.ts
```

## Data Sources

### Historical Data (Initial Baseline)

| Platform | Description |
|----------|-------------|
| NVD | National Vulnerability Database |
| AIID | AI Incident Database |
| AIVD | AI Vulnerability Database |

### Real-time Data (RSS Feeds)

| Platform | Description |
|----------|-------------|
| WeChat Official Accounts | Via RSShub |
| Security Blogs | User-customizable |
| Official Advisories | OpenAI, Anthropic, Google, etc. |
| GitHub Releases | Monitor LLM security project updates |

## Installation

### Prerequisites

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/JohnnyChanZY/llm-security-extension.git
cd llm-security-extension
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Create database
mysql -u root -p -e "CREATE DATABASE llm_security CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# Run database migrations
alembic upgrade head

# Seed initial data
python -m app.core.seed
```

Copy `backend/.env.example` to `backend/.env` and fill in the configuration:

```env
# Database
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/llm_security

# NVD API Key (optional, 0.6s interval with key vs 6s without)
# Apply at: https://nvd.nist.gov/developers/request-an-api-key
NVD_API_KEY=

# AIID API Key (optional)
AIID_API_KEY=

# LLM API Configuration (supports Tencent Cloud, SiliconFlow, etc. — OpenAI-compatible)
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.lkeap.cloud.tencent.com/coding/v3
LLM_MODEL=glm-5

# JWT Configuration
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Admin Account
ADMIN_EMAIL=admin
ADMIN_PASSWORD=password

# CORS Allowed Origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000
```

Start the backend:

```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

API documentation: `http://localhost:8000/docs` (Swagger) / `http://localhost:8000/redoc` (ReDoc)

### 3. Browser Extension

```bash
cd extension

# Install dependencies
npm install

# Development mode (hot reload)
npm run dev

# Production build
npm run build
```

In Chrome:
1. Navigate to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked"
4. Select the `extension/dist/` directory

### 4. Admin Panel

```bash
cd admin

# Install dependencies
npm install

# Development mode
npm run dev

# Production build
npm run build
```

Visit http://localhost:3000

## API Endpoints

### User API (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | /auth/register | User registration |
| POST | /auth/login | User login |
| POST | /auth/logout | User logout |
| POST | /auth/refresh | Refresh token |
| GET | /auth/profile | Get user info |
| PUT | /auth/profile | Update user info |
| PUT | /auth/password | Change password |
| GET | /events | Event list |
| GET | /events/unread-count | Unread event count |
| GET | /events/recommend | Recommended events |
| GET | /events/subscribed | Subscribed events |
| GET | /events/{id} | Event detail |
| GET | /categories | Category list |
| GET | /models | Model list |
| GET | /preferences | User preferences |
| POST | /preferences | Add preference |
| PUT | /preferences/{id} | Update preference |
| DELETE | /preferences/{id} | Delete preference |

### Admin API (`/api/admin`)

| Method | Path | Description |
|--------|------|-------------|
| GET | /configs | Get system configs |
| PUT | /configs/{key} | Update config |
| GET | /configs/llm | Get LLM config |
| GET | /events | Event list |
| DELETE | /events/rss/{id} | Delete RSS event |
| DELETE | /events/historical/{id} | Delete historical event |
| POST | /events/batch-delete | Batch delete events |
| GET | /events/stats | Event statistics |
| GET | /models | Model list |
| POST | /models | Add model |
| PUT | /models/{id} | Update model |
| DELETE | /models/{id} | Delete model |
| POST | /rating/trigger | Trigger rating |
| POST | /rating/process | Process unrated events |
| POST | /rating/check-security | Security check |
| POST | /rating/rate | Single rating |
| POST | /rating/classify | Single classification |
| POST | /rating/rate-and-classify | Rate + classify |
| POST | /rating/batch-operations | Batch operations |
| GET | /rating/status | Rating status |
| GET | /rating/config | Rating config |
| PUT | /rating/config | Update rating config |
| POST | /rating/stop | Stop rating task |
| GET | /rss-sources | RSS source list |
| POST | /rss-sources | Add RSS source |
| PUT | /rss-sources/{id} | Update RSS source |
| DELETE | /rss-sources/{id} | Delete RSS source |
| POST | /rss-sources/{id}/validate | Validate RSS source |
| POST | /rss-sources/actions/crawl-all | Crawl all RSS |
| POST | /rss-sources/{id}/crawl | Crawl single RSS |
| POST | /sync/nvd | Sync NVD data |
| POST | /sync/aiid | Sync AIID data |
| POST | /sync/aivd | Sync AIVD data |

### WebSocket (`/ws/events`)

Connection authentication:
```
ws://host/ws/events?token=<jwt_token>
```

Message format:
```json
{
  "type": "new_event",
  "data": {
    "id": 123,
    "title": "Event title",
    "severity": "high"
  }
}
```

## Scheduled Tasks

| Task | Interval | Description |
|------|----------|-------------|
| RSS Crawl | 30 min | Crawl RSS data sources |
| Historical Sync | Daily 03:00 | Sync NVD/AIID/AIVD |
| Event Push | 1 min | WebSocket push |
| LLM Auto-Process | 5 min | Auto-filter, judge, rate, and classify |
| Data Cleanup | Daily 04:00 | Clean up expired logs |

## Security Event Categories

| Code | Name | Description |
|------|------|-------------|
| prompt_injection | Prompt Injection | Manipulating LLM behavior |
| data_leakage | Data Leakage | Leaking training data |
| jailbreak | Jailbreak | Bypassing safety restrictions |
| adversarial_attack | Adversarial Attack | Adversarial sample deception |
| model_theft | Model Theft | Copying model parameters |
| privacy_violation | Privacy Violation | Leaking personal information |
| misinformation | Misinformation | Generating misleading content |

## Default Account

| Role | Email | Password |
|------|-------|----------|
| Admin | admin | password |

> Please change the default password in production

## Development Guide

### Adding New API Endpoints

1. Create model (`models/`)
2. Create schema (`schemas/`)
3. Create service methods (`services/`)
4. Create route (`api/v1/` or `api/admin/`)
5. Register route (`api/v1/__init__.py` or `api/admin/__init__.py`)

### Adding Scheduled Tasks

1. Create task file (`tasks/`)
2. Register task in `tasks/scheduler.py`

### Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## License

[MIT License](LICENSE)
