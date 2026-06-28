"""MCP Client - 平台内建 MCP 客户端

连接 Agent MCP Server，执行能力发现 (initialize/tools/list) 和工具调用 (tools/call)。

MCP 组网流程:
1. 建立传输层连接 (stdio/SSE/WebSocket)
2. initialize 握手，交换能力声明
3. tools/list 发现 Agent 提供的能力
4. tools/call 调用 Agent 工具
5. resources/list + resources/read 读取 Agent 资源
"""

import asyncio
import logging
import uuid
from typing import Any, Optional

from app.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    MCPMethod,
    ToolSchema,
    ResourceSchema,
    PromptSchema,
    ServerCapabilities,
    InitializeResult,
    CapabilityManifest,
    JSONRPCErrorCode,
    make_error_response,
    make_success_response,
)
from app.mcp.transport import (
    MCPTransport,
    TransportConfig,
    TransportType,
    create_transport,
)

logger = logging.getLogger(__name__)


class MCPConnection:
    """单个 MCP 连接，代表平台与一个 Agent MCP Server 之间的会话"""

    def __init__(self, transport: MCPTransport, agent_id: str):
        self.transport = transport
        self.agent_id = agent_id
        self._initialized = False
        self._server_capabilities: ServerCapabilities | None = None
        self._tools: dict[str, ToolSchema] = {}
        self._resources: dict[str, ResourceSchema] = {}
        self._prompts: dict[str, PromptSchema] = {}
        self._pending_tasks: dict[str, asyncio.Future] = {}

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    async def initialize(self) -> InitializeResult:
        """执行 MCP initialize 握手"""
        request = JSONRPCRequest(
            method=MCPMethod.INITIALIZE,
            params={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "roots": {"listChanged": True},
                    "sampling": {},
                },
                "clientInfo": {"name": "aibond", "version": "1.3.0"},
            },
        )

        response = await self._send_and_wait(request)

        if isinstance(response, JSONRPCError):
            raise ConnectionError(f"Initialize failed: {response.error}")

        result = response.result
        self._server_capabilities = ServerCapabilities(**result.get("capabilities", {}))
        self._initialized = True

        # 发送 initialized 通知
        from app.mcp.protocol import JSONRPCNotification
        notification = JSONRPCNotification(method=MCPMethod.INITIALIZED)
        await self.transport.send(notification.model_dump(exclude_none=True))

        logger.info(f"[MCPConnection] Agent {self.agent_id} initialized: "
                     f"tools={self._server_capabilities.tools is not None}, "
                     f"resources={self._server_capabilities.resources is not None}, "
                     f"prompts={self._server_capabilities.prompts is not None}")

        return InitializeResult(**result)

    async def discover_tools(self) -> list[ToolSchema]:
        """发现 Agent 提供的所有 Tools"""
        if not self._initialized:
            raise RuntimeError("Connection not initialized")

        request = JSONRPCRequest(method=MCPMethod.TOOLS_LIST)
        response = await self._send_and_wait(request)

        if isinstance(response, JSONRPCError):
            raise RuntimeError(f"tools/list failed: {response.error}")

        tools = response.result.get("tools", [])
        self._tools = {}
        for tool_data in tools:
            tool = ToolSchema(**tool_data)
            self._tools[tool.name] = tool

        logger.info(f"[MCPConnection] Agent {self.agent_id}: discovered {len(self._tools)} tools")
        return list(self._tools.values())

    async def discover_resources(self) -> list[ResourceSchema]:
        """发现 Agent 提供的所有 Resources"""
        if not self._initialized:
            raise RuntimeError("Connection not initialized")

        request = JSONRPCRequest(method=MCPMethod.RESOURCES_LIST)
        response = await self._send_and_wait(request)

        if isinstance(response, JSONRPCError):
            logger.warning(f"resources/list failed: {response.error}")
            return []

        resources = response.result.get("resources", [])
        self._resources = {}
        for res_data in resources:
            res = ResourceSchema(**res_data)
            self._resources[res.uri] = res

        logger.info(f"[MCPConnection] Agent {self.agent_id}: discovered {len(self._resources)} resources")
        return list(self._resources.values())

    async def discover_prompts(self) -> list[PromptSchema]:
        """发现 Agent 提供的所有 Prompts"""
        if not self._initialized:
            raise RuntimeError("Connection not initialized")

        request = JSONRPCRequest(method=MCPMethod.PROMPTS_LIST)
        response = await self._send_and_wait(request)

        if isinstance(response, JSONRPCError):
            logger.warning(f"prompts/list failed: {response.error}")
            return []

        prompts = response.result.get("prompts", [])
        self._prompts = {}
        for prompt_data in prompts:
            prompt = PromptSchema(**prompt_data)
            self._prompts[prompt.name] = prompt

        logger.info(f"[MCPConnection] Agent {self.agent_id}: discovered {len(self._prompts)} prompts")
        return list(self._prompts.values())

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        """调用 Agent 的一个 Tool"""
        if not self._initialized:
            raise RuntimeError("Connection not initialized")

        if tool_name not in self._tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        request = JSONRPCRequest(
            method=MCPMethod.TOOLS_CALL,
            params={"name": tool_name, "arguments": arguments},
        )
        response = await self._send_and_wait(request)

        if isinstance(response, JSONRPCError):
            raise RuntimeError(f"tools/call '{tool_name}' failed: {response.error}")

        result = response.result
        content = result.get("content", [])
        is_error = result.get("isError", False)

        if is_error:
            raise RuntimeError(f"Tool '{tool_name}' returned error: {content}")

        return content

    async def read_resource(self, uri: str) -> dict:
        """读取 Agent 的一个 Resource"""
        if not self._initialized:
            raise RuntimeError("Connection not initialized")

        request = JSONRPCRequest(
            method=MCPMethod.RESOURCES_READ,
            params={"uri": uri},
        )
        response = await self._send_and_wait(request)

        if isinstance(response, JSONRPCError):
            raise RuntimeError(f"resources/read '{uri}' failed: {response.error}")

        return response.result

    async def get_prompt(self, prompt_name: str, arguments: dict | None = None) -> dict:
        """获取 Agent 的一个 Prompt"""
        if not self._initialized:
            raise RuntimeError("Connection not initialized")

        request = JSONRPCRequest(
            method=MCPMethod.PROMPTS_GET,
            params={"name": prompt_name, "arguments": arguments or {}},
        )
        response = await self._send_and_wait(request)

        if isinstance(response, JSONRPCError):
            raise RuntimeError(f"prompts/get '{prompt_name}' failed: {response.error}")

        return response.result

    async def full_discovery(self) -> CapabilityManifest:
        """执行完整的 Agent 能力发现流程"""
        init_result = await self.initialize()
        tools = await self.discover_tools()
        resources = await self.discover_resources()
        prompts = await self.discover_prompts()

        from app.mcp.protocol import ResourceTemplateSchema
        # 尝试获取 resource templates
        resource_templates = []
        try:
            request = JSONRPCRequest(method=MCPMethod.RESOURCES_TEMPLATES_LIST)
            response = await self._send_and_wait(request)
            if not isinstance(response, JSONRPCError):
                for tmpl_data in response.result.get("resourceTemplates", []):
                    resource_templates.append(ResourceTemplateSchema(**tmpl_data))
        except Exception:
            pass

        return CapabilityManifest(
            agent_id=self.agent_id,
            agent_name=init_result.serverInfo.name,
            transport=self.transport.config.transport_type.value,
            tools=tools,
            resources=resources,
            resource_templates=resource_templates,
            prompts=prompts,
            server_capabilities=self._server_capabilities or ServerCapabilities(),
        )

    async def _send_and_wait(self, request: JSONRPCRequest) -> JSONRPCResponse | JSONRPCError:
        """发送请求并等待响应"""
        try:
            result = await self.transport.send_request(
                request.model_dump(exclude_none=True)
            )
            if "error" in result:
                return JSONRPCError(**result)
            return JSONRPCResponse(**result)
        except TimeoutError:
            return make_error_response(
                request.id,
                JSONRPCErrorCode.INTERNAL_ERROR,
                "Request timed out",
            )
        except Exception as e:
            return make_error_response(
                request.id,
                JSONRPCErrorCode.INTERNAL_ERROR,
                str(e),
            )

    async def ping(self) -> bool:
        """发送 ping 检测连接状态"""
        try:
            request = JSONRPCRequest(method=MCPMethod.PING)
            response = await self._send_and_wait(request)
            return not isinstance(response, JSONRPCError)
        except Exception:
            return False


