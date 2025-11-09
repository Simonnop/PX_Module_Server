from django.core.management.base import BaseCommand
from platform_app.models import WorkFlow, WorkModule

# 自定义管理命令（类比 Spring 的运维脚本/定时任务入口）
# 用法：python manage.py add

# WorkFlowCONFIG = {
#     "name": "A股数据获取",
#     "description": "用于A股数据定时获取的工作流",
#     "execute_cron_list": [
#         "30-55/5 9 * * 1-5",
#         "*/5 10 * * 1-5",
#         "0-30/5 11 * * 1-5",
#         "*/5 13 * * 1-5",
#         "*/5 14 * * 1-5",
#         "0 15 * * 1-5"
#     ],
#     "execute_shift_time": 0,
#     "execute_shift_unit": "s",
#     "enable": True,
#     "execute_modules": [
#         {
#             "name": "股票实时数据获取模块",
#             "args": {
#                 "code_list": [
#                     "601197"
#                 ]
#             }
#         },
#         {
#             "name": "基金实时数据获取模块",
#             "args": {
#                 "code_list": [
#                     "510300"
#                 ]
#             }
#         }
#     ]
# }

WorkFlowCONFIG = {
    "name": "测试工作流",
    "description": "这是一个测试工作流",
    "execute_cron_list": [
        "*/10 17 * * *",
    ],
    "execute_shift_time": -0,
    "execute_shift_unit": "s",
    "enable": True,
    "execute_modules": [
        {
            "name": "测试模块",
            "args": {
                "print": "hi~"
            }
        }
    ]
}


