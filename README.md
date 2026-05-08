# LLM安全事件推送系统

[English](README_EN.md) | 中文

基于多源数据聚合的大语言模型安全事件推送系统，通过爬虫技术从多个安全平台自动采集最新的 LLM 安全事件，经过智能分类与筛选后，主动推送给订阅用户，帮助用户及时了解 LLM 安全领域的最新动态。

## 功能特性

### 用户功能
- 关注特定 AI 模型（从预设列表中选择）
- 关注特定安全事件类别
- 接收最新安全事件推送（浏览器插件通知）
- 查看历史安全事件与推荐事件
- 未读事件计数

### 系统功能
- 定时自动获取安全事件
- 数据源聚合与存储
- 安全事件智能分类（可通过管理员开关控制）
- 安全等级评估（LLM 自动评级）
- 关键词过滤（RSS 数据源）
- WebSocket 实时推送

### 管理员功能
- LLM 分类/评级开关
- 手动触发评级与分类
- RSS 数据源管理（增删改查、验证、手动抓取）
- 预设模型列表管理
- 事件管理（查看、删除、批量删除）
- 数据同步（NVD / AIID / AIVD）
- 系统配置管理

## 技术栈

| 模块 | 技术 |
|------|------|
| 后端框架 | FastAPI |
| 数据库 | MySQL 8.0+ |
| ORM | SQLAlchemy 2.0+ |
| 数据库迁移 | Alembic |
| 定时任务 | APScheduler |
| 爬虫 | BeautifulSoup + Requests + Feedparser |
| LLM 调用 | OpenAI SDK（兼容 API） |
| 浏览器插件 | Vue 3 + Vite + CRXJS (Manifest V3) |
| 管理后台 | Vue 3 + Element Plus |
| 认证 | JWT (access/refresh token) |

## 项目结构

```
.
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/               # API 路由
│   │   │   ├── v1/            # 用户 API
│   │   │   ├── admin/         # 管理员 API
│   │   │   ├── deps.py        # 认证依赖
│   │   │   └── websocket.py   # WebSocket 推送
│   │   ├── core/              # 核心模块
│   │   │   ├── config.py      # 配置管理
│   │   │   ├── database.py    # 数据库连接
│   │   │   ├── security.py    # JWT + 密码哈希
│   │   │   └── exceptions.py  # 自定义异常
│   │   ├── models/            # SQLAlchemy ORM 模型
│   │   ├── schemas/           # Pydantic 验证模式
│   │   ├── services/          # 业务逻辑层
│   │   │   ├── nvd_collector.py    # NVD 数据采集
│   │   │   ├── aiid_collector.py   # AIID 数据采集
│   │   │   ├── aivd_collector.py   # AIVD 数据采集
│   │   │   ├── llm_service.py      # LLM API 集成
│   │   │   ├── model_matcher.py    # AI 模型匹配
│   │   │   ├── keyword_filter.py   # RSS 关键词过滤
│   │   │   └── html_cleaner.py     # HTML 内容清洗
│   │   └── tasks/             # 定时任务
│   │       ├── scheduler.py       # 任务调度器
│   │       ├── rss_crawler.py     # RSS 爬虫
│   │       ├── historical_sync.py # 历史数据同步
│   │       ├── event_pusher.py    # 事件推送
│   │       ├── llm_rating.py      # LLM 评级/分类
│   │       └── data_cleanup.py    # 数据清理
│   ├── alembic/               # 数据库迁移
│   ├── .env.example           # 环境变量模板
│   └── requirements.txt       # Python 依赖
│
├── extension/                  # Chrome 浏览器插件 (Manifest V3)
│   ├── src/
│   │   ├── popup/             # 弹窗页面
│   │   ├── sidepanel/         # 侧边栏主界面
│   │   │   ├── views/         # 页面组件
│   │   │   └── components/    # 公共组件
│   │   ├── background/        # Service Worker
│   │   └── shared/            # 共享模块
│   │       ├── api.ts         # API 客户端
│   │       ├── websocket.ts   # WebSocket 客户端
│   │       └── stores.ts      # Pinia 状态管理
│   ├── package.json
│   └── vite.config.ts
│
└── admin/                      # 管理后台
    ├── src/
    │   ├── views/             # 页面组件
    │   ├── api/               # API 客户端
    │   └── router/            # 路由配置
    ├── package.json
    └── vite.config.ts
```

