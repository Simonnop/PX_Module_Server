from django.urls import path
from . import views

# 说明：路由到视图函数（类比 Spring 的 @RequestMapping）

urlpatterns = [
    path("module/register", views.module_register),
    path("module/online", views.show_online_modules),
    path("module/send_message", views.send_message),
    path("workflow/create", views.workflow_create),
    path("workflow/execute", views.workflow_execute),
    path("workflow/list", views.list_workflows),
    path("scheduler/jobs", views.list_scheduled_jobs),
    path("scheduler/reload", views.reload_scheduler_jobs),
]


