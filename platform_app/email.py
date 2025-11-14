"""
邮件模板模块

用于生成各种工作流执行失败的邮件通知内容
"""
from datetime import datetime
from typing import Optional
from decouple import config
from .utils import send_email_notification

# 默认收件人邮箱，必须通过环境变量 NOTIFICATION_EMAIL 配置
DEFAULT_NOTIFICATION_EMAIL = config("NOTIFICATION_EMAIL")


def format_module_execution_failure_email(
    workflow_name: str,
    workflow_id: Optional[str],
    module_name: str,
    module_hash: str,
    error_message: str,
    failure_time: datetime
) -> tuple[str, str]:
    """
    生成模块执行失败的邮件主题和内容
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_name: 模块名称
        module_hash: 模块Hash
        error_message: 错误信息
        failure_time: 失败时间
    
    Returns:
        tuple: (邮件主题, 邮件内容)
    """
    subject = f"【工作流执行失败】{workflow_name} - {module_name}"
    
    content = f"""工作流模块执行失败通知

工作流名称: {workflow_name}
工作流ID: {workflow_id or "未知"}
模块名称: {module_name}
模块Hash: {module_hash}
失败时间: {failure_time.strftime('%Y-%m-%d %H:%M:%S')}
错误信息: {error_message}

请及时检查并处理。
"""
    return subject, content.strip()


def format_module_not_found_email(
    workflow_name: str,
    workflow_id: Optional[int],
    module_hash: str,
    failure_time: datetime
) -> tuple[str, str]:
    """
    生成模块不存在或已离线的邮件主题和内容
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_hash: 模块Hash
        failure_time: 失败时间
    
    Returns:
        tuple: (邮件主题, 邮件内容)
    """
    subject = f"【工作流执行失败】{workflow_name} - 模块不存在或已离线"
    
    content = f"""工作流模块执行失败通知

工作流名称: {workflow_name}
工作流ID: {workflow_id or "未知"}
模块Hash: {module_hash}
失败时间: {failure_time.strftime('%Y-%m-%d %H:%M:%S')}
错误信息: 模块不存在或已离线

请检查模块是否已注册或在线状态。
"""
    return subject, content.strip()


def format_module_name_not_found_email(
    workflow_name: str,
    workflow_id: Optional[int],
    module_name: str,
    failure_time: datetime
) -> tuple[str, str]:
    """
    生成模块名称不存在的邮件主题和内容
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_name: 模块名称
        failure_time: 失败时间
    
    Returns:
        tuple: (邮件主题, 邮件内容)
    """
    subject = f"【工作流执行失败】{workflow_name} - 模块名称不存在"
    
    content = f"""工作流模块执行失败通知

工作流名称: {workflow_name}
工作流ID: {workflow_id or "未知"}
模块名称: {module_name}
失败时间: {failure_time.strftime('%Y-%m-%d %H:%M:%S')}
错误信息: 模块名称不存在

请检查模块是否已注册。
"""
    return subject, content.strip()


def format_module_info_invalid_email(
    workflow_name: str,
    workflow_id: Optional[int],
    module_info: str,
    failure_time: datetime
) -> tuple[str, str]:
    """
    生成模块信息无效的邮件主题和内容
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_info: 模块信息
        failure_time: 失败时间
    
    Returns:
        tuple: (邮件主题, 邮件内容)
    """
    subject = f"【工作流执行失败】{workflow_name} - 模块信息无效"
    
    content = f"""工作流模块执行失败通知

工作流名称: {workflow_name}
工作流ID: {workflow_id or "未知"}
模块信息: {module_info}
失败时间: {failure_time.strftime('%Y-%m-%d %H:%M:%S')}
错误信息: 模块信息无效，无法解析 module_hash

请检查工作流配置中的模块信息格式。
"""
    return subject, content.strip()


def format_module_execution_exception_email(
    workflow_name: str,
    workflow_id: Optional[int],
    module_hash: str,
    exception_message: str,
    failure_time: datetime
) -> tuple[str, str]:
    """
    生成模块执行异常的邮件主题和内容
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_hash: 模块Hash
        exception_message: 异常信息
        failure_time: 失败时间
    
    Returns:
        tuple: (邮件主题, 邮件内容)
    """
    subject = f"【工作流执行失败】{workflow_name} - 模块执行异常"
    
    content = f"""工作流模块执行失败通知

工作流名称: {workflow_name}
工作流ID: {workflow_id or "未知"}
模块Hash: {module_hash}
失败时间: {failure_time.strftime('%Y-%m-%d %H:%M:%S')}
错误信息: {exception_message}

请及时检查并处理。
"""
    return subject, content.strip()


def send_module_execution_failure_notification(
    workflow_name: str,
    workflow_id: Optional[str],
    module_name: str,
    module_hash: str,
    error_message: str,
    failure_time: datetime,
    to_email: Optional[str] = None
) -> bool:
    """
    发送模块执行失败的邮件通知
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_name: 模块名称
        module_hash: 模块Hash
        error_message: 错误信息
        failure_time: 失败时间
        to_email: 收件人邮箱，默认使用配置的邮箱
    
    Returns:
        bool: 发送是否成功
    """
    subject, content = format_module_execution_failure_email(
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        module_name=module_name,
        module_hash=module_hash,
        error_message=error_message,
        failure_time=failure_time
    )
    return send_email_notification(
        to_email=to_email or DEFAULT_NOTIFICATION_EMAIL,
        subject=subject,
        content=content
    )


