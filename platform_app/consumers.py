import json
import logging
from datetime import datetime
from .utils import local_now
from .email import send_module_execution_failure_notification
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import WorkModule, WorkFlow
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

# 说明（类比 Spring WebSocket/STOMP）：
# - `AsyncWebsocketConsumer` 处理 WS 生命周期：connect/receive/disconnect。
# - 通过查询参数 `hash` 识别模块，并在连接时绑定会话。

# 跟踪模块执行等待状态：{execution_id: {'module_id': int, 'workflow_id': str, 'sent_time': datetime}}
global _execution_waiting 
_execution_waiting = {}

def send_message_to_client(module_id, message):
    """同步方式发送消息到客户端"""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"module_{module_id}",
        {
            "type": "send_message", # 反射? 对应触发 consumers.py 中的 send_message 方法
            "message": message
        }
    )

def close_module_websocket(module_id):
    """服务端关闭指定模块的 WebSocket 连接
    
    Args:
        module_id: 模块ID
    
    Returns:
        bool: 是否成功发送关闭连接消息
    """
    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            logger.error("Channel Layer 未配置，无法关闭 WebSocket 连接")
            return False
        
        async_to_sync(channel_layer.group_send)(
            f"module_{module_id}",
            {
                "type": "close_connection"  # 触发 close_connection 方法
            }
        )
        # 获取模块信息用于日志
        from .models import WorkModule
        try:
            module = WorkModule.objects.get(module_id=module_id)
            logger.info(f"已发送关闭 WebSocket 连接消息到模块 {module.name}(id: {module_id})")
        except WorkModule.DoesNotExist:
            logger.info(f"已发送关闭 WebSocket 连接消息到模块 (id: {module_id})")
        return True
    except Exception as e:
        # 获取模块信息用于日志
        from .models import WorkModule
        try:
            module = WorkModule.objects.get(module_id=module_id)
            logger.error(f"关闭模块 {module.name}(id: {module_id}) 的 WebSocket 连接失败: {str(e)}", exc_info=True)
        except WorkModule.DoesNotExist:
            logger.error(f"关闭模块 (id: {module_id}) 的 WebSocket 连接失败: {str(e)}", exc_info=True)
        return False