## 数据源

### 历史数据（初始化基础数据）

| 平台 | 说明 |
|------|------|
| NVD | National Vulnerability Database |
| AIID | AI Incident Database |
| AIVD | AI Vulnerability Database |

### 实时数据（RSS 订阅）

| 平台 | 说明 |
|------|------|
| 微信公众号 | 通过 RSShub 获取推文 |
| 安全博客 | 用户自定义添加 |
| 官方公告 | OpenAI、Anthropic、Google 等 |
| GitHub Releases | 监控 LLM 安全相关项目更新 |

## 安装部署

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0+
- Git

### 1. 克隆项目

```bash
git clone https://github.com/JohnnyChanZY/llm-security-extension.git
cd llm-security-extension
```

### 2. 后端配置

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt

# 创建数据库
mysql -u root -p -e "CREATE DATABASE llm_security CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 数据库迁移
alembic upgrade head

# 初始化数据
python -m app.core.seed
```

复制 `backend/.env.example` 为 `backend/.env` 并填写配置：

```env
# 数据库
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/llm_security

# NVD API Key（可选，有 Key 时请求间隔 0.6 秒，无 Key 时 6 秒）
# 申请地址: https://nvd.nist.gov/developers/request-an-api-key
NVD_API_KEY=

# AIID API Key（可选）
AIID_API_KEY=

# LLM API 配置（支持腾讯云、硅基流动等 OpenAI 兼容 API）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.lkeap.cloud.tencent.com/coding/v3
LLM_MODEL=glm-5

# JWT 配置
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# 管理员账号
ADMIN_EMAIL=admin
ADMIN_PASSWORD=password

# CORS 允许的来源（逗号分隔）
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,http://localhost:8000
```

启动后端：

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

API 文档：`http://localhost:8000/docs`（Swagger）/ `http://localhost:8000/redoc`（ReDoc）

### 3. 浏览器插件

```bash
cd extension

# 安装依赖
npm install

# 开发模式（热更新）
npm run dev

# 生产构建
npm run build
```

在 Chrome 浏览器中：
1. 打开 `chrome://extensions/`
2. 开启「开发者模式」
3. 点击「加载已解压的扩展程序」
4. 选择 `extension/dist/` 目录

### 4. 管理后台

```bash
cd admin

# 安装依赖
npm install

# 开发模式
npm run dev

# 生产构建
npm run build
```

访问 http://localhost:3000

## API 接口

### 用户 API (`/api/v1`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /auth/register | 用户注册 |
| POST | /auth/login | 用户登录 |
| POST | /auth/logout | 用户登出 |
| POST | /auth/refresh | 刷新 Token |
| GET | /auth/profile | 获取用户信息 |
| PUT | /auth/profile | 更新用户信息 |
| PUT | /auth/password | 修改密码 |
| GET | /events | 事件列表 |
| GET | /events/unread-count | 未读事件计数 |
| GET | /events/recommend | 推荐事件 |
| GET | /events/subscribed | 订阅事件 |
| GET | /events/{id} | 事件详情 |
| GET | /categories | 分类列表 |
| GET | /models | 模型列表 |
| GET | /preferences | 用户偏好列表 |
| POST | /preferences | 添加偏好 |
| PUT | /preferences/{id} | 更新偏好 |
| DELETE | /preferences/{id} | 删除偏好 |

