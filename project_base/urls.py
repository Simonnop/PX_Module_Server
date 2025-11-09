"""项目根路由

说明（类比 Spring Boot）：
- 相当于全局的 `@RequestMapping` 映射入口。
- 将 `/` 下的 API 转发给业务应用 `platform_app`。
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("platform_app.urls")),
]