def send_module_not_found_notification(
    workflow_name: str,
    workflow_id: Optional[int],
    module_hash: str,
    failure_time: datetime,
    to_email: Optional[str] = None
) -> bool:
    """
    发送模块不存在或已离线的邮件通知
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_hash: 模块Hash
        failure_time: 失败时间
        to_email: 收件人邮箱，默认使用配置的邮箱
    
    Returns:
        bool: 发送是否成功
    """
    subject, content = format_module_not_found_email(
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        module_hash=module_hash,
        failure_time=failure_time
    )
    return send_email_notification(
        to_email=to_email or DEFAULT_NOTIFICATION_EMAIL,
        subject=subject,
        content=content
    )


def send_module_name_not_found_notification(
    workflow_name: str,
    workflow_id: Optional[int],
    module_name: str,
    failure_time: datetime,
    to_email: Optional[str] = None
) -> bool:
    """
    发送模块名称不存在的邮件通知
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_name: 模块名称
        failure_time: 失败时间
        to_email: 收件人邮箱，默认使用配置的邮箱
    
    Returns:
        bool: 发送是否成功
    """
    subject, content = format_module_name_not_found_email(
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        module_name=module_name,
        failure_time=failure_time
    )
    return send_email_notification(
        to_email=to_email or DEFAULT_NOTIFICATION_EMAIL,
        subject=subject,
        content=content
    )


def send_module_info_invalid_notification(
    workflow_name: str,
    workflow_id: Optional[int],
    module_info: str,
    failure_time: datetime,
    to_email: Optional[str] = None
) -> bool:
    """
    发送模块信息无效的邮件通知
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_info: 模块信息
        failure_time: 失败时间
        to_email: 收件人邮箱，默认使用配置的邮箱
    
    Returns:
        bool: 发送是否成功
    """
    subject, content = format_module_info_invalid_email(
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        module_info=module_info,
        failure_time=failure_time
    )
    return send_email_notification(
        to_email=to_email or DEFAULT_NOTIFICATION_EMAIL,
        subject=subject,
        content=content
    )


def send_module_execution_exception_notification(
    workflow_name: str,
    workflow_id: Optional[int],
    module_hash: str,
    exception_message: str,
    failure_time: datetime,
    to_email: Optional[str] = None
) -> bool:
    """
    发送模块执行异常的邮件通知
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_hash: 模块Hash
        exception_message: 异常信息
        failure_time: 失败时间
        to_email: 收件人邮箱，默认使用配置的邮箱
    
    Returns:
        bool: 发送是否成功
    """
    subject, content = format_module_execution_exception_email(
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        module_hash=module_hash,
        exception_message=exception_message,
        failure_time=failure_time
    )
    return send_email_notification(
        to_email=to_email or DEFAULT_NOTIFICATION_EMAIL,
        subject=subject,
        content=content
    )


def format_module_execution_timeout_email(
    workflow_name: str,
    workflow_id: Optional[str],
    module_name: str,
    module_hash: str,
    execution_id: str,
    elapsed_seconds: float,
    timeout_seconds: int,
    failure_time: datetime
) -> tuple[str, str]:
    """
    生成模块执行超时的邮件主题和内容
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_name: 模块名称
        module_hash: 模块Hash
        execution_id: 执行ID
        elapsed_seconds: 已等待时间（秒）
        timeout_seconds: 超时时间（秒）
        failure_time: 超时时间
    
    Returns:
        tuple: (邮件主题, 邮件内容)
    """
    subject = f"【工作流执行超时】{workflow_name} - {module_name}"
    
    content = f"""工作流模块执行超时通知

工作流名称: {workflow_name}
工作流ID: {workflow_id or "未知"}
模块名称: {module_name}
模块Hash: {module_hash}
执行ID: {execution_id}
超时时间: {timeout_seconds} 秒
已等待时间: {elapsed_seconds:.1f} 秒
超时时间: {failure_time.strftime('%Y-%m-%d %H:%M:%S')}
错误信息: 模块执行指令超时，未在规定时间内返回结果

请检查模块是否正常运行或网络连接是否正常。
"""
    return subject, content.strip()


def send_module_execution_timeout_notification(
    workflow_name: str,
    workflow_id: Optional[str],
    module_name: str,
    module_hash: str,
    execution_id: str,
    elapsed_seconds: float,
    timeout_seconds: int,
    failure_time: datetime,
    to_email: Optional[str] = None
) -> bool:
    """
    发送模块执行超时的邮件通知
    
    Args:
        workflow_name: 工作流名称
        workflow_id: 工作流ID
        module_name: 模块名称
        module_hash: 模块Hash
        execution_id: 执行ID
        elapsed_seconds: 已等待时间（秒）
        timeout_seconds: 超时时间（秒）
        failure_time: 超时时间
        to_email: 收件人邮箱，默认使用配置的邮箱
    
    Returns:
        bool: 发送是否成功
    """
    subject, content = format_module_execution_timeout_email(
        workflow_name=workflow_name,
        workflow_id=workflow_id,
        module_name=module_name,
        module_hash=module_hash,
        execution_id=execution_id,
        elapsed_seconds=elapsed_seconds,
        timeout_seconds=timeout_seconds,
        failure_time=failure_time
    )
    return send_email_notification(
        to_email=to_email or DEFAULT_NOTIFICATION_EMAIL,
        subject=subject,
        content=content
    )