### 管理员 API (`/api/admin`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /configs | 获取系统配置 |
| PUT | /configs/{key} | 更新配置项 |
| GET | /configs/llm | 获取 LLM 配置 |
| GET | /events | 事件列表 |
| DELETE | /events/rss/{id} | 删除 RSS 事件 |
| DELETE | /events/historical/{id} | 删除历史事件 |
| POST | /events/batch-delete | 批量删除事件 |
| GET | /events/stats | 事件统计 |
| GET | /models | 模型列表 |
| POST | /models | 新增模型 |
| PUT | /models/{id} | 更新模型 |
| DELETE | /models/{id} | 删除模型 |
| POST | /rating/trigger | 触发评级 |
| POST | /rating/process | 处理待评级事件 |
| POST | /rating/check-security | 安全检查 |
| POST | /rating/rate | 单次评级 |
| POST | /rating/classify | 单次分类 |
| POST | /rating/rate-and-classify | 评级+分类 |
| POST | /rating/batch-operations | 批量操作 |
| GET | /rating/status | 评级状态 |
| GET | /rating/config | 评级配置 |
| PUT | /rating/config | 更新评级配置 |
| POST | /rating/stop | 停止评级任务 |
| GET | /rss-sources | RSS 源列表 |
| POST | /rss-sources | 新增 RSS 源 |
| PUT | /rss-sources/{id} | 更新 RSS 源 |
| DELETE | /rss-sources/{id} | 删除 RSS 源 |
| POST | /rss-sources/{id}/validate | 验证 RSS 源 |
| POST | /rss-sources/actions/crawl-all | 抓取所有 RSS |
| POST | /rss-sources/{id}/crawl | 抓取单个 RSS |
| POST | /sync/nvd | 同步 NVD 数据 |
| POST | /sync/aiid | 同步 AIID 数据 |
| POST | /sync/aivd | 同步 AIVD 数据 |

### WebSocket (`/ws/events`)

连接认证：
```
ws://host/ws/events?token=<jwt_token>
```

消息类型：
```json
{
  "type": "new_event",
  "data": {
    "id": 123,
    "title": "事件标题",
    "severity": "high"
  }
}
```

## 定时任务

| 任务 | 间隔 | 说明 |
|------|------|------|
| RSS 爬取 | 30 分钟 | 爬取 RSS 数据源 |
| 历史数据同步 | 每天 03:00 | 同步 NVD/AIID/AIVD |
| 事件推送 | 1 分钟 | WebSocket 推送 |
| LLM 自动处理 | 5 分钟 | 自动筛选、判断、评级、分类 |
| 数据清理 | 每天 04:00 | 清理过期日志 |

## 安全事件分类

| 分类代码 | 名称 | 说明 |
|---------|------|------|
| prompt_injection | 提示注入 | 操纵 LLM 行为 |
| data_leakage | 数据泄露 | 泄露训练数据 |
| jailbreak | 越狱攻击 | 绕过安全限制 |
| adversarial_attack | 对抗攻击 | 对抗样本欺骗 |
| model_theft | 模型窃取 | 复制模型参数 |
| privacy_violation | 隐私侵犯 | 泄露个人信息 |
| misinformation | 虚假信息 | 生成误导信息 |

## 默认账号

| 角色 | 邮箱 | 密码 |
|------|------|------|
| 管理员 | admin | password |

> 请在生产环境中修改默认密码

## 开发说明

### 添加新的 API 端点

1. 创建模型 (`models/`)
2. 创建 Schema (`schemas/`)
3. 创建服务方法 (`services/`)
4. 创建路由 (`api/v1/` 或 `api/admin/`)
5. 注册路由 (`api/v1/__init__.py` 或 `api/admin/__init__.py`)

### 添加定时任务

1. 创建任务文件 (`tasks/`)
2. 在 `tasks/scheduler.py` 中注册任务

### 数据库迁移

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## 许可证

[MIT License](LICENSE)
