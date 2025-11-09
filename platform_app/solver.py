import pandas as pd
from models import DataRequirement

# 用于解析 DATA_INPUT, 获取对应表的对应时间范围的数据

def solve_data_input(requirement_list, execute_time):
    result_dict = {}
    for requirement in requirement_list:
        result_dict[requirement.table_name] = solve_single_input(requirement, execute_time)
    return result_dict

def solve_single_input(requirement: DataRequirement, execute_time):
    # 获取输入数据需求
    table_kind = requirement.table_kind
    table_name = requirement.table_name
    table_columns = requirement.table_columns
    time_begin = requirement.time_begin
    time_end = requirement.time_end
    time_unit = requirement.time_unit

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
        
    return data

def solve_data_output(requirement_list, execute_time):
    pass

def solve_single_output(requirement: DataRequirement, execute_time):
    pass