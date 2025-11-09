from django.db import models
from django_mongodb_backend.models import EmbeddedModel
from django_mongodb_backend.fields import EmbeddedModelArrayField, ArrayField, ObjectIdAutoField

# 说明（类比 Spring Data JPA）：
# - 这里定义 ORM 实体，映射到数据库表。
# - 字段类型与约束由 `models.*Field` 指定，`Meta.db_table` 指定表名。

class DataRequirement(EmbeddedModel):
    """数据需求配置"""
    id = ObjectIdAutoField(primary_key=True)
    table_kind = models.CharField(max_length=10)  # 表类型
    table_name = models.CharField(max_length=20)  # 表名
    table_columns = ArrayField(models.CharField(max_length=20))  # 表列
    time_begin = models.IntegerField(default=0)  # 开始时间
    time_end = models.IntegerField(default=0)  # 结束时间
    time_unit = models.CharField(max_length=10)  # 时间单位

class WorkModule(models.Model):
    """预测模块表
    
    - 模块通过注册接口创建记录，`module_hash` 唯一标识模块。
    - WebSocket 连接建立后，写入 `session_id` 与在线状态 `alive`。
    """

    # 主键字段 (MongoDB 需要显式定义为 ObjectId)
    id = ObjectIdAutoField(primary_key=True)
    
    # 基本信息
    module_id = models.IntegerField(unique=True, null=True, blank=True)  # 模块ID（自增）
    name = models.CharField(max_length=100)  # 模块名称
    description = models.CharField(max_length=500, null=True, blank=True)  # 模块描述

    # 状态信息
    priority = models.IntegerField(default=100)  # 优先级
    module_hash = models.CharField(max_length=64, unique=True)  # 模块哈希值
    alive = models.BooleanField(default=False)  # 在线状态
    session_id = models.CharField(max_length=64, null=True, blank=True)  # 会话ID
    last_alive_time = models.DateTimeField(null=True, blank=True)  # 最后存活时间
    last_login_time = models.DateTimeField(null=True, blank=True)  # 最后登录时间
    
    # 执行信息
    last_execution_time = models.DateTimeField(null=True, blank=True)  # 最后执行时间

    # 数据需求
    input_data = EmbeddedModelArrayField(DataRequirement)  # 输入数据需求
    output_data = EmbeddedModelArrayField(DataRequirement)  # 输出数据需求

    def save(self, *args, **kwargs):
        """重写 save 方法，实现 module_id 自增"""
        if not self.module_id:
            # 获取当前最大的 module_id
            max_module = WorkModule.objects.all().order_by('-module_id').first()
            if max_module and max_module.module_id:
                self.module_id = max_module.module_id + 1
            else:
                self.module_id = 1
        super().save(*args, **kwargs)

    class Meta:
        db_table = "module"  # 指定表名
        indexes = [
            models.Index(fields=["module_hash"], name="idx_module_hash"), # 按模块哈希值查询加速
            models.Index(fields=["name"], name="idx_name"),   # 按名称查询加速
            models.Index(fields=["alive"], name="idx_alive"), # 在线状态查询加速
            models.Index(fields=["module_id"], name="idx_module_id"),  # 按模块ID查询加速
        ]

class WorkFlow(models.Model):
    """工作流配置"""

    id = ObjectIdAutoField(primary_key=True)
    workflow_id = models.IntegerField(unique=True, null=True, blank=True)  # 工作流ID（自增）
    name = models.CharField(max_length=100)  # 工作流名称
    description = models.CharField(max_length=500, null=True, blank=True)  # 工作流描述
    enable = models.BooleanField(default=True)  # 是否启用

    execute_cron_list = ArrayField(models.CharField(max_length=50))  # 执行 crontab
    execute_shift_time = models.IntegerField(default=0)  # 执行偏移时间
    execute_shift_unit = models.CharField(max_length=10)  # 执行偏移时间单位

    execute_modules = models.JSONField(null=True, blank=True)  # 执行模块

    def save(self, *args, **kwargs):
        """重写 save 方法，实现 workflow_id 自增"""
        if not self.workflow_id:
            # 获取当前最大的 workflow_id
            max_workflow = WorkFlow.objects.all().order_by('-workflow_id').first()
            if max_workflow and max_workflow.workflow_id:
                self.workflow_id = max_workflow.workflow_id + 1
            else:
                self.workflow_id = 1
        super().save(*args, **kwargs)

    class Meta:
        db_table = "workflow"  # 指定表名
        indexes = [
            models.Index(fields=["name"], name="idx_workflow_name"),  # 按名称查询加速
            models.Index(fields=["workflow_id"], name="idx_workflow_id"),  # 按工作流ID查询加速
            models.Index(fields=["enable"], name="idx_workflow_enable"),  # 按启用状态查询加速
        ]

# MySQL version
# class ForecastModule(models.Model):
#     """预测模块表

#     - 模块通过注册接口创建记录，`module_hash` 唯一标识模块。
#     - WebSocket 连接建立后，写入 `session_id` 与在线状态 `alive`。
#     - `data_requirement` 保存模块所需数据结构（JSON）。
#     """
#     name = models.CharField(max_length=100)
#     description = models.CharField(max_length=500, null=True, blank=True)
#     mission_kind = models.CharField(max_length=50, null=True, blank=True)
#     priority = models.IntegerField(default=100)
#     module_hash = models.CharField(max_length=64, unique=True)
#     alive = models.BooleanField(default=False)
#     session_id = models.CharField(max_length=64, null=True, blank=True)
#     last_alive_time = models.DateTimeField(null=True, blank=True)
#     last_login_time = models.DateTimeField(null=True, blank=True)
#     data_requirement = models.JSONField(null=True, blank=True)

#     class Meta:
#         db_table = "forecast_module"
#         indexes = [
#             models.Index(fields=["name"], name="idx_name"),   # 按名称查询加速
#             models.Index(fields=["alive"], name="idx_alive"), # 在线状态查询加速
#         ]


# class ForecastTask(models.Model):
#     """预测任务表（占位，后续可扩展）"""
#     class Meta:
#         db_table = "forecast_task"