class MCPClient:
    """MCP 客户端管理器

    管理平台到多个 Agent MCP Server 的连接池。
    每个 Agent 对应一个 MCPConnection。
    """

    def __init__(self):
        self._connections: dict[str, MCPConnection] = {}
        self._manifests: dict[str, CapabilityManifest] = {}

    async def connect_agent(
        self,
        agent_id: str,
        transport_config: TransportConfig,
    ) -> MCPConnection:
        """建立与 Agent 的 MCP 连接"""
        if agent_id in self._connections:
            conn = self._connections[agent_id]
            if conn.transport.is_connected:
                return conn
            # 重新连接
            await conn.transport.disconnect()

        transport = create_transport(transport_config)
        await transport.connect()
        connection = MCPConnection(transport, agent_id)
        self._connections[agent_id] = connection

        logger.info(f"[MCPClient] Connected to agent {agent_id} via {transport_config.transport_type}")
        return connection

    async def discover_agent(self, agent_id: str) -> CapabilityManifest:
        """发现 Agent 的全部能力"""
        if agent_id not in self._connections:
            raise ValueError(f"Agent {agent_id} not connected")

        connection = self._connections[agent_id]
        manifest = await connection.full_discovery()
        self._manifests[agent_id] = manifest
        return manifest

    async def disconnect_agent(self, agent_id: str) -> None:
        """断开与 Agent 的连接"""
        if agent_id in self._connections:
            await self._connections[agent_id].transport.disconnect()
            del self._connections[agent_id]
        if agent_id in self._manifests:
            del self._manifests[agent_id]
        logger.info(f"[MCPClient] Disconnected agent {agent_id}")

    async def disconnect_all(self) -> None:
        """断开所有连接"""
        for agent_id in list(self._connections.keys()):
            await self.disconnect_agent(agent_id)

    def get_connection(self, agent_id: str) -> MCPConnection | None:
        """获取已建立的连接"""
        return self._connections.get(agent_id)

    def get_manifest(self, agent_id: str) -> CapabilityManifest | None:
        """获取已发现的 Agent 能力清单"""
        return self._manifests.get(agent_id)

    def list_connected_agents(self) -> list[str]:
        """列出所有已连接的 Agent"""
        return list(self._connections.keys())

    async def call_agent_tool(
        self,
        agent_id: str,
        tool_name: str,
        arguments: dict,
    ) -> Any:
        """调用指定 Agent 的工具"""
        connection = self._connections.get(agent_id)
        if not connection:
            raise ValueError(f"Agent {agent_id} not connected")
        return await connection.call_tool(tool_name, arguments)

    async def find_agents_with_tool(self, tool_name: str) -> list[str]:
        """查找提供指定工具的所有 Agent"""
        result = []
        for agent_id, manifest in self._manifests.items():
            for tool in manifest.tools:
                if tool.name == tool_name:
                    result.append(agent_id)
                    break
        return result

    async def find_agents_with_resource(self, uri_pattern: str) -> list[str]:
        """查找提供指定资源的所有 Agent"""
        result = []
        for agent_id, manifest in self._manifests.items():
            for resource in manifest.resources:
                if uri_pattern in resource.uri:
                    result.append(agent_id)
                    break
        return result


# 全局 MCP 客户端实例
global_mcp_client = MCPClient()