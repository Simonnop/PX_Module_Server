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
├── db.sqlite3                        # SQLite 数据库文件（Django 内置应用）
└── README.md                         # 项目说明文档
```

## 功能特点

- **模块注册**：通过接口注册模块信息，生成 `module_hash` 和 `module_id`
- **在线管理**：WebSocket 连接绑定会话并维护心跳时间
- **列表查询**：查询当前在线模块列表
- **工作流调度**：创建工作流，配置定时执行任务（支持多个 crontab 表达式）
- **消息通信**：通过 WebSocket 向模块发送执行命令，接收模块执行结果
- **邮件通知**：模块执行失败时自动发送邮件通知
- **定时任务管理**：查看和管理调度器中的定时任务
- **一致的响应结构**：`{"code","message","result"}`

## 技术栈

- **Web 框架**：Django 5.2 + Channels 4（ASGI）
- **数据库**：MongoDB（业务数据）+ SQLite（Django 内置应用）
- **消息层**：Channels 内存实现（单进程部署）
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

# MongoDB 配置
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
- 心跳：
  - 客户端发送：`heartbeat`
  - 服务端响应：`heartbeat confirm`
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
   - 当前使用内存消息层，仅支持单进程部署
   - 如需多进程或多服务器部署，需要配置 Redis 作为消息层

4. **调度器管理**
   - 调度器在应用启动时自动初始化，加载所有启用状态的工作流
   - 可通过 `/scheduler/reload` 接口重新加载工作流任务
   - 调度器会自动清理旧的任务执行记录（每周一凌晨）

5. **日志管理**
   - 日志文件位于 `logs/` 目录
   - 自动轮转，单个文件最大 10MB，保留 5 个备份
   - 可通过 `LOG_LEVEL` 环境变量控制日志级别