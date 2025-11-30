import logging
from datetime import datetime, timedelta
import pytz
import uuid
from django.utils import timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.combining import OrTrigger
from django.conf import settings
from django.db import models
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from platform_app.models import WorkModule, WorkFlow
from platform_app.consumers import send_message_to_client, _execution_waiting, _channel_layer
from decouple import config
from asgiref.sync import async_to_sync

from .utils import parse_time_tz, parse_time_shift, to_naive_local, local_now
from .email import (
    send_module_not_found_notification,
    send_module_name_not_found_notification,
    send_module_info_invalid_notification,
    send_module_execution_exception_notification,
    send_module_execution_timeout_notification
)

logger = logging.getLogger(__name__)

# WebSocket 连接超时时间配置（秒），默认120秒（2分钟）
# 如果 last_alive_time 超过此时间未更新，则认为连接已断开
WEBSOCKET_TIMEOUT_SECONDS = config("WEBSOCKET_TIMEOUT_SECONDS", default=120, cast=int)

# 执行指令等待超时时间配置（秒），默认120秒（2分钟）
EXECUTION_TIMEOUT_SECONDS = config("EXECUTION_TIMEOUT_SECONDS", default=120, cast=int)

# 创建调度器
_trigger_tz = pytz.UTC if settings.USE_TZ else pytz.timezone(settings.TIME_ZONE)
scheduler = BackgroundScheduler(timezone=_trigger_tz)
scheduler.add_jobstore(DjangoJobStore(), "default")

def get_next_execution_time(cron_list, shift_time, shift_unit):
    """
    计算下一次执行时间，如果有多个 cron 表达式，选择距离当前时间最近的那个
    
    Args:
        cron_list (list): crontab 表达式列表
        shift_time (int): 时间偏移量
        shift_unit (str): 时间偏移单位 ('minutes', 'hours', 'days')
    
    Returns:
        next_execution_time: 下一次执行时间
    """
    
    # 计算所有 crontab 表达式的下一个执行时间
    next_times = []
    now = parse_time_tz(parse_time_shift(timezone.now(), shift_time, shift_unit, reverse=True))
    for cron_expr in cron_list:
        try:
            # 解析 crontab 表达式
            parts = cron_expr.split()
            if len(parts) != 5:
                logger.error(f"无效的 crontab 表达式: {cron_expr}")
                continue
            
            minute, hour, day, month, day_of_week = parts
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=_trigger_tz
            )
            next_time = trigger.get_next_fire_time(None, now)
            if next_time:
                next_times.append(next_time)
        except Exception as e:
            logger.error(f"解析 crontab 表达式失败: {cron_expr}, 错误: {str(e)}")
            continue
    
    if not next_times:
        return None
    
    # 获取最近的下一个执行时间
    next_execution_time = min(next_times)
    next_execution_time = parse_time_shift(next_execution_time, shift_time, shift_unit)
    
    return next_execution_time

