from django.core.management.base import BaseCommand
from platform_app.scheduler import reload_workflow_jobs
from platform_app.models import WorkFlow
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "重新加载 workflow 定时任务"

    def handle(self, *args, **options):
        
        # 重新加载启用状态的工作流任务（使用 scheduler.py 中的函数确保使用同一个 scheduler 实例）
        enabled_workflows = WorkFlow.objects.filter(enable=True)
        try:
            reload_workflow_jobs()
            added_count = enabled_workflows.count()
            self.stdout.write(self.style.SUCCESS(f"已重新加载 {added_count} 个工作流任务"))
            
            # 显示加载的工作流详情
            for workflow in enabled_workflows:
                self.stdout.write(f"  ✓ {workflow.name} (ID: {workflow.workflow_id})")
        except Exception as e:
            logger.error(f"重新加载工作流任务失败: {str(e)}")
            self.stdout.write(self.style.ERROR(f"重新加载失败: {str(e)}"))

