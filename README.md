# 组件调度平台

基于 Django + Channels 的组件调度平台，实现组件注册、在线状态管理与 WebSocket 通信。

## 项目结构

```
Module_Server/
├── project_base/                      # Django 项目基础配置
│   ├── __init__.py                   # Python 包初始化
│   ├── settings.py                   # Django 配置文件
│   ├── urls.py                       # 根 URL 路由配置
│   ├── asgi.py                       # ASGI 应用入口（支持 WebSocket）
│   ├── wsgi.py                       # WSGI 应用入口（传统 HTTP）
│   ├── routing.py                    # WebSocket 路由配置
│   └── db_router.py                  # 数据库路由器（MongoDB/SQLite 路由）
├── platform_app/                     # 业务应用模块
│   ├── __init__.py                   # Python 包初始化
│   ├── models.py                     # 数据模型
│   ├── views.py                      # HTTP 视图函数（REST API）
│   ├── urls.py                       # 业务路由配置
│   ├── consumers.py                  # WebSocket 消费者（ModuleConsumer）
│   ├── admin.py                      # Django Admin 后台配置
│   ├── apps.py                       # 应用配置
│   ├── scheduler.py                  # 定时任务调度器（APScheduler）
│   ├── solver.py                     # 数据需求解析器（解析 DataRequirement）
│   ├── email.py                      # 邮件通知模块（失败通知模板）
│   ├── utils.py                      # 工具函数（时间处理、邮件发送等）
│   ├── migrations/                   # 数据库迁移文件
│   └── management/commands/         # Django 自定义管理命令
├── resources/                        # 资源文件目录
├── tests/                            # 测试文件目录
├── logs/                             # 日志文件目录
├── manage.py                         # Django 管理脚本（启动、迁移等）
├── manage.sh                         # 部署管理脚本（启动/停止/重启服务）
├── test_server.sh                    # 测试服务器启动脚本
├── requirements.txt                  # Python 依赖包列表
├── gunicorn.conf.py                  # Gunicorn 生产环境配置
└── README.md                         # 项目说明文档
```

## 功能特点

- **组件管理**：WebSocket 连接绑定会话并维护心跳时间，支持组件热切换
- **工作流调度**：创建工作流，配置定时执行任务（支持多个 crontab 表达式）
- **消息通信**：通过 WebSocket 向模块发送执行命令，接收模块执行结果
- **邮件通知**：模块执行失败时自动发送邮件通知
- **定时任务管理**：查看和管理调度器中的定时任务

## 技术栈

- **Web 框架**：Django 5.2 + Channels 4（ASGI）
- **数据库**：MySQL（Django 内置应用和 APScheduler）+ MongoDB（业务数据）
- **消息层**：基于 Channels 的 WebSocket 负责与组件进行通信
- **定时任务**：APScheduler（django-apscheduler）
- **ORM**：Django ORM + django-mongodb-backend（模型见 `platform_app/models.py`）

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

# MySQL 配置（Django 内置应用和 APScheduler）
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=module_server

# MongoDB 配置（业务数据）
MONGODB_HOST=mongodb://localhost:27017
MONGODB_NAME=forecast_platform

# 邮件通知配置
NOTIFICATION_EMAIL=*********
EMAIL_API_URL=http://your-email-server:port/send
```

### 生产环境配置示例

```env
# Django 配置（生产环境必须设置）
DEBUG=False
SECRET_KEY=your-strong-secret-key-here
ALLOWED_HOSTS=example.com,www.example.com,api.example.com

# MySQL 配置（Django 内置应用和 APScheduler）
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_strong_password
MYSQL_DB=module_server

# MongoDB 配置（业务数据）
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
- MySQL 和 MongoDB 服务必须提前启动并配置正确

## 依赖服务

### MySQL 数据库

- 项目使用 MySQL 作为默认数据库，用于 Django 内置应用（如 admin、sessions）和 APScheduler 定时任务存储。
- 使用 Docker 启动 MySQL 示例：

