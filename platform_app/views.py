import json
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from .models import WorkModule, DataRequirement, WorkFlow
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .scheduler import execute_workflow, scheduler, reload_workflow_jobs
from .consumers import close_module_websocket

# 说明（类比 Spring MVC）：
# - 这些函数可类比为 `@RestController` 下的 `@GetMapping`。
# - 返回统一结构：{"code","message","result"}。


def response_ok(data=None):
    return JsonResponse({"code": "2000", "message": "成功!", "result": data}, json_dumps_params={"ensure_ascii": False})


def response_fail(code: str, message: str):
    return JsonResponse({"code": code, "message": message, "result": None}, status=400, json_dumps_params={"ensure_ascii": False})


@require_GET
@transaction.atomic
def module_register(request: HttpRequest):
    """注册预测模块

    请求参数：name, description, input_data, output_data, modelHash
    返回：{"hash": module_hash, "module_id": module_id}
    """
    name = request.GET.get("name")
    description = request.GET.get("description")
    input_data_json = json.loads(request.GET.get("input_data"))
    output_data_json = json.loads(request.GET.get("output_data"))
    model_hash = request.GET.get("modelHash")

    if not name:
        return response_fail("3002", "传递数据非法!")

    try:
        input_data = []
        for single_input_json in input_data_json:
            # 解析输入数据需求
            input_data.append(DataRequirement(
                table_kind=single_input_json["table_kind"],
                table_name=single_input_json["table_name"],
                table_columns=single_input_json["table_columns"],
                time_begin=single_input_json["time_begin"],
                time_end=single_input_json["time_end"],
                time_unit=single_input_json["time_unit"],
            ))
        # 解析输出数据需求  
        output_data = []
        for single_output_json in output_data_json:
            output_data.append(DataRequirement(
            table_kind=single_output_json["table_kind"],
            table_name=single_output_json["table_name"],
            table_columns=single_output_json["table_columns"],
            time_begin=single_output_json["time_begin"],
            time_end=single_output_json["time_end"],
            time_unit=single_output_json["time_unit"],
        ))
    except (json.JSONDecodeError, ValueError):
        return response_fail("3002", "传递数据非法!")

    hash_value = str(hash(f"{name}:{description}:{model_hash}"))
    if WorkModule.objects.filter(module_hash=hash_value).exists():
        return response_fail("3005", "模块重复注册!")
    
    # 输出参数类型用于调试
    print(f"name 类型: {type(name)}, 值: {name}")
    print(f"description 类型: {type(description)}, 值: {description}")
    print(f"input_data_json 类型: {type(input_data_json)}, 值: {input_data_json}")
    print(f"output_data_json 类型: {type(output_data_json)}, 值: {output_data_json}")
    print(f"model_hash 类型: {type(model_hash)}, 值: {model_hash}")
    print(f"input_data 类型: {type(input_data)}, 值: {input_data}")
    print(f"output_data 类型: {type(output_data)}, 值: {output_data}")
    print(f"hash_value 类型: {type(hash_value)}, 值: {hash_value}")

    module = WorkModule.objects.create(
        name=name,
        description=description,
        module_hash=hash_value,
        input_data=input_data,
        output_data=output_data,
    )

    return response_ok({"hash": module.module_hash, "module_id": module.module_id})


@require_GET
def show_online_modules(request: HttpRequest):
    """查询在线模块列表

    由 WebSocket 连接状态驱动 `alive/session_id/last_login_time` 字段更新。
    连接监控使用 WebSocket ping/pong 机制，不再使用 heartbeat 消息。
    """
    online = WorkModule.objects.filter(alive=True).values(
        "module_id", "name", "description", "priority", "module_hash", "last_execution_time",
        "alive", "session_id", "last_alive_time", "last_login_time",
    )
    return response_ok(list(online))


@require_POST
@csrf_exempt
def send_message(request: HttpRequest):
    """发送消息到模块

    请求参数：module_id, message
    """
    module_id = request.POST.get("module_id")
    message = request.POST.get("message")

    if not module_id:
        return response_fail("3002", "module_id 参数不能为空")
    
    try:
        module_id = int(module_id)
    except ValueError:
        return response_fail("3002", "module_id 必须是整数")

    try:
        module = WorkModule.objects.get(module_id=module_id)
    except WorkModule.DoesNotExist:
        return response_fail("3003", f"模块 (id: {module_id}) 不存在")

    channel_layer = get_channel_layer()

    if channel_layer is None:
        return response_fail("3002", "Channel Layer is not configured. Please check your settings.")

    from .consumers import send_message_to_client
    send_message_to_client(module_id, message)

    return response_ok({"message": message, "module_id": module_id, "module_name": module.name})


