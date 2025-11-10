# 预测平台（Django 版本）

基于 Django + Channels 的预测平台，实现预测模块注册、在线状态管理与 WebSocket 通信。

## 项目结构

```
Module_Server/
├── project_base/              # Django 项目（settings/urls/asgi/wsgi/routing）
├── platform_app/              # 业务应用（models/views/urls/consumers/admin）
│   └── management/commands/   # 自定义命令（expire_modules, fresh等）
├── resources/
│   ├── data/                  # 数据文件
│   ├── sql/                   # SQL 脚本
│   ├── templates/             # 模板文件
│   └── static/                # 静态文件
├── logs/                      # 日志目录
├── tests/                     # 测试文件
├── manage.py                  # Django 管理脚本
├── manage.sh                  # 部署管理脚本
├── requirements.txt           # Python 依赖
├── gunicorn.conf.py           # Gunicorn 配置文件
├── db.sqlite3                 # SQLite 数据库（Django 内置应用）
├── .env.example               # 环境变量配置示例
└── README.md                  # 项目说明文档
```

## 功能特点

- **模块注册**：通过接口注册模块信息，生成 `module_hash`
- **在线管理**：WebSocket 连接绑定会话并维护心跳时间
- **列表查询**：查询当前在线模块列表
- **一致的响应结构**：`{"code","message","result"}`

## 技术栈

- **Web 框架**：Django 5.2 + Channels 4（ASGI）
- **数据库**：MongoDB（业务数据）+ SQLite（Django 内置应用）
- **消息层**：Channels 内存实现（单进程部署）
- **ORM**：Django ORM（模型见 `platform_app/models.py`）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

在项目根目录创建 `.env` 文件，或以环境变量形式提供配置。

### 开发环境配置示例

```env
# Django 配置
DEBUG=True
SECRET_KEY=dev_secret_key_change_in_production
ALLOWED_HOSTS=*

# 服务器端口（仅用于开发环境的 runserver）
SERVER_PORT=10080

# MongoDB 配置
MONGODB_HOST=mongodb://localhost:27017
MONGODB_NAME=forecast_platform

# 邮件通知配置
NOTIFICATION_EMAIL=741617293@qq.com
EMAIL_API_URL=http://your-email-server:port/send
```

### 生产环境配置示例

```env
# Django 配置（生产环境必须设置）
DEBUG=False
SECRET_KEY=your-strong-secret-key-here
ALLOWED_HOSTS=example.com,www.example.com,api.example.com

# MongoDB 配置
MONGODB_HOST=mongodb://localhost:27017
MONGODB_NAME=forecast_platform

# 邮件通知配置
NOTIFICATION_EMAIL=your-email@example.com
EMAIL_API_URL=http://your-email-server:port/send

# 静态文件目录（可选，默认使用项目根目录下的 staticfiles）
STATIC_ROOT=/path/to/staticfiles

# 日志级别（可选，默认 INFO）
LOG_LEVEL=INFO
```

