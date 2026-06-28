"""MCP 传输层 - 多传输协议支持

MCP 支持三种标准传输:
- stdio: 本地进程间通信，通过 stdin/stdout 交换 JSON-RPC
- SSE: Server-Sent Events，HTTP 长连接，服务端推送
- Streamable HTTP: 模块化 HTTP 传输（2025 年新标准）
- WebSocket: aibond 扩展，用于 Agent 实时双向通信

每种传输实现 MCPTransport 抽象接口。
"""

import asyncio
import json
import logging
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Optional

import aiohttp

logger = logging.getLogger(__name__)


class TransportType(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    WEBSOCKET = "websocket"
    STREAMABLE_HTTP = "streamable_http"


@dataclass
class TransportConfig:
    """传输层配置"""
    transport_type: TransportType
    # stdio 配置
    command: str | None = None  # 可执行文件路径
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    # SSE / Streamable HTTP 配置
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    # WebSocket 配置
    ws_url: str | None = None
    # 通用
    timeout: float = 30.0
    max_retries: int = 3


class MCPTransport(ABC):
    """MCP 传输层抽象基类"""

    def __init__(self, config: TransportConfig):
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """建立连接"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接"""
        ...

    @abstractmethod
    async def send(self, message: dict) -> None:
        """发送 JSON-RPC 消息"""
        ...

    @abstractmethod
    async def receive(self) -> dict:
        """接收一条 JSON-RPC 消息"""
        ...

    async def send_request(self, request: dict) -> dict:
        """发送请求并等待响应"""
        await self.send(request)
        return await self.receive()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()


class StdioTransport(MCPTransport):
    """stdio 传输：通过标准输入输出与子进程通信

    适用场景：本地 Agent 进程，如 Python/Node.js MCP Server
    """

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._process: subprocess.Popen | None = None
        self._reader_task: asyncio.Task | None = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._buffer = ""

    async def connect(self) -> None:
        if not self.config.command:
            raise ValueError("stdio transport requires 'command' in config")

        cmd = [self.config.command] + self.config.args
        logger.info(f"[StdioTransport] Starting process: {' '.join(cmd)}")

        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # 启动异步读取 stdout
        self._reader_task = asyncio.create_task(self._read_stdout())
        self._connected = True
        logger.info("[StdioTransport] Connected")

    async def disconnect(self) -> None:
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        logger.info("[StdioTransport] Disconnected")

    async def send(self, message: dict) -> None:
        if not self._process or not self._process.stdin:
            raise ConnectionError("stdio transport not connected")
        data = json.dumps(message, ensure_ascii=False) + "\n"
        self._process.stdin.write(data)
        self._process.stdin.flush()

    async def receive(self) -> dict:
        try:
            return await asyncio.wait_for(
                self._message_queue.get(),
                timeout=self.config.timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError("stdio transport receive timeout")

    async def _read_stdout(self) -> None:
        """持续读取子进程 stdout，按行解析 JSON-RPC 消息"""
        loop = asyncio.get_event_loop()
        while self._connected and self._process and self._process.stdout:
            try:
                line = await loop.run_in_executor(
                    None, self._process.stdout.readline
                )
                if not line:
                    logger.warning("[StdioTransport] Process stdout closed")
                    self._connected = False
                    break
                line = line.strip()
                if line:
                    try:
                        message = json.loads(line)
                        await self._message_queue.put(message)
                    except json.JSONDecodeError:
                        logger.warning(f"[StdioTransport] Invalid JSON: {line[:100]}")
            except Exception as e:
                logger.error(f"[StdioTransport] Read error: {e}")
                break


class SSETransport(MCPTransport):
    """SSE 传输：通过 HTTP Server-Sent Events 进行远程通信

    适用场景：远程 Agent MCP Server，通过 HTTP 长连接推送事件
    """

    def __init__(self, config: TransportConfig):
        super().__init__(config)
        self._session: aiohttp.ClientSession | None = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._sse_task: asyncio.Task | None = None
        self._endpoint: str = ""

    async def connect(self) -> None:
        if not self.config.url:
            raise ValueError("SSE transport requires 'url' in config")

        self._session = aiohttp.ClientSession(headers=self.config.headers)
        self._endpoint = self.config.url.rstrip("/")

        # 发送 initialize 请求
        init_request = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": {"name": "aibond", "version": "1.3.0"},
            },
        }

        # 通过 POST /message 发送初始化请求
        message_url = f"{self._endpoint}/message"
        async with self._session.post(message_url, json=init_request) as resp:
            if resp.status != 200:
                raise ConnectionError(f"SSE initialize failed: HTTP {resp.status}")
            init_result = await resp.json()
            logger.info(f"[SSETransport] Initialized: {init_result.get('result', {}).get('serverInfo', {})}")

        # 发送 initialized 通知
        initialized = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        async with self._session.post(message_url, json=initialized) as resp:
            pass

        # 启动 SSE 事件流监听
        self._sse_task = asyncio.create_task(self._listen_sse())
        self._connected = True
        logger.info("[SSETransport] Connected")

    async def disconnect(self) -> None:
        self._connected = False
        if self._sse_task:
            self._sse_task.cancel()
            try:
                await self._sse_task
            except asyncio.CancelledError:
                pass
        if self._session:
            await self._session.close()
            self._session = None
        logger.info("[SSETransport] Disconnected")

    async def send(self, message: dict) -> None:
        if not self._session:
            raise ConnectionError("SSE transport not connected")
        message_url = f"{self._endpoint}/message"
        async with self._session.post(message_url, json=message) as resp:
            if resp.status not in (200, 202):
                text = await resp.text()
                raise ConnectionError(f"SSE send failed: HTTP {resp.status}: {text[:200]}")
            # 如果是请求（有 id），读取响应
            if "id" in message:
                result = await resp.json()
                await self._message_queue.put(result)

    async def receive(self) -> dict:
        try:
            return await asyncio.wait_for(
                self._message_queue.get(),
                timeout=self.config.timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError("SSE transport receive timeout")

    async def _listen_sse(self) -> None:
        """监听 SSE 事件流（服务端主动推送）"""
        if not self._session:
            return
        sse_url = f"{self._endpoint}/sse"
        try:
            async with self._session.get(sse_url) as resp:
                if resp.status != 200:
                    logger.warning(f"[SSETransport] SSE stream failed: HTTP {resp.status}")
                    return
                async for line in resp.content:
                    if not self._connected:
                        break
                    line_text = line.decode("utf-8").strip()
                    if line_text.startswith("data: "):
                        data_str = line_text[6:]
                        try:
                            message = json.loads(data_str)
                            await self._message_queue.put(message)
                        except json.JSONDecodeError:
                            logger.warning(f"[SSETransport] Invalid SSE data: {data_str[:100]}")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[SSETransport] SSE listen error: {e}")


class WebSocketTransport(MCPTransport):
    """WebSocket 传输：通过 WebSocket 进行双向实时通信

    aibond 扩展传输，用于 Agent 与平台之间的 MCP 协议通信。
    使用 aibond 现有的 WebSocket 连接管理器。
    """

    def __init__(self, config: TransportConfig, ws_manager=None):
        super().__init__(config)
        self._ws_manager = ws_manager
        self._agent_id: str | None = None
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._pending_requests: dict[str, asyncio.Future] = {}

    async def connect(self) -> None:
        # WebSocket 传输由 agent_handler 管理连接，这里不需要主动连接
        self._connected = True
        logger.info("[WebSocketTransport] Ready (managed by agent_handler)")

    async def disconnect(self) -> None:
        self._connected = False
        # 取消所有等待中的请求
        for req_id, future in self._pending_requests.items():
            if not future.done():
                future.set_exception(ConnectionError("WebSocket disconnected"))
        self._pending_requests.clear()
        logger.info("[WebSocketTransport] Disconnected")

    async def send(self, message: dict) -> None:
        if not self._ws_manager or not self._agent_id:
            raise ConnectionError("WebSocket transport not connected to agent")
        await self._ws_manager.send_to_agent(self._agent_id, message)

    async def receive(self) -> dict:
        try:
            return await asyncio.wait_for(
                self._message_queue.get(),
                timeout=self.config.timeout,
            )
        except asyncio.TimeoutError:
            raise TimeoutError("WebSocket transport receive timeout")

    def set_agent_id(self, agent_id: str):
        self._agent_id = agent_id

    def set_ws_manager(self, ws_manager):
        self._ws_manager = ws_manager

    async def handle_incoming_message(self, message: dict) -> None:
        """处理来自 Agent 的 WebSocket 消息"""
        # 如果消息包含 id 且是响应，匹配到 pending request
        if "id" in message and "method" not in message:
            req_id = message["id"]
            future = self._pending_requests.pop(req_id, None)
            if future and not future.done():
                future.set_result(message)
                return
        # 否则放入通用队列
        await self._message_queue.put(message)

    async def send_request(self, request: dict) -> dict:
        """发送请求并等待响应（WebSocket 模式）"""
        req_id = request.get("id")
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        if req_id:
            self._pending_requests[req_id] = future
        await self.send(request)
        try:
            return await asyncio.wait_for(future, timeout=self.config.timeout)
        except asyncio.TimeoutError:
            self._pending_requests.pop(req_id, None)
            raise TimeoutError("WebSocket request timeout")


def create_transport(config: TransportConfig, **kwargs) -> MCPTransport:
    """工厂函数：根据配置创建对应的传输实例"""
    transport_map = {
        TransportType.STDIO: StdioTransport,
        TransportType.SSE: SSETransport,
        TransportType.WEBSOCKET: WebSocketTransport,
        TransportType.STREAMABLE_HTTP: SSETransport,  # 暂用 SSE 实现
    }
    transport_cls = transport_map.get(config.transport_type)
    if not transport_cls:
        raise ValueError(f"Unsupported transport type: {config.transport_type}")
    return transport_cls(config, **kwargs) if kwargs else transport_cls(config)