def execute_workflow(workflow_id):
    """执行工作流的预测任务"""
    try:
        # 获取工作流
        workflow = WorkFlow.objects.get(workflow_id=workflow_id)
        now = timezone.now()
        
        # 获取工作流中需要执行的模块列表
        execute_modules = workflow.execute_modules
        if not execute_modules:
            logger.warning(f"工作流 {workflow.name} 没有配置执行模块")
            return
        
        # 遍历执行每个模块
        for module_info in execute_modules:
            # 支持多种格式：字符串（module_hash）或字典（包含 module_hash 或 name）
            if isinstance(module_info, dict):
                module_hash = module_info.get('module_hash')
                module_name = module_info.get('name')
                module_args = module_info.get('args', {})
                
                # 如果没有 module_hash，尝试通过 name 查找
                if not module_hash and module_name:
                    try:
                        module = WorkModule.objects.get(name=module_name)
                        module_hash = module.module_hash
                    except WorkModule.DoesNotExist:
                        error_msg = f"工作流 {workflow.name} 中的模块名称 {module_name} 不存在"
                        logger.warning(error_msg)
                        
                        # 发送邮件通知
                        send_module_name_not_found_notification(
                            workflow_name=workflow.name,
                            workflow_id=workflow.workflow_id,
                            module_name=module_name,
                            failure_time=to_naive_local(now)
                        )
                        continue
                    except WorkModule.MultipleObjectsReturned:
                        # 如果多个同名模块，取第一个
                        module = WorkModule.objects.filter(name=module_name).first()
                        module_hash = module.module_hash
                        logger.warning(f"工作流 {workflow.name} 中存在多个名为 {module_name} 的模块，使用第一个 模块 {module.name}(id: {module.module_id})")
            else:
                # 字符串格式，直接作为 module_hash
                module_hash = module_info
                module_args = {}
            
            if not module_hash:
                error_msg = f"工作流 {workflow.name} 中的模块信息无效: {module_info}"
                logger.warning(error_msg)
                
                # 发送邮件通知
                send_module_info_invalid_notification(
                    workflow_name=workflow.name,
                    workflow_id=workflow.workflow_id,
                    module_info=str(module_info),
                    failure_time=to_naive_local(now)
                )
                continue
                
            try:
                # 获取模块
                module = WorkModule.objects.get(module_hash=module_hash, alive=True)
                # 存库使用本地朴素时间
                module.last_execution_time = to_naive_local(now)
                module.save()
                
                # 生成执行ID用于跟踪
                execution_id = str(uuid.uuid4())
                
                # 发送执行命令到客户端
                message = {
                    "type": "execute",
                    "meta": {
                        "execution_id": execution_id,  # 添加执行ID用于跟踪
                        "execution_time": to_naive_local(now).isoformat(),
                        "workflow_id": str(workflow.id),
                        "workflow_name": workflow.name
                    },
                    "args": module_args  # 传递模块参数
                }
                send_message_to_client(module.module_id, message)
                
                # 记录执行等待状态
                _execution_waiting[execution_id] = {
                    'module_id': module.module_id,
                    'workflow_id': str(workflow.workflow_id),
                    'workflow_name': workflow.name,
                    'module_name': module.name,
                    'sent_time': to_naive_local(now)
                }
                
                logger.info(f"工作流 {workflow.name} 执行模块 {module.name}(id: {module.module_id})，执行ID: {execution_id}")
            except WorkModule.DoesNotExist:
                error_msg = f"工作流 {workflow.name} 中的模块 {module_hash} 不存在或已离线"
                logger.error(error_msg)
                
                # 发送邮件通知（使用 module_hash 查找模块信息）
                try:
                    module = WorkModule.objects.get(module_hash=module_hash)
                    send_module_not_found_notification(
                        workflow_name=workflow.name,
                        workflow_id=workflow.workflow_id,
                        module_id=module.module_id,
                        module_name=module.name,
                        failure_time=to_naive_local(now)
                    )
                except WorkModule.DoesNotExist:
                    # 如果找不到模块，使用 hash 作为标识
                    send_module_not_found_notification(
                        workflow_name=workflow.name,
                        workflow_id=workflow.workflow_id,
                        module_id=None,
                        module_name=None,
                        failure_time=to_naive_local(now)
                    )
            except Exception as e:
                error_msg = f"工作流 {workflow.name} 执行模块 {module_hash} 失败: {str(e)}"
                logger.error(error_msg)
                
                # 发送邮件通知（使用 module_hash 查找模块信息）
                try:
                    module = WorkModule.objects.get(module_hash=module_hash)
                    send_module_execution_exception_notification(
                        workflow_name=workflow.name,
                        workflow_id=workflow.workflow_id,
                        module_id=module.module_id,
                        module_name=module.name,
                        exception_message=str(e),
                        failure_time=to_naive_local(now)
                    )
                except WorkModule.DoesNotExist:
                    # 如果找不到模块，使用 hash 作为标识
                    send_module_execution_exception_notification(
                        workflow_name=workflow.name,
                        workflow_id=workflow.workflow_id,
                        module_id=None,
                        module_name=None,
                        exception_message=str(e),
                        failure_time=to_naive_local(now)
                    )
            
    except WorkFlow.DoesNotExist:
        logger.error(f"工作流 {workflow_id} 不存在")
    except Exception as e:
        logger.error(f"工作流 {workflow_id} 执行失败: {str(e)}")

