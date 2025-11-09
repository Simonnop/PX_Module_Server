"""
ASGI config for project_base.

说明：
- ASGI 是 Django 的异步服务器接口，支持 WebSocket。
- 通过 Channels 的 `ProtocolTypeRouter` 将 HTTP 与 WebSocket 分流。
"""
import os
import asyncio
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# 指定 Django 配置模块
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "project_base.settings")

# 必须先初始化 Django 应用
django_asgi_app = get_asgi_application()

# 延后导入以避免 settings 未加载，获取 WebSocket 路由表
try:
    from project_base.routing import websocket_urlpatterns
except Exception:
    websocket_urlpatterns = []

# 在 Django 应用初始化后，再导入和初始化调度器
try:
    from platform_app.scheduler import initialize_scheduler
    initialize_scheduler()
except Exception as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"调度器初始化失败: {e}")

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})