```bash
docker pull mysql:8.0
docker run -d \
  --name mysql8 \
  -e MYSQL_ROOT_PASSWORD=your_password \
  -e MYSQL_DATABASE=module_server \
  -p 3306:3306 \
  -v mysql_data:/var/lib/mysql \
  mysql:8.0
```

- 如果使用本地 MySQL 服务，需要提前创建数据库（默认数据库名：`module_server`）：

```sql
CREATE DATABASE module_server CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### MongoDB 数据库

- 项目使用 MongoDB 存储业务数据（模块、工作流等）。
- 需要提前启动 MongoDB 服务。
- 使用 Docker 启动 MongoDB 示例：

```bash
docker pull mongo:latest
docker run -d \
  --name module_server_mongo \
  -p 27017:27017 \
  -v mongo_data:/data/db \
  mongo:latest
```

### Channels 消息层

- 项目使用 `InMemoryChannelLayer` 作为 Channels 消息层。
- 当前实现通过直接调用 consumer 实例方法进行通信，不依赖 channel_layer 的跨进程功能。
- **注意**：当前配置仅支持单进程部署，如需多进程或多服务器部署，需要配置 Redis Channel Layer。

## 数据库初始化

1. **启动 MySQL 和 MongoDB 服务**

   - 确保 MySQL 服务正在运行
   - 确保 MongoDB 服务正在运行

2. **创建 MySQL 数据库**

   ```sql
   CREATE DATABASE module_server CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

3. **配置数据库连接**

   在 `.env` 文件中设置：
   - MySQL 配置：`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DB`
   - MongoDB 配置：`MONGODB_HOST`、`MONGODB_NAME`

4. **生成并应用迁移**

   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

   注意：迁移会同时应用到 MySQL（Django 内置应用）和 MongoDB（业务应用）。

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
gunicorn project_base.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:10080 --workers 2
```

**Gunicorn 配置说明**：
- `-k uvicorn.workers.UvicornWorker`：使用 Uvicorn worker 处理 ASGI 应用
- `--workers 1`：当前使用 InMemoryChannelLayer，仅支持单 worker 部署
- `-b 0.0.0.0:10080`：绑定地址和端口

**推荐配置**：项目已包含 `gunicorn.conf.py` 配置文件，可直接使用：

```bash
gunicorn project_base.asgi:application -c gunicorn.conf.py
```

配置文件说明：
- `workers = 1`：当前配置仅支持单 worker（InMemoryChannelLayer 限制）
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

- **注意事项**：
- 当前使用 InMemoryChannelLayer，仅支持单进程部署
- 如需多进程或多服务器部署，需要配置 Redis Channel Layer
- 建议使用 Nginx 作为反向代理处理静态文件和负载均衡
- 确保 MySQL 和 MongoDB 服务正常运行

## 接口说明

### 模块相关接口

- `GET /module/register`
  - 参数：`name`（模块名称）、`description`（模块描述）、`input_data`（输入数据需求，JSON 字符串）、`output_data`（输出数据需求，JSON 字符串）、`modelHash`（模型哈希值）
  - 返回：`{"code":"2000","message":"成功!","result":{"hash":"...","module_id":1}}`

- `GET /module/online`
  - 返回：`{"code":"2000","message":"成功!","result":[...在线模块列表...]}`

- `POST /module/send_message`
  - 参数：`module_hash`（模块哈希值）、`message`（消息内容）
  - 返回：`{"code":"2000","message":"成功!","result":{"message":"..."}}`

### 工作流相关接口

- `POST /workflow/create`
  - 请求体（JSON）：
    ```json
    {
      "name": "工作流名称",
      "description": "工作流描述",
      "enable": true,
      "execute_cron_list": ["*/10 10 * * 1-5", "*/10 14 * * 1-5"],
      "execute_shift_time": -30,
      "execute_shift_unit": "s",
      "execute_modules": [
        {
          "module_hash": "模块hash值",
          "args": {"stock_list": [...], "fund_list": [...]}
        }
      ]
    }
    ```
  - 返回：`{"code":"2000","message":"成功!","result":{"id":"...","workflow_id":1,"name":"..."}}`

- `POST /workflow/<workflow_id>/execute`
  - 路径参数：`workflow_id`（工作流ID）
  - 返回：`{"code":"2000","message":"成功!","result":{"workflow_id":1,"workflow_name":"...","message":"工作流执行已启动"}}`

- `GET /workflow/list`
  - 返回：`{"code":"2000","message":"成功!","result":[...工作流列表...]}`

### 调度器相关接口

- `GET /scheduler/jobs`
  - 返回：`{"code":"2000","message":"成功!","result":[...定时任务列表...]}`

- `POST /scheduler/reload`
  - 返回：`{"code":"2000","message":"成功!","result":{"removed_count":0,"current_count":1,"enabled_workflows":[...],"message":"..."}}`

## WebSocket 协议

- 连接地址：`ws://<host>:<port>/websocket?hash=<module_hash>`
- 连接监控：使用 WebSocket 协议自带的 ping/pong 机制进行连接监控，无需客户端发送心跳消息
- 执行命令（服务端 → 客户端）：
  - 服务端发送（JSON）：
    ```json
    {
      "type": "execute",
      "meta": {
        "execution_time": "2024-01-01T10:00:00",
        "workflow_id": "工作流ID",
        "workflow_name": "工作流名称"
      },
      "args": {"stock_list": [...], "fund_list": [...]}
    }
    ```