def add_workflow_job(workflow):
    """为工作流添加调度任务"""
    try:
        next_execution_time = get_next_execution_time(
            workflow.execute_cron_list,
            workflow.execute_shift_time,
            workflow.execute_shift_unit
        )
        if next_execution_time is None:
            logger.warning(f"工作流 {workflow.name} 无法计算下一次执行时间")
            return
            
        # 使用 workflow_id 作为 job_id，如果不存在则使用 id
        job_id = f"workflow_{workflow.workflow_id if workflow.workflow_id else workflow.id}"

        trigger = CronTrigger(
            minute=next_execution_time.minute,
            hour=next_execution_time.hour,
            day=next_execution_time.day,
            month=next_execution_time.month,
            second=next_execution_time.second,
            day_of_week=next_execution_time.weekday(),
            timezone=_trigger_tz
        )
        
        # 添加任务
        scheduler.add_job(
            execute_workflow,
            trigger,
            id=job_id,
            args=[str(workflow.workflow_id)],
            misfire_grace_time=None,  # 错过的任务不再执行
            coalesce=True,  # 合并重复的任务
            max_instances=1,  # 同一时间只允许一个实例运行
            replace_existing=True,
        )
        
        logger.info(f"工作流 {workflow.name} 的调度任务已添加，下一次执行时间: {next_execution_time}")
    except Exception as e:
        logger.error(f"添加工作流 {workflow.name} 的调度任务失败: {str(e)}")

def remove_workflow_job(workflow):
    """移除工作流的调度任务"""
    try:
        # 使用 workflow_id 作为 job_id，如果不存在则使用 id（转换为字符串）
        if workflow.workflow_id:
            job_id = f"workflow_{workflow.workflow_id}"
        else:
            job_id = f"workflow_{str(workflow.id)}"
        
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"工作流 {workflow.name} 的调度任务已移除 (job_id: {job_id})")
    except Exception as e:
        logger.error(f"移除工作流 {workflow.name} 的调度任务失败: {str(e)}")

def cleanup_old_job_executions(max_age=604_800):
    """清理旧的任务执行记录"""
    DjangoJobExecution.objects.delete_old_job_executions(max_age)

def check_execution_timeout():
    """检查所有等待中的执行指令是否超时，如果超时则发送邮件通知"""
    try:
        now = local_now()
        timeout_threshold = now - timedelta(seconds=EXECUTION_TIMEOUT_SECONDS)
        
        # 遍历所有等待中的执行指令
        expired_executions = []
        for execution_id, execution_info in list(_execution_waiting.items()):
            sent_time = execution_info['sent_time']
            
            # 检查是否超时（sent_time 早于超时阈值）
            if sent_time < timeout_threshold:
                expired_executions.append((execution_id, execution_info))
        
        if expired_executions:
            logger.info(f"检测到 {len(expired_executions)} 个执行指令超时")
            
            # 处理每个超时的执行指令
            for execution_id, execution_info in expired_executions:
                module_id = execution_info['module_id']
                workflow_id = execution_info['workflow_id']
                workflow_name = execution_info['workflow_name']
                module_name = execution_info['module_name']
                sent_time = execution_info['sent_time']
                
                elapsed_seconds = (now - sent_time).total_seconds()
                
                # 发送邮件通知
                try:
                    send_module_execution_timeout_notification(
                        workflow_name=workflow_name,
                        workflow_id=workflow_id,
                        module_name=module_name,
                        module_id=module_id,
                        execution_id=execution_id,
                        elapsed_seconds=elapsed_seconds,
                        timeout_seconds=EXECUTION_TIMEOUT_SECONDS,
                        failure_time=to_naive_local(now)
                    )
                    
                    logger.warning(
                        f"模块 {module_name}(id: {module_id}) 执行指令超时 "
                        f"(工作流: {workflow_name}, 执行ID: {execution_id}, "
                        f"等待时间: {elapsed_seconds:.1f}秒)，已发送邮件通知"
                    )
                except Exception as e:
                    logger.error(f"发送超时邮件通知失败 (执行ID: {execution_id}): {str(e)}", exc_info=True)
                
                # 移除等待状态
                _execution_waiting.pop(execution_id, None)
        else:
            logger.debug(f"所有执行指令正常，当前等待中的执行指令数量: {len(_execution_waiting)}")
            
    except Exception as e:
        logger.error(f"检查执行超时失败: {str(e)}", exc_info=True)