def clear_execution_waiting(execution_id):
    """清除执行等待状态"""
    try:
        if execution_id in _execution_waiting:
            _execution_waiting.pop(execution_id)
            logger.debug(f"已清除执行ID {execution_id} 的等待状态")
    except Exception as e:
        logger.warning(f"清除执行等待状态失败 (执行ID: {execution_id}): {str(e)}")

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
        
        logger.info(f"模块 {module.name}(id: {module.module_id}) 连接成功")
        await self.channel_layer.group_add(
                f"module_{module.module_id}",
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
        await sync_to_async(WorkModule.objects.filter(module_id=module.module_id).update)(
            session_id=module.session_id, 
            alive=module.alive
        )
        logger.info(f"模块 {module.name}(id: {module.module_id}) 断开连接")
        await self.channel_layer.group_discard(
                f"module_{module.module_id}",
                self.channel_name
            )

    async def receive(self, text_data=None, bytes_data=None):
        """接收消息：处理JSON请求或WebSocket ping/pong"""
        # 每次收到消息时更新 last_alive_time（表示连接活跃）
        # WebSocket ping/pong 帧也会触发此方法，但 text_data 和 bytes_data 可能为 None
        await self._update_alive_time()
        
        # WebSocket ping/pong 由底层自动处理，这里只处理业务消息
        if text_data is None or text_data.strip() == "":
            # 可能是 ping 帧或空消息，由 WebSocket 协议自动处理
            return
        
        # 检查是否是已知的非 JSON 消息（如 ping/pong 相关的文本消息）
        text_data_stripped = text_data.strip()
        if text_data_stripped.lower() in ['ping', 'pong']:
            # 静默处理 ping/pong 文本消息，不记录错误
            return
        
        # 尝试解析JSON数据
        try:
            json_data = json.loads(text_data)
            
            # 处理模块执行结果
            await self._handle_module_result(json_data)
            
            # 返回处理结果
            await self.send("receive result")
            
        except json.JSONDecodeError:
            # JSON 解析失败，记录警告而不是错误（可能是客户端发送了非预期的消息格式）
            logger.warning(f"收到非 JSON 格式的消息: {text_data[:100] if len(text_data) > 100 else text_data}")
            await self.send(json.dumps({
                'status': 'error',
                'message': 'JSON格式错误，请发送有效的 JSON 格式消息'
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
    
    async def close_connection(self, event=None):
        """服务端主动关闭 WebSocket 连接
        
        Args:
            event: Channels 事件对象（可选）
        """
        try:
            # 更新模块状态为离线
            try:
                module = await self._get_module_by_session(self.session_id)
                module.session_id = None
                module.alive = False
                await sync_to_async(WorkModule.objects.filter(module_id=module.module_id).update)(
                    session_id=module.session_id, 
                    alive=module.alive
                )
                logger.info(f"服务端主动断开模块 {module.name}(id: {module.module_id}) 的 WebSocket 连接")
            except WorkModule.DoesNotExist:
                logger.warning("无法找到模块信息，直接关闭连接")
            
            # 从 group 中移除
            if hasattr(self, 'session_id'):
                try:
                    module = await self._get_module_by_session(self.session_id)
                    await self.channel_layer.group_discard(
                        f"module_{module.module_id}",
                        self.channel_name
                    )
                except WorkModule.DoesNotExist:
                    pass
            
            # 主动关闭连接
            await self.close()
        except Exception as e:
            logger.error(f"关闭连接时发生异常: {str(e)}", exc_info=True)
            await self.close()

    async def _get_module(self, module_hash: str) -> WorkModule:
        return await WorkModule.objects.aget(module_hash=module_hash)

    async def _get_module_by_session(self, session_id: str) -> WorkModule:
        return await WorkModule.objects.aget(session_id=session_id)

    async def _update_alive_time(self):
        """更新模块的 last_alive_time（在收到 ping/pong 或任何消息时调用）"""
        try:
            module = await self._get_module_by_session(self.session_id)
            now = local_now()
            # 更新 last_alive_time - 使用 sync_to_async 包装同步操作
            await sync_to_async(WorkModule.objects.filter(module_id=module.module_id).update)(
                last_alive_time=now
            )
        except WorkModule.DoesNotExist:
            # 模块不存在，忽略
            pass
        except Exception as e:
            logger.warning(f"更新模块存活时间失败: {str(e)}")
    
    async def _bind_session(self, module: WorkModule):
        """绑定 WebSocket 会话到模块并记录时间戳"""
        module.session_id = self.session_id
        module.alive = True
        now = local_now()
        module.last_login_time = now
        module.last_alive_time = now
        # 更新模块 - 使用 sync_to_async 包装同步操作
        await sync_to_async(WorkModule.objects.filter(module_id=module.module_id).update)(
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
            
            # 获取执行ID（如果存在）
            meta = json_data.get("meta", {})
            execution_id = json_data.get("execution_id") or meta.get("execution_id")
            
            # 如果收到执行结果，清除超时等待状态
            if execution_id:
                await sync_to_async(clear_execution_waiting)(execution_id)
                logger.info(f"收到合法回复信息: {json_data}")
            
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
                    workflow_id = json_data.get("workflow_id") or meta.get("workflow_id")
                    workflow_name = json_data.get("workflow_name") or meta.get("workflow_name") or "未知工作流"
                    module_name = json_data.get("module_name", module.name)
                    error_message = json_data.get("error") or json_data.get("message") or json_data.get("error_message") or "执行失败"
                    
                    # 发送邮件通知
                    await sync_to_async(send_module_execution_failure_notification)(
                        workflow_name=workflow_name,
                        workflow_id=workflow_id,
                        module_name=module_name,
                        module_id=module.module_id,
                        error_message=error_message,
                        failure_time=local_now()
                    )
                    
                    logger.warning(f"模块 {module_name}(id: {module.module_id}) 执行失败，已发送邮件通知")
        except Exception as e:
            logger.exception(f"处理模块执行结果时发生异常: {str(e)}")




