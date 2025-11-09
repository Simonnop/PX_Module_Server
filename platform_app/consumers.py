import json
import logging
from datetime import datetime
from .utils import local_now
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import WorkModule

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