def _cleanup_channel_group(module_id):
    """清理指定模块的 channel group
    
    注意：由于不知道具体的 channel_name，这里尝试清理整个 group。
    对于 InMemoryChannelLayer，可以尝试直接清理；对于其他类型，group 会在没有活跃连接时自动清理。
    
    Args:
        module_id: 模块ID
    """
    try:
        if _channel_layer is None:
            return False
        
        group_name = f"module_{module_id}"
        
        # 尝试清理 group（如果 _channel_layer 支持）
        # 对于 InMemoryChannelLayer，可以尝试直接访问并清理
        try:
            from channels.layers import InMemoryChannelLayer
            if isinstance(_channel_layer, InMemoryChannelLayer):
                # 直接访问 groups 并清理
                groups = getattr(_channel_layer, 'groups', None)
                if groups and group_name in groups:
                    # 清空 group 中的所有 channel
                    groups[group_name].clear()
                    logger.debug(f"已清理 channel group: {group_name}")
                    return True
        except Exception as e:
            logger.debug(f"清理 channel group {group_name} 失败（可能不支持直接操作）: {str(e)}")
        
        # 对于其他类型的 channel_layer，group 会在没有活跃连接时自动清理
        # 或者可以通过发送一个清理消息（但僵尸连接已断开，不会收到）
        return False
        
    except Exception as e:
        logger.warning(f"清理 channel group 时发生异常: {str(e)}")
        return False


def check_and_cleanup_zombie_connections():
    """检查并清理僵尸 WebSocket 连接
    
    僵尸连接定义：last_alive_time 超过 WEBSOCKET_TIMEOUT_SECONDS 未更新的在线连接
    """
    try:
        now = local_now()
        timeout_threshold = now - timedelta(seconds=WEBSOCKET_TIMEOUT_SECONDS)
        
        # 查询所有在线但可能超时的模块
        # 注意：last_alive_time 可能为 None，需要特殊处理
        zombie_modules = WorkModule.objects.filter(
            alive=True
        ).filter(
            models.Q(last_alive_time__lt=timeout_threshold) | 
            models.Q(last_alive_time__isnull=True)
        )
        
        zombie_count = zombie_modules.count()
        
        if zombie_count > 0:
            logger.warning(f"检测到 {zombie_count} 个僵尸 WebSocket 连接，开始清理")
            
            cleaned_count = 0
            for module in zombie_modules:
                try:
                    # 计算超时时间
                    if module.last_alive_time:
                        elapsed_seconds = (now - module.last_alive_time).total_seconds()
                    else:
                        elapsed_seconds = None
                    
                    elapsed_str = f"{elapsed_seconds:.1f}秒" if elapsed_seconds is not None else "未知"
                    old_session_id = module.session_id
                    
                    logger.info(
                        f"清理僵尸连接: 模块 {module.name}(id: {module.module_id}), "
                        f"最后活跃时间: {module.last_alive_time}, "
                        f"超时时间: {elapsed_str}, "
                        f"会话ID: {old_session_id}"
                    )
                    
                    # 清理 channel group
                    _cleanup_channel_group(module.module_id)
                    
                    # 更新数据库状态
                    # 注意：不调用 close_module_websocket，因为僵尸连接已经断开，
                    # 通过 group_send 发送消息无法关闭已断开的连接
                    module.session_id = None
                    module.alive = False
                    module.save()
                    
                    cleaned_count += 1
                    
                    logger.info(
                        f"已清理僵尸连接: 模块 {module.name}(id: {module.module_id}), "
                        f"已更新数据库状态为离线并清理 channel group"
                    )
                    
                except Exception as e:
                    logger.error(
                        f"清理僵尸连接失败: 模块 {module.name}(id: {module.module_id}), "
                        f"错误: {str(e)}", 
                        exc_info=True
                    )
                    # 即使出错也尝试更新状态
                    try:
                        module.session_id = None
                        module.alive = False
                        module.save()
                    except Exception as save_error:
                        logger.error(f"更新模块状态失败: {str(save_error)}", exc_info=True)
            
            logger.info(f"僵尸连接清理完成，共清理 {cleaned_count}/{zombie_count} 个连接")
        else:
            logger.debug(f"未发现僵尸连接，当前在线模块数量: {WorkModule.objects.filter(alive=True).count()}")
            
    except Exception as e:
        logger.error(f"检查并清理僵尸连接失败: {str(e)}", exc_info=True)