@require_POST
@csrf_exempt
def close_module_websocket_api(request: HttpRequest):
    """关闭指定模块的 WebSocket 连接

    请求参数：module_id（模块ID）
    """
    module_id = request.POST.get("module_id")
    
    if not module_id:
        return response_fail("3002", "module_id 参数不能为空")
    
    try:
        module_id = int(module_id)
    except ValueError:
        return response_fail("3002", "module_id 必须是整数")
    
    try:
        # 根据 module_id 查找模块
        module = WorkModule.objects.get(module_id=module_id)
        
        # 检查模块是否在线
        if not module.alive:
            return response_fail("3003", f"模块 {module.name}(id: {module.module_id}) 当前不在线")
        
        # 关闭 WebSocket 连接
        success = close_module_websocket(module.module_id)
        
        if success:
            return response_ok({
                "module_id": module.module_id,
                "module_name": module.name,
                "message": f"已成功关闭模块 {module.name}(id: {module.module_id}) 的 WebSocket 连接"
            })
        else:
            return response_fail("3004", f"关闭模块 {module.name}(id: {module.module_id}) 的 WebSocket 连接失败")
            
    except WorkModule.DoesNotExist:
        return response_fail("3003", f"模块 (id: {module_id}) 不存在")
    except Exception as e:
        return response_fail("3001", f"关闭 WebSocket 连接时发生异常: {str(e)}")


@require_POST
@csrf_exempt
@transaction.atomic
def workflow_create(request: HttpRequest):
    """创建工作流

    请求参数（JSON）：
    {
        "workflow_id": 工作流ID（可选，不提供则自动自增）,
        "name": "工作流名称",
        "description": "工作流描述",
        "enable": true,  // 是否启用，默认 true
        "execute_cron_list": ["*/10 10 * * 1-5", "*/10 14 * * 1-5"],
        "execute_shift_time": -30,
        "execute_shift_unit": "s",
        "execute_modules": [
            {
                "module_hash": "模块hash值"  // 或使用 "name": "模块名称"
                "args": {  // 可选，模块执行参数
                    "stock_list": [...],
                    "fund_list": [...]
                }
            },
            ...
        ]
    }
    返回：{"id": workflow_id, "workflow_id": workflow_id, "name": workflow_name}
    """
    try:
        data = json.loads(request.body)
        workflow_id = data.get("workflow_id")
        name = data.get("name")
        description = data.get("description", "")
        enable = data.get("enable", True)
        execute_cron_list = data.get("execute_cron_list")
        execute_shift_time = data.get("execute_shift_time", 0)
        execute_shift_unit = data.get("execute_shift_unit", "s")
        execute_modules = data.get("execute_modules", [])

        if not name:
            return response_fail("3002", "工作流名称不能为空!")
        
        if not execute_cron_list or not isinstance(execute_cron_list, list):
            return response_fail("3002", "execute_cron_list 必须是非空列表!")
        
        if not execute_modules or not isinstance(execute_modules, list):
            return response_fail("3002", "execute_modules 必须是非空列表!")

        # 如果提供了 workflow_id，检查是否已存在
        if workflow_id is not None:
            if WorkFlow.objects.filter(workflow_id=workflow_id).exists():
                return response_fail("3004", f"工作流ID {workflow_id} 已存在!")

        # 验证模块是否存在（如果提供了 module_hash 或 name）
        for module_info in execute_modules:
            if isinstance(module_info, dict):
                module_hash = module_info.get("module_hash")
                module_name = module_info.get("name")
                
                if module_hash:
                    if not WorkModule.objects.filter(module_hash=module_hash).exists():
                        return response_fail("3003", f"模块 {module_hash} 不存在!")
                elif module_name:
                    if not WorkModule.objects.filter(name=module_name).exists():
                        return response_fail("3003", f"模块名称 {module_name} 不存在!")
                else:
                    return response_fail("3002", "模块信息必须包含 module_hash 或 name!")
            elif isinstance(module_info, str):
                # 字符串格式，可能是 module_hash
                if not WorkModule.objects.filter(module_hash=module_info).exists():
                    return response_fail("3003", f"模块 {module_info} 不存在!")

        workflow = WorkFlow.objects.create(
            workflow_id=workflow_id,
            name=name,
            description=description,
            enable=enable,
            execute_cron_list=execute_cron_list,
            execute_shift_time=execute_shift_time,
            execute_shift_unit=execute_shift_unit,
            execute_modules=execute_modules,
        )

        return response_ok({"id": str(workflow.id), "workflow_id": workflow.workflow_id, "name": workflow.name})
    
    except json.JSONDecodeError:
        return response_fail("3002", "JSON 格式错误!")
    except Exception as e:
        return response_fail("3001", f"创建工作流失败: {str(e)}")


