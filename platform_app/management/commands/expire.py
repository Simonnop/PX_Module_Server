from django.core.management.base import BaseCommand
from platform_app.models import WorkModule

# 自定义管理命令（类比 Spring 的运维脚本/定时任务入口）
# 用法：python manage.py expire_modules


class Command(BaseCommand):
    help = "Set all modules to offline"

    def handle(self, *args, **options):
        updated = WorkModule.objects.update(alive=False, session_id=None)
        self.stdout.write(self.style.SUCCESS(f"已将所有模块设置为离线状态，数量: {updated}"))