**重要说明**：
- 生产环境必须设置 `SECRET_KEY` 和 `ALLOWED_HOSTS`
- `SECRET_KEY` 生成方式：`python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- 邮件通知配置 `NOTIFICATION_EMAIL` 和 `EMAIL_API_URL` 必须设置，否则应用启动时会报错

## 数据库初始化

1) 启动 MongoDB（确保 MongoDB 服务正在运行）

2) 配置 MongoDB 连接（在 `.env` 文件中设置 `MONGODB_HOST` 和 `MONGODB_NAME`）

3) 生成并应用迁移

```bash
python manage.py makemigrations
python manage.py migrate
```

注意：SQLite 数据库（`db.sqlite3`）会自动创建，用于 Django 内置应用。

## 运行服务器

### 开发环境

```bash
python manage.py expire_modules   # 启动前可将所有模块置为离线
python manage.py runserver 0.0.0.0:10080
```

### 生产环境

1. **收集静态文件**

```bash
python manage.py collectstatic --noinput
```

2. **使用 Gunicorn 运行 ASGI 服务器**

```bash
gunicorn project_base.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:10080 --workers 1
```

**Gunicorn 配置说明**：
- `-k uvicorn.workers.UvicornWorker`：使用 Uvicorn worker 处理 ASGI 应用
- `--workers 1`：由于使用内存消息层，仅支持单进程部署
- `-b 0.0.0.0:10080`：绑定地址和端口

**推荐配置**：项目已包含 `gunicorn.conf.py` 配置文件，可直接使用：

```bash
gunicorn project_base.asgi:application -c gunicorn.conf.py
```

配置文件说明：
- `workers = 1`：单进程部署（内存消息层限制）
- `worker_class = "uvicorn.workers.UvicornWorker"`：使用 Uvicorn worker 处理 ASGI
- 日志文件：`logs/gunicorn_access.log` 和 `logs/gunicorn_error.log`
- 可根据实际部署环境修改 `bind`、`chdir` 等配置项

**使用部署管理脚本（推荐）**：

项目提供了 `manage.sh` 脚本，方便管理服务：

```bash
# 赋予执行权限
chmod +x manage.sh

# 查看帮助
./manage.sh help

# 完整部署（安装依赖、迁移、收集静态文件、启动服务）
./manage.sh deploy

# 启动服务
./manage.sh start

# 停止服务
./manage.sh stop

# 重启服务
./manage.sh restart

# 查看服务状态
./manage.sh status

# 查看日志
./manage.sh logs 100

# 实时查看日志
./manage.sh logs-follow
```

3. **使用进程管理器（推荐）**

使用 systemd、supervisor 或 PM2 管理进程，确保服务自动重启。

**注意事项**：
- 生产环境使用内存消息层，仅支持单进程部署（`--workers 1`）
- 如需多进程或多服务器部署，需要配置 Redis 作为消息层
- 建议使用 Nginx 作为反向代理处理静态文件和负载均衡

## 接口说明

- `GET /module/register`
  - 参数：`name`、`description`、`missionKind`、`dataRequirement`（JSON 字符串）
  - 返回：`{"code":"2000","message":"成功!","result":{"hash":"..."}}`

- `GET /module/online`
  - 返回：`{"code":"2000","message":"成功!","result":[...模块列表...]}`

## WebSocket 协议

- 连接地址：`ws://<host>:<port>/websocket?hash=<module_hash>`
- 心跳：
  - 客户端发送：`heartbeat`
  - 服务端响应：`heartbeat confirm`

## 客户端示例

```bash
cd _client
python register.py        # 注册模块，生成 module_hash 保存至 module_hash.txt
python client_connect.py  # 连接 WebSocket 并发送心跳
```

## 开发指南

- 模型：`platform_app/models.py`（业务模型使用 MongoDB）
- 视图与路由：`platform_app/views.py` / `platform_app/urls.py`
- WebSocket：`platform_app/consumers.py`，路由见 `project_base/routing.py`
- 配置：`project_base/settings.py`（ASGI、Channels、数据库）
- 调度器：`platform_app/scheduler.py`（定时任务管理）

## 维护命令

- 将所有模块置为离线：

```bash
python manage.py expire_modules
```

- 查看在线模块列表：

```bash
python manage.py test_list_scheduled_jobs
```

## 生产环境部署注意事项

1. **安全配置**
   - 必须设置强密码的 `SECRET_KEY`
   - 必须明确配置 `ALLOWED_HOSTS`
   - 关闭 `DEBUG` 模式
   - 配置 HTTPS（通过反向代理）

2. **性能优化**
   - 使用 Nginx 作为反向代理
   - 配置静态文件服务
   - 设置适当的日志级别
   - 监控服务器资源使用情况

3. **消息层限制**
   - 当前使用内存消息层，仅支持单进程部署
   - 如需多进程或多服务器部署，需要配置 Redis

4. **日志管理**
   - 日志文件位于 `logs/` 目录
   - 自动轮转，单个文件最大 10MB，保留 5 个备份
   - 可通过 `LOG_LEVEL` 环境变量控制日志级别