"""Django settings for project_base

注释说明（面向 Spring Boot 用户）：
- 这里相当于 `application.yml`/`application.properties` 的集中配置。
- `INSTALLED_APPS` 可类比为启用的模块/Starter 列表。
- `MIDDLEWARE` 可类比为过滤器链（FilterChain）。
- `urls.py` 是路由配置，类比 `@RequestMapping` 的全局映射。
- `ASGI_APPLICATION` 开启异步能力（Channels），支持 WebSocket。
"""
from pathlib import Path
import os
from urllib.parse import urlsplit
from decouple import config, Csv


# 项目根目录（常用于拼接静态/模板等目录）
BASE_DIR = Path(__file__).resolve().parent.parent

# 安全性配置（从 .env 文件读取）
# 先读取 DEBUG 状态，用于判断是否为生产环境
DEBUG = config("DEBUG", default=False, cast=bool)

# SECRET_KEY 配置：生产环境必须设置，开发环境可以使用默认值
if DEBUG:
    # 开发环境：允许使用默认值
    SECRET_KEY = config("SECRET_KEY", default="dev_secret_key_change_in_production")
else:
    # 生产环境：必须设置 SECRET_KEY
    SECRET_KEY = config("SECRET_KEY", default=None)
    if not SECRET_KEY:
        raise ValueError("生产环境必须设置 SECRET_KEY 环境变量，不能为空")

# 生产环境必须明确指定 ALLOWED_HOSTS
if DEBUG:
    ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="*", cast=Csv())
else:
    ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="", cast=Csv())
    if not ALLOWED_HOSTS:
        raise ValueError("生产环境必须设置 ALLOWED_HOSTS 环境变量")

# 已安装应用（Django 内置 + 第三方 + 业务应用）
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "django_apscheduler",
    "platform_app",
]

# 中间件（请求进入/响应返回时依次经过）
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# 根路由配置模块
ROOT_URLCONF = "project_base.urls"

# 模板引擎（如需渲染 HTML 模板，可在这里配置模板目录/上下文处理器）
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(BASE_DIR / "resources" / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# WSGI（同步）与 ASGI（异步）入口。Channels 依赖 ASGI 支持 WebSocket。
WSGI_APPLICATION = "project_base.wsgi.application"
ASGI_APPLICATION = "project_base.asgi.application"

# Channels 的消息层（使用内存实现，适用于单进程部署）
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}

# Django 数据库配置（等价于 Spring 的 DataSource 配置）
# 将默认库切到 SQLite（供 Django 内置应用使用），
# 另起一个名为 "mongo" 的库供业务模型（platform_app）使用
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(BASE_DIR / "db.sqlite3"),
    },
    "mongo": {
        "ENGINE": "django_mongodb_backend",
        "HOST": config("MONGODB_HOST", default=""),
        "NAME": config("MONGODB_NAME", default="forecast_platform"),
    },
}

# 路由器：将 platform_app 的读/写/迁移路由到 "mongo"
DATABASE_ROUTERS = [
    "project_base.db_router.MongoRouter",
]

# 国际化/时区（默认关闭 `USE_TZ`，与数据库保持本地时间）
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = False

# 静态资源
STATIC_URL = "/static/"
STATICFILES_DIRS = [str(BASE_DIR / "resources" / "static")]
# 生产环境静态文件收集目录
STATIC_ROOT = config("STATIC_ROOT", default=str(BASE_DIR / "staticfiles"))

# 开发服务器端口（仅用于 `runserver`）
SERVER_PORT = config("SERVER_PORT", default=10080, cast=int)

# 日志配置
LOGGING_DIR = BASE_DIR / "logs"
LOGGING_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGGING_DIR / "django.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGGING_DIR / "django_error.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        "platform_app_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGGING_DIR / "platform_app.log"),
            "maxBytes": 1024 * 1024 * 10,  # 10MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file", "error_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "platform_app": {
            "handlers": ["console", "platform_app_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# 生产环境安全配置
if not DEBUG:
    # HTTPS 相关配置（如果使用反向代理如 Nginx，这些可能不需要）
    # SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=False, cast=bool)
    # SESSION_COOKIE_SECURE = config("SESSION_COOKIE_SECURE", default=True, cast=bool)
    # CSRF_COOKIE_SECURE = config("CSRF_COOKIE_SECURE", default=True, cast=bool)
    
    # 安全头部配置
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    
    # 日志级别在生产环境可以通过环境变量控制
    log_level = config("LOG_LEVEL", default="INFO")
    LOGGING["root"]["level"] = log_level
    for logger_name in LOGGING["loggers"]:
        LOGGING["loggers"][logger_name]["level"] = log_level