def reload_workflow_jobs():
    """重新加载所有工作流定时任务"""
    # 获取所有当前工作流的 job_id（包括 enable=False 的，用于清理）
    valid_job_ids = set()
    for workflow in WorkFlow.objects.all():
        # 确保 ObjectId 转换为字符串
        if workflow.workflow_id:
            job_id = f"workflow_{workflow.workflow_id}"
        else:
            job_id = f"workflow_{str(workflow.id)}"
        valid_job_ids.add(job_id)
        # 移除所有旧任务（不管 enable 状态）
        remove_workflow_job(workflow)
    
    # 清理所有遗留的工作流任务（不在数据库中的）
    all_jobs = scheduler.get_jobs()
    removed_count = 0
    for job in all_jobs:
        if job.id.startswith("workflow_") and job.id not in valid_job_ids:
            try:
                scheduler.remove_job(job.id)
                logger.info(f"移除遗留的工作流任务: {job.id}")
                removed_count += 1
            except Exception as e:
                logger.warning(f"移除遗留任务 {job.id} 失败: {str(e)}")
    
    if removed_count > 0:
        logger.info(f"共清理了 {removed_count} 个遗留的工作流任务")
    
    # 只添加启用状态的工作流任务
    for workflow in WorkFlow.objects.filter(enable=True):
        print(f"加载工作流 {workflow.name} (ID: {workflow.workflow_id})")
        add_workflow_job(workflow)

def initialize_scheduler():

    scheduler.remove_all_jobs()

    """初始化调度器"""
    # 重新加载工作流任务
    reload_workflow_jobs()
    
    # 添加清理任务
    scheduler.add_job(
        cleanup_old_job_executions,
        trigger=CronTrigger(
            day_of_week="mon", hour="00", minute="00", timezone=_trigger_tz
        ),
        id="cleanup_old_job_executions",
        max_instances=1,
        replace_existing=True,
    )
    
    # 添加执行指令超时检查任务（30 秒钟执行一次）
    scheduler.add_job(
        check_execution_timeout,
        trigger=IntervalTrigger(seconds=30, timezone=_trigger_tz),
        id="check_execution_timeout",
        max_instances=1,
        replace_existing=True,
    )
    logger.info(f"执行指令超时检查任务已添加，超时时间: {EXECUTION_TIMEOUT_SECONDS} 秒")
    
    # 添加 WebSocket 僵尸连接检查任务（60 秒钟执行一次）
    # 检查间隔建议设置为超时时间的 1/2，确保及时清理
    websocket_check_interval = max(30, WEBSOCKET_TIMEOUT_SECONDS // 2)
    scheduler.add_job(
        check_and_cleanup_zombie_connections,
        trigger=IntervalTrigger(seconds=websocket_check_interval, timezone=_trigger_tz),
        id="check_and_cleanup_zombie_connections",
        max_instances=1,
        replace_existing=True,
    )
    logger.info(
        f"WebSocket 僵尸连接检查任务已添加，检查间隔: {websocket_check_interval} 秒，"
        f"超时时间: {WEBSOCKET_TIMEOUT_SECONDS} 秒"
    )
    
    # 启动调度器
    scheduler.start()
