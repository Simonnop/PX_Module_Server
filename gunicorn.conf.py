# Gunicorn 配置文件
# 用于生产环境部署 Django ASGI 应用

# 绑定地址和端口
bind = "0.0.0.0:10080"

# Worker 配置
# 注意：由于使用内存消息层，仅支持单进程部署
workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000

# 超时设置
timeout = 30
keepalive = 2

# 请求限制（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 50

# 日志配置
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"

# 进程名称
proc_name = "module_server"

# 用户和组（生产环境建议设置，需要 root 权限）
# user = "www-data"
# group = "www-data"

# 工作目录（需要根据实际部署路径修改）
# chdir = "/path/to/Module_Server"

# 环境变量
raw_env = [
    "DJANGO_SETTINGS_MODULE=project_base.settings",
]

# 预加载应用（提高性能，但可能导致内存增加）
preload_app = False

# 守护进程模式（如果使用 systemd/supervisor 管理，设为 False）
daemon = False

# PID 文件
pidfile = "/tmp/gunicorn.pid"