- 执行结果（客户端 → 服务端）：
  - 客户端发送（JSON）：
    ```json
    {
      "type": "result",
      "status": "success" | "failure",
      "workflow_id": "工作流ID",
      "workflow_name": "工作流名称",
      "module_name": "模块名称",
      "error": "错误信息（失败时）",
      "message": "结果消息"
    }
    ```
  - 服务端响应：`receive result`

## 客户端示例

```bash
cd _client
python register.py        # 注册模块，生成 module_hash 保存至 module_hash.txt
python client_connect.py  # 连接 WebSocket 并发送心跳
```

## 开发指南

- **模型**：`platform_app/models.py`
  - `WorkModule`：工作模块表（模块注册、在线状态管理）
  - `WorkFlow`：工作流表（定时任务配置）
  - `DataRequirement`：数据需求配置（嵌入模型）
- **视图与路由**：`platform_app/views.py` / `platform_app/urls.py`
- **WebSocket**：`platform_app/consumers.py`，路由见 `project_base/routing.py`
- **配置**：`project_base/settings.py`（ASGI、Channels、数据库、日志）
- **调度器**：`platform_app/scheduler.py`（定时任务管理，基于 APScheduler）
- **邮件通知**：`platform_app/email.py`（模块执行失败通知）

## 维护命令

- 将所有模块置为离线：

```bash
python manage.py expire_modules
```

- 查看在线模块列表：

```bash
python manage.py test_list_scheduled_jobs
```

- 其他自定义命令（位于 `platform_app/management/commands/`）：
  - `add.py`：添加数据
  - `expire.py`：过期模块处理
  - `fresh.py`：刷新数据
  - `test.py`：测试命令

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
   - 当前使用 InMemoryChannelLayer，仅支持单进程部署
   - 代码通过直接调用 consumer 实例方法进行通信，不依赖 channel_layer 的跨进程功能
   - 如需多进程或多服务器部署，需要配置 Redis Channel Layer

4. **调度器管理**
   - 调度器在应用启动时自动初始化，加载所有启用状态的工作流
   - 可通过 `/scheduler/reload` 接口重新加载工作流任务
   - 调度器会自动清理旧的任务执行记录（每周一凌晨）

5. **日志管理**
   - 日志文件位于 `logs/` 目录
   - 自动轮转，单个文件最大 10MB，保留 5 个备份
   - 可通过 `LOG_LEVEL` 环境变量控制日志级别