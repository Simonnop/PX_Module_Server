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
from platform_app.consumers import send_message_to_client, _execution_waiting
from decouple import config

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
            
        # 调度内部使用带时区时间，用于 CronTrigger
        aware_next = parse_time_tz(next_execution_time)

        # 使用 workflow_id 作为 job_id，如果不存在则使用 id
        job_id = f"workflow_{workflow.workflow_id if workflow.workflow_id else workflow.id}"
        
        # 构建多个 cron 表达式的触发器
        triggers = []
        for cron_expr in workflow.execute_cron_list:
            try:
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
                triggers.append(trigger)
            except Exception as e:
                logger.error(f"解析 crontab 表达式失败: {cron_expr}, 错误: {str(e)}")
                continue
        
        if not triggers:
            logger.error(f"工作流 {workflow.name} 没有有效的 cron 表达式")
            return
        
        # 如果有多个触发器，使用 OrTrigger
        if len(triggers) == 1:
            final_trigger = triggers[0]
        else:
            final_trigger = OrTrigger(triggers)
        
        # 添加任务
        scheduler.add_job(
            execute_workflow,
            final_trigger,
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

def check_module_alive_status():
    """检查模块存活状态，基于 WebSocket 连接状态和 last_alive_time 进行监控"""
    try:
        from channels.layers import get_channel_layer, InMemoryChannelLayer
        
        now = local_now()
        timeout_threshold = now - timedelta(seconds=WEBSOCKET_TIMEOUT_SECONDS)
        
        channel_layer = get_channel_layer()
        groups_dict = None
        
        # 尝试获取 channel layer 的 groups 信息（仅适用于 InMemoryChannelLayer）
        if channel_layer is not None:
            if isinstance(channel_layer, InMemoryChannelLayer):
                groups_dict = getattr(channel_layer, 'groups', None)
        
        # 获取所有在线模块
        online_modules = WorkModule.objects.filter(alive=True)
        expired_modules = []
        
        # 检查每个在线模块的存活状态
        for module in online_modules:
            is_expired = False
            reason = ""
            
            # 方法1：检查 WebSocket 连接状态（如果可用）
            if groups_dict is not None:
                group_name = f"module_{module.module_id}"
                try:
                    channel_set = groups_dict.get(group_name)
                    if not channel_set or len(channel_set) == 0:
                        is_expired = True
                        reason = "WebSocket 连接已断开（channel layer 中无活跃连接）"
                except Exception as e:
                    logger.debug(f"检查模块 {module.name}(id: {module.module_id}) channel layer 状态失败: {str(e)}")
            
            # 方法2：检查 last_alive_time 超时（备用检查）
            if not is_expired:
                if module.last_alive_time is None or module.last_alive_time < timeout_threshold:
                    is_expired = True
                    reason = f"last_alive_time 超时（最后活跃时间: {module.last_alive_time}，超时阈值: {timeout_threshold}）"
            
            if is_expired:
                expired_modules.append(module)
                logger.warning(
                    f"模块 {module.name}(id: {module.module_id}) 连接已断开，原因: {reason}"
                )
        
        # 批量更新为离线状态
        if expired_modules:
            module_ids = [m.module_id for m in expired_modules]
            updated_count = WorkModule.objects.filter(module_id__in=module_ids).update(
                alive=False, 
                session_id=None
            )
            logger.info(f"检测到 {len(expired_modules)} 个模块连接已断开，已将 {updated_count} 个模块设置为离线状态")
        else:
            logger.debug("所有在线模块的连接正常")
            
    except Exception as e:
        logger.error(f"检查模块存活状态失败: {str(e)}", exc_info=True)

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
    
    # 添加模块存活状态检查任务（30 秒钟执行一次）
    # 基于 WebSocket 连接状态和 last_alive_time 进行监控
    # WebSocket ping/pong 会触发 receive 方法并更新 last_alive_time
    scheduler.add_job(
        check_module_alive_status,
        trigger=IntervalTrigger(seconds=30, timezone=_trigger_tz),
        id="check_module_alive_status",
        max_instances=1,
        replace_existing=True,
    )
    logger.info(f"模块存活状态检查任务已添加，WebSocket 超时时间: {WEBSOCKET_TIMEOUT_SECONDS} 秒")
    
    # 添加执行指令超时检查任务（30 秒钟执行一次）
    scheduler.add_job(
        check_execution_timeout,
        trigger=IntervalTrigger(seconds=30, timezone=_trigger_tz),
        id="check_execution_timeout",
        max_instances=1,
        replace_existing=True,
    )
    logger.info(f"执行指令超时检查任务已添加，超时时间: {EXECUTION_TIMEOUT_SECONDS} 秒")
    
    # 启动调度器
    scheduler.start()
