import pytz
import requests
import logging
from django.conf import settings
from datetime import datetime, timedelta
from decouple import config

logger = logging.getLogger(__name__)
trigger_tz = pytz.UTC if settings.USE_TZ else pytz.timezone(settings.TIME_ZONE)

# 邮件服务配置
EMAIL_API_URL = config("EMAIL_API_URL")

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

def send_email_notification(to_email: str, subject: str, content: str, content_type: str = "text"):
    """
    发送邮件通知
    
    Args:
        to_email: 收件人邮箱
        subject: 邮件主题
        content: 邮件内容
        content_type: 内容类型，默认为 "text"
    
    Returns:
        bool: 发送是否成功
    """
    try:
        data = {
            "to_email": to_email,
            "subject": subject,
            "content": content,
            "content_type": content_type
        }
        
        response = requests.post(EMAIL_API_URL, json=data, timeout=10)
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"邮件发送成功: {result}")
        return True
    except Exception as e:
        logger.error(f"邮件发送失败: {str(e)}")
        return False