@require_POST
@csrf_exempt
def workflow_execute(request: HttpRequest, workflow_id: int):
    """执行工作流

    请求方式：POST /workflow/{workflow_id}/execute
    
    路径参数：
        workflow_id: 工作流ID
    
    返回：{"workflow_id": workflow_id, "workflow_name": workflow_name, "message": "工作流执行已启动"}
    """
    try:
        # 验证工作流是否存在
        try:
            workflow = WorkFlow.objects.get(workflow_id=workflow_id)
        except WorkFlow.DoesNotExist:
            return response_fail("3003", f"工作流 {workflow_id} 不存在!")
        
        # 执行工作流（传递字符串类型，与 scheduler 中的调用保持一致）
        execute_workflow(str(workflow_id))
        
        return response_ok({
            "workflow_id": workflow_id,
            "workflow_name": workflow.name,
            "message": "工作流执行已启动"
        })
    
    except Exception as e:
        return response_fail("3001", f"执行工作流失败: {str(e)}")


@require_GET
def list_scheduled_jobs(request: HttpRequest):
    """列出 scheduler 中所有的定时任务
    
    返回：定时任务列表，包含 job_id, next_run_time, trigger 等信息，并关联工作流信息
    """
    try:
        jobs = scheduler.get_jobs()
        job_list = []
        
        # 获取所有工作流，用于关联
        workflows_dict = {}
        for wf in WorkFlow.objects.all():
            # 使用 workflow_id 或 id 作为 key
            if wf.workflow_id:
                workflows_dict[f"workflow_{wf.workflow_id}"] = wf
            workflows_dict[f"workflow_{str(wf.id)}"] = wf
        
        for job in jobs:
            # 获取函数信息
            func_str = str(job.func)
            if hasattr(job, 'func_ref'):
                func_str = str(job.func_ref)
            
            job_info = {
                "job_id": job.id,
                "name": job.name or "",
                "func": func_str,
                "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger),
                "max_instances": job.max_instances,
                "misfire_grace_time": job.misfire_grace_time,
            }
            
            # 尝试关联工作流信息
            if job.id in workflows_dict:
                wf = workflows_dict[job.id]
                job_info["workflow"] = {
                    "id": str(wf.id),
                    "workflow_id": wf.workflow_id,
                    "name": wf.name,
                    "enable": wf.enable,
                    "description": wf.description,
                }
            else:
                # 如果找不到对应的工作流，说明可能已被删除
                job_info["workflow"] = None
                job_info["workflow_not_found"] = True
            
            job_list.append(job_info)
        
        return response_ok(job_list)
    
    except Exception as e:
        return response_fail("3001", f"获取定时任务列表失败: {str(e)}")


@require_GET
def list_workflows(request: HttpRequest):
    """列出数据库中所有的工作流
    
    返回：工作流列表，包含 workflow_id, name, enable, execute_cron_list 等信息
    """
    try:
        workflows = WorkFlow.objects.all().values(
            "id", "workflow_id", "name", "description", "enable",
            "execute_cron_list", "execute_shift_time", "execute_shift_unit",
            "execute_modules"
        )
        # 将 ObjectId 转换为字符串
        workflow_list = []
        for wf in workflows:
            wf_dict = dict(wf)
            # 将 id (ObjectId) 转换为字符串
            if wf_dict.get("id"):
                wf_dict["id"] = str(wf_dict["id"])
            workflow_list.append(wf_dict)
        
        return response_ok(workflow_list)
    
    except Exception as e:
        return response_fail("3001", f"获取工作流列表失败: {str(e)}")


