"""WebSocket 路由配置

- 将 `/websocket` 路径映射到 `ModuleConsumer`
- 等价于 HTTP 路由里的 `urls.py`，但这里只处理 WS
"""
from django.urls import path
from platform_app import consumers

websocket_urlpatterns = [
    path("websocket", consumers.ModuleConsumer.as_asgi()),
]