class Command(BaseCommand):
    help = "添加工作流"

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            default='默认工作流',
            help='工作流名称',
        )
        parser.add_argument(
            '--description',
            type=str,
            default='',
            help='工作流描述',
        )
        parser.add_argument(
            '--use-config',
            action='store_true',
            help='使用预定义的 WorkFlowCONFIG 配置',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='强制创建工作流，即使模块不存在也创建（仅在使用 --use-config 时有效）',
        )

    def handle(self, *args, **options):
        name = options['name']
        description = options.get('description', '')
        use_config = options.get('use_config', False)
        force = options.get('force', False)

        # 询问是否使用预定义配置
        if not use_config:
            use_config_input = input("是否使用预定义配置? (y/n): ")
            use_config = use_config_input.lower() == 'y'

        # 询问是否强制
        if not force:
            force_input = input("是否强制创建工作流，即使模块不存在也创建? (y/n): ")
            force = force_input.lower() == 'y'
            if force:
                self.stdout.write(
                    self.style.WARNING('警告: 强制创建工作流，即使模块不存在也创建')
                )

        if use_config:
            # 使用预定义配置
            config = WorkFlowCONFIG
            # 如果配置中有 name 和 description，优先使用配置中的值（除非用户通过参数指定）
            if 'name' in config and name == '默认工作流':
                name = config['name']
            if 'description' in config and not description:
                description = config.get('description', '')
            
            execute_cron_list = config['execute_cron_list']
            execute_shift_time = config['execute_shift_time']
            execute_shift_unit = config['execute_shift_unit']
            execute_modules_config = config['execute_modules']
            
            # 处理模块配置
            execute_modules = []
            for module_info in execute_modules_config:
                module_name = module_info.get('name')
                module_args = module_info.get('args', {})
                
                if module_name:
                    if force:
                        # 强制模式：直接使用配置中的模块信息，不验证是否存在
                        execute_modules.append({
                            "name": module_name,
                            "args": module_args
                        })
                        self.stdout.write(
                            self.style.WARNING(f'强制模式: 使用模块 "{module_name}"（不验证是否存在）')
                        )
                    else:
                        # 正常模式：验证模块是否存在
                        try:
                            module = WorkModule.objects.get(name=module_name)
                            # 保留 name 和 args，scheduler 会通过 name 查找模块
                            execute_modules.append({
                                "name": module_name,
                                "args": module_args
                            })
                        except WorkModule.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f'警告: 模块 "{module_name}" 不存在，跳过（使用 --force 可强制创建）')
                            )
                            continue
                        except WorkModule.MultipleObjectsReturned:
                            # 如果多个同名模块，取第一个
                            module = WorkModule.objects.filter(name=module_name).first()
                            execute_modules.append({
                                "name": module_name,
                                "args": module_args
                            })
                            self.stdout.write(
                                self.style.WARNING(f'警告: 存在多个名为 "{module_name}" 的模块，使用第一个 (hash: {module.module_hash})')
                            )
            
            if not execute_modules:
                if force:
                    self.stdout.write(
                        self.style.ERROR('错误: 配置中没有模块信息，无法创建工作流')
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR('错误: 没有找到有效的模块，无法创建工作流（使用 --force 可强制创建）')
                    )
                return
            
            workflow = WorkFlow.objects.create(
                name=name,
                description=description,
                execute_cron_list=execute_cron_list,
                execute_shift_time=execute_shift_time,
                execute_shift_unit=execute_shift_unit,
                execute_modules=execute_modules,
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'成功创建工作流: {workflow.name} (ID: {workflow.id})')
            )
            self.stdout.write(f'  - Cron 表达式: {execute_cron_list}')
            self.stdout.write(f'  - 偏移时间: {execute_shift_time} {execute_shift_unit}')
            self.stdout.write(f'  - 执行模块数: {len(execute_modules)}')
        else:
            # 交互式创建
            self.stdout.write('交互式创建工作流')
            self.stdout.write('请输入工作流信息（直接回车使用默认值）')
            
            name_input = input(f'工作流名称 [{name}]: ').strip()
            if name_input:
                name = name_input
            
            description_input = input(f'工作流描述 [{description}]: ').strip()
            if description_input:
                description = description_input
            
            # 输入 cron 表达式
            self.stdout.write('请输入 cron 表达式（每行一个，空行结束）:')
            execute_cron_list = []
            while True:
                cron_expr = input('  > ').strip()
                if not cron_expr:
                    break
                execute_cron_list.append(cron_expr)
            
            if not execute_cron_list:
                self.stdout.write(self.style.ERROR('错误: 至少需要一个 cron 表达式'))
                return
            
            # 输入偏移时间
            shift_time_input = input('偏移时间 [0]: ').strip()
            execute_shift_time = int(shift_time_input) if shift_time_input else 0
            
            shift_unit_input = input('偏移时间单位 [s]: ').strip()
            execute_shift_unit = shift_unit_input if shift_unit_input else 's'
            
            # 选择模块
            self.stdout.write('\n可用模块列表:')
            modules = WorkModule.objects.all()
            if not modules.exists():
                self.stdout.write(self.style.ERROR('错误: 没有可用的模块'))
                return
            
            for idx, module in enumerate(modules, 1):
                status = '在线' if module.alive else '离线'
                self.stdout.write(f'  {idx}. {module.name} ({module.module_hash}) [{status}]')
            
            self.stdout.write('\n请输入要执行的模块序号（用逗号分隔，空行结束）:')
            module_indices_input = input('  > ').strip()
            if not module_indices_input:
                self.stdout.write(self.style.ERROR('错误: 至少需要选择一个模块'))
                return
            
            try:
                indices = [int(x.strip()) for x in module_indices_input.split(',')]
                execute_modules = []
                module_list = list(modules)
                for idx in indices:
                    if 1 <= idx <= len(module_list):
                        module = module_list[idx - 1]
                        execute_modules.append({
                            "module_hash": module.module_hash
                        })
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'警告: 序号 {idx} 无效，跳过')
                        )
                
                if not execute_modules:
                    self.stdout.write(self.style.ERROR('错误: 没有选择有效的模块'))
                    return
                
                workflow = WorkFlow.objects.create(
                    name=name,
                    description=description,
                    execute_cron_list=execute_cron_list,
                    execute_shift_time=execute_shift_time,
                    execute_shift_unit=execute_shift_unit,
                    execute_modules=execute_modules,
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'\n成功创建工作流: {workflow.name} (ID: {workflow.id})')
                )
                self.stdout.write(f'  - Cron 表达式: {execute_cron_list}')
                self.stdout.write(f'  - 偏移时间: {execute_shift_time} {execute_shift_unit}')
                self.stdout.write(f'  - 执行模块数: {len(execute_modules)}')
                
            except ValueError:
                self.stdout.write(self.style.ERROR('错误: 输入的序号格式不正确'))