@require_POST
@csrf_exempt
def reload_scheduler_jobs(request: HttpRequest):
    """重新加载调度器中的所有工作流任务
    
    会清理所有遗留任务和 enable=False 的任务，只保留 enable=True 的工作流任务
    返回：清理和加载的结果信息
    """
    try:
        # 获取清理前的任务数量
        jobs_before = scheduler.get_jobs()
        job_count_before = len([j for j in jobs_before if j.id.startswith("workflow_")])
        
        # 重新加载工作流任务
        reload_workflow_jobs()
        
        # 获取清理后的任务数量
        jobs_after = scheduler.get_jobs()
        job_count_after = len([j for j in jobs_after if j.id.startswith("workflow_")])
        
        # 获取启用的工作流列表
        enabled_workflows = WorkFlow.objects.filter(enable=True).values(
            "workflow_id", "name"
        )
        workflow_list = []
        for wf in enabled_workflows:
            workflow_list.append({
                "workflow_id": wf["workflow_id"],
                "name": wf["name"]
            })
        
        return response_ok({
            "removed_count": job_count_before - job_count_after,
            "current_count": job_count_after,
            "enabled_workflows": workflow_list,
            "message": f"已清理 {job_count_before - job_count_after} 个任务，当前有 {job_count_after} 个工作流任务"
        })
    
    except Exception as e:
        return response_fail("3001", f"重新加载调度器任务失败: {str(e)}")


@require_GET
def list_channel_groups(request: HttpRequest):
    """列出 channel layer 中所有的 group 及其连接
    
    返回：group 列表，包含 group 名称、连接的 channel 列表，以及关联的模块信息（如果适用）
    """
    try:
        channel_layer = get_channel_layer()
        
        if channel_layer is None:
            return response_fail("3002", "Channel Layer 未配置")
        
        # 检查是否是 InMemoryChannelLayer
        from channels.layers import InMemoryChannelLayer
        if not isinstance(channel_layer, InMemoryChannelLayer):
            return response_fail("3002", f"当前 Channel Layer 类型 ({type(channel_layer).__name__}) 不支持查询 group 信息")
        
        # 获取所有 group 信息
        groups_info = []
        
        # 获取所有在线模块，用于关联 group 信息
        online_modules = {}
        for module in WorkModule.objects.filter(alive=True):
            online_modules[module.module_id] = {
                "module_id": module.module_id,
                "name": module.name,
                "session_id": module.session_id,
                "last_alive_time": module.last_alive_time.isoformat() if module.last_alive_time else None,
                "last_login_time": module.last_login_time.isoformat() if module.last_login_time else None,
            }
        
        # 访问 InMemoryChannelLayer 的 groups 属性
        # groups 是一个字典：{group_name: set of channel_names}
        # 使用 getattr 安全访问，以防属性不存在
        groups_dict = getattr(channel_layer, 'groups', None)
        if groups_dict is None:
            return response_fail("3002", "无法访问 Channel Layer 的 groups 属性")
        
        for group_name, channel_set in groups_dict.items():
            # channel_set 可能是 set 或其他可迭代对象
            try:
                channel_list = list(channel_set) if channel_set else []
            except (TypeError, AttributeError):
                channel_list = []
            
            group_info = {
                "group_name": group_name,
                "channel_count": len(channel_list),
                "channels": channel_list,
            }
            
            # 如果是 module_{module_id} 格式的 group，尝试关联模块信息
            if group_name.startswith("module_"):
                try:
                    module_id_str = group_name.replace("module_", "")
                    module_id = int(module_id_str)
                    if module_id in online_modules:
                        group_info["module"] = online_modules[module_id]
                    else:
                        # 模块不在线，但 group 可能还存在（延迟清理）
                        # 尝试从数据库查询模块信息
                        try:
                            module = WorkModule.objects.get(module_id=module_id)
                            group_info["module"] = {
                                "module_id": module.module_id,
                                "name": module.name,
                                "session_id": module.session_id,
                                "alive": module.alive,
                                "last_alive_time": module.last_alive_time.isoformat() if module.last_alive_time else None,
                                "last_login_time": module.last_login_time.isoformat() if module.last_login_time else None,
                            }
                        except WorkModule.DoesNotExist:
                            group_info["module"] = None
                            group_info["module_id"] = module_id
                            group_info["module_not_found"] = True
                except ValueError:
                    # group 名称格式不正确
                    group_info["module"] = None
            else:
                group_info["module"] = None
            
            groups_info.append(group_info)
        
        return response_ok({
            "total_groups": len(groups_info),
            "groups": groups_info
        })
    
    except Exception as e:
        return response_fail("3001", f"获取 channel groups 信息失败: {str(e)}")

