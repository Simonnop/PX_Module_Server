"""
WSGI config for project_base.

说明：
- WSGI 是 Django 的同步服务器接口（如 gunicorn, uWSGI）。
- 若仅使用 HTTP 而非 WebSocket，可只通过 WSGI 部署。
"""
import os
from django.core.wsgi import get_wsgi_application

# 指定 Django 配置模块
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_base.settings")

application = get_wsgi_application()


