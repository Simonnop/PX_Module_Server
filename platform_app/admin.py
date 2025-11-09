from django.contrib import admin
from .models import WorkModule, WorkFlow

# 管理后台配置（类似 Spring Actuator 的可视化数据管理能力）


@admin.register(WorkModule)
class WorkModuleAdmin(admin.ModelAdmin):
    list_display = ("id", "module_id", "name", "alive", "priority", "module_hash")
    search_fields = ("name", "module_hash", "module_id")
    list_filter = ("alive",)
    readonly_fields = ("module_hash", "module_id", "last_alive_time", "last_login_time")
    fieldsets = (
        ("基本信息", {
            "fields": ("module_id", "name", "description", "priority")
        }),
        ("状态信息", {
            "fields": ("module_hash", "alive", "session_id", "last_alive_time", "last_login_time")
        }),
        ("执行信息", {
            "fields": ("last_execution_time",)
        }),
        ("数据需求", {
            "fields": ("input_data", "output_data"),
            "classes": ("collapse",)
        }),
    )


@admin.register(WorkFlow)
class WorkFlowAdmin(admin.ModelAdmin):
    list_display = ("id", "workflow_id", "name", "description", "enable", "execute_shift_time", "execute_shift_unit")
    search_fields = ("name", "workflow_id")
    list_filter = ("enable", "execute_shift_unit")
    fieldsets = (
        ("基本信息", {
            "fields": ("workflow_id", "name", "description", "enable")
        }),
        ("执行配置", {
            "fields": ("execute_cron_list", "execute_shift_time", "execute_shift_unit", "execute_modules")
        }),
    )


