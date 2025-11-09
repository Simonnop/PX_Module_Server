from django.core.management.base import BaseCommand
from platform_app.models import WorkModule
import pandas as pd

# 自定义管理命令（类比 Spring 的运维脚本/定时任务入口）
# 用法：python manage.py expire_modules


class Command(BaseCommand):
    help = "Test"

    def handle(self, *args, **options):
        execute_time = pd.Timestamp("2025-08-27 10:10:00")
        module = WorkModule.objects.all()[0]
        single_input = module.input_data[0]

        # 获取输入数据需求
        table_kind = single_input.table_kind
        table_name = single_input.table_name
        table_columns = single_input.table_columns
        time_begin = single_input.time_begin
        time_end = single_input.time_end
        time_unit = single_input.time_unit

        # 计算起止时点
        time_begin = pd.Timestamp(execute_time) + pd.Timedelta(time_begin, time_unit)
        time_end = pd.Timestamp(execute_time) + pd.Timedelta(time_end, time_unit)
        # 生成数据时点列表
        data_time = pd.date_range(start=time_begin, end=time_end, freq=time_unit)
        # 根据 table_kind 获取数据
        if table_kind == "csv":
            data = pd.read_csv(f"resources/data/{table_name}.csv")
            # 根据 data_time 获取数据
            data_time = data_time.strftime('%Y-%m-%d %H:%M:%S')
            data = data[data['timeStamp'].isin(data_time)]
            # 根据 table_columns 获取数据
            data = data[table_columns].to_dict(orient='records')
        else:
            raise ValueError(f"不支持的表类型: {table_kind}")
        
        print(data)