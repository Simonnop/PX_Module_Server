import pytz
from django.conf import settings
from datetime import datetime, timedelta

trigger_tz = pytz.UTC if settings.USE_TZ else pytz.timezone(settings.TIME_ZONE)

def parse_time_tz(time):
    """
    解析时间并转换为触发器时区
    Args:
        time: 时间
    Returns:
        time: 转换后的时间
    """
    if time.tzinfo is None:
        # 使用 pytz 的 localize 正确本地化，避免历史偏移问题
        return trigger_tz.localize(time)
    else:
        return time.astimezone(trigger_tz)

def parse_time_shift(time: datetime, shift_time: int, shift_unit: str, reverse: bool = False) -> datetime:
    """
    时间偏移
    Args:
        time (datetime): 时间
        shift_time (int): 时间偏移量
        shift_unit (str): 时间偏移单位
    Returns:
        datetime: 偏移后的时间
    """
    if reverse:
        shift_num = -shift_time
    else:
        shift_num = shift_time

    if shift_unit == 's':
        return time + timedelta(seconds=shift_num)
    elif shift_unit == 'min':
        return time + timedelta(minutes=shift_num)
    elif shift_unit == 'h':
        return time + timedelta(hours=shift_num)
    elif shift_unit == 'D':
        return time + timedelta(days=shift_num)
    else:
        raise ValueError(f"不支持的时间偏移单位: {shift_unit}")

def to_naive_local(time: datetime) -> datetime:
    """
    将时间标准化为本地（settings.TIME_ZONE）朴素时间（naive）。
    - 若为 aware，则先转为本地时区再去掉 tzinfo。
    - 若为 naive，默认其已是本地时间，直接返回。
    """
    if time.tzinfo is None:
        return time
    return time.astimezone(trigger_tz).replace(tzinfo=None)

def local_now() -> datetime:
    """获取本地朴素时间（naive）。"""
    return datetime.now()