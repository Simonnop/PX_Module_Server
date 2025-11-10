import json
import logging
from datetime import datetime
from .utils import local_now
from .email import send_module_execution_failure_notification
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import WorkModule, WorkFlow

logger = logging.getLogger(__name__)

# 说明（类比 Spring WebSocket/STOMP）：
# - `AsyncWebsocketConsumer` 处理 WS 生命周期：connect/receive/disconnect。
# - 通过查询参数 `hash` 识别模块，并在连接时绑定会话。


class ModuleConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """建立连接：验证 module_hash 并绑定 session"""
        module_hash = self.scope["query_string"].decode().split("hash=")[-1] if self.scope.get("query_string") else ""
        if not module_hash:
            logger.error("模块hash不存在")
            await self.close()
            return

        try:
            module = await self._get_module(module_hash)
        except WorkModule.DoesNotExist:
            logger.error("模块不存在")
            await self.close()
            return

        self.session_id = str(id(self))

        if module.alive:
            logger.error("模块已在线")
            await self.close()
            return

        await self._bind_session(module)
        await self.accept()
        
        logger.info(f"模块 {module.module_hash} 连接成功")
        await self.channel_layer.group_add(
                f"module_{module.module_hash}",
                self.channel_name
            )

    async def disconnect(self, close_code):
        """断开连接：清理在线状态与会话"""
        try:
            module = await self._get_module_by_session(self.session_id)
        except WorkModule.DoesNotExist:
            return
            
        module.session_id = None
        module.alive = False
        # 更新模块 - 使用 sync_to_async 包装同步操作
        await sync_to_async(WorkModule.objects.filter(module_hash=module.module_hash).update)(
            session_id=module.session_id, 
            alive=module.alive
        )
        logger.info(f"模块 {module.module_hash} 断开连接")
        await self.channel_layer.group_discard(
                f"module_{module.module_hash}",
                self.channel_name
            )

    async def receive(self, text_data=None, bytes_data=None):
        """接收消息：处理心跳或JSON请求"""
        if text_data == "heartbeat":
            try:
                module = await self._get_module_by_session(self.session_id)
            except WorkModule.DoesNotExist:
                return
            module.last_alive_time = local_now()
            # 更新模块 - 使用 sync_to_async 包装同步操作
            await sync_to_async(WorkModule.objects.filter(module_hash=module.module_hash).update)(
                last_alive_time=module.last_alive_time
            )
            await self.send("heartbeat confirm")
        else:
            # 尝试解析JSON数据
            try:
                json_data = json.loads(text_data)
                logger.info(f"收到模块消息: {json_data}")
                
                # 处理模块执行结果
                await self._handle_module_result(json_data)
                
                # 返回处理结果
                await self.send("receive result")
                
            except json.JSONDecodeError:
                logger.error("JSON解析失败")
                await self.send(json.dumps({
                    'status': 'error',
                    'message': 'JSON格式错误'
                }))
            except Exception as e:
                logger.exception(f"处理请求时发生异常: {str(e)}")
                await self.send(json.dumps({
                    'status': 'error',
                    'message': f'处理请求时发生异常: {str(e)}'
                }))

    async def send_message(self, event):
        message = event['message']
        logger.info(f"向客户端发送消息: {message}")
        await self.send(text_data=json.dumps({
            'message': message
        }))

    async def _get_module(self, module_hash: str) -> WorkModule:
        return await WorkModule.objects.aget(module_hash=module_hash)

    async def _get_module_by_session(self, session_id: str) -> WorkModule:
        return await WorkModule.objects.aget(session_id=session_id)

    async def _bind_session(self, module: WorkModule):
        """绑定 WebSocket 会话到模块并记录时间戳"""
        module.session_id = self.session_id
        module.alive = True
        now = local_now()
        module.last_login_time = now
        module.last_alive_time = now
        # 更新模块 - 使用 sync_to_async 包装同步操作
        await sync_to_async(WorkModule.objects.filter(module_hash=module.module_hash).update)(
            session_id=module.session_id, 
            alive=module.alive, 
            last_login_time=module.last_login_time, 
            last_alive_time=module.last_alive_time
        )
    
    async def _handle_module_result(self, json_data: dict):
        """处理模块执行结果，如果失败则发送邮件通知"""
        try:
            # 检查是否是执行结果消息
            result_type = json_data.get("type")
            status = json_data.get("status")
            
            # 支持多种格式：type="result" 或直接包含 status 字段
            if result_type == "result" or "status" in json_data:
                # 检查执行状态是否为失败
                if status in ["failure", "failed", "error", "fail"]:
                    # 获取模块信息
                    try:
                        module = await self._get_module_by_session(self.session_id)
                    except WorkModule.DoesNotExist:
                        logger.warning("无法找到模块信息，跳过邮件通知")
                        return
                    
                    # 获取工作流信息（支持从 meta 字段或直接字段获取）
                    meta = json_data.get("meta", {})
                    workflow_id = json_data.get("workflow_id") or meta.get("workflow_id")
                    workflow_name = json_data.get("workflow_name") or meta.get("workflow_name") or "未知工作流"
                    module_name = json_data.get("module_name", module.name)
                    error_message = json_data.get("error") or json_data.get("message") or json_data.get("error_message") or "执行失败"
                    
                    # 发送邮件通知
                    await sync_to_async(send_module_execution_failure_notification)(
                        workflow_name=workflow_name,
                        workflow_id=workflow_id,
                        module_name=module_name,
                        module_hash=module.module_hash,
                        error_message=error_message,
                        failure_time=local_now()
                    )
                    
                    logger.warning(f"模块 {module_name} 执行失败，已发送邮件通知")
        except Exception as e:
            logger.exception(f"处理模块执行结果时发生异常: {str(e)}")




