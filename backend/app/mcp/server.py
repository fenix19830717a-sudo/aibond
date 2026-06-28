"""MCP Server - 平台作为 MCP Server 暴露能力

aibond 平台作为 MCP Server，对外暴露:
- 平台上的所有 Agent 能力（聚合后的 Tools/Resources/Prompts）
- 平台自身的工具（如 workfow 执行、任务调度）
- 通过 JSON-RPC 2.0 协议与外部 MCP Client 通信

外部 MCP Client（如 Claude Desktop、Trae IDE）可以通过此接口
发现并调用 aibond 平台上的 Agent 能力。
"""

import json
import logging
from typing import Any, Optional

from app.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    JSONRPCNotification,
    MCPMethod,
    JSONRPCErrorCode,
    ToolSchema,
    ToolInputSchema,
    ResourceSchema,
    PromptSchema,
    ServerCapabilities,
    InitializeResult,
    Implementation,
    make_error_response,
    make_success_response,
    is_request,
    is_notification,
)

logger = logging.getLogger(__name__)


class MCPServer:
    """MCP Server 实现

    处理来自外部 MCP Client 的 JSON-RPC 请求，路由到:
    - 平台自身的能力（平台工具）
    - 注册的 Agent 能力（通过 registry 和 client 代理调用）
    """

    def __init__(self, registry=None, mcp_client=None):
        self._registry = registry
        self._mcp_client = mcp_client
        self._initialized_sessions: set[str] = set()
        self._platform_tools: dict[str, ToolSchema] = {}
        self._platform_resources: dict[str, ResourceSchema] = {}
        self._platform_prompts: dict[str, PromptSchema] = {}

        # 注册平台自身工具
        self._register_platform_tools()

    def _register_platform_tools(self) -> None:
        """注册平台自身提供的工具"""
        # 工具: 列出所有 Agent
        self._platform_tools["aibond.list_agents"] = ToolSchema(
            name="aibond.list_agents",
            description="列出 aibond 平台上所有在线 Agent 及其能力",
            inputSchema=ToolInputSchema(
                properties={
                    "status": {"type": "string", "description": "筛选状态: online/offline/all"},
                },
            ),
        )

        # 工具: 运行 Workflow
        self._platform_tools["aibond.run_workflow"] = ToolSchema(
            name="aibond.run_workflow",
            description="在 aibond 平台上执行一个 Workflow",
            inputSchema=ToolInputSchema(
                properties={
                    "workflow_id": {"type": "string", "description": "Workflow ID"},
                },
                required=["workflow_id"],
            ),
        )

        # 工具: 创建任务
        self._platform_tools["aibond.create_task"] = ToolSchema(
            name="aibond.create_task",
            description="在 aibond 平台上创建一个任务并分配给 Agent",
            inputSchema=ToolInputSchema(
                properties={
                    "title": {"type": "string", "description": "任务标题"},
                    "description": {"type": "string", "description": "任务描述"},
                    "agent_id": {"type": "string", "description": "目标 Agent ID"},
                    "priority": {"type": "string", "description": "优先级: low/normal/high/urgent"},
                },
                required=["title", "agent_id"],
            ),
        )

        # 工具: 搜索工具
        self._platform_tools["aibond.search_tools"] = ToolSchema(
            name="aibond.search_tools",
            description="在 aibond 平台上搜索所有 Agent 提供的工具",
            inputSchema=ToolInputSchema(
                properties={
                    "query": {"type": "string", "description": "搜索关键词"},
                },
                required=["query"],
            ),
        )

        # 工具: 调用 Agent 工具
        self._platform_tools["aibond.call_agent_tool"] = ToolSchema(
            name="aibond.call_agent_tool",
            description="通过 aibond 平台调用指定 Agent 的工具",
            inputSchema=ToolInputSchema(
                properties={
                    "agent_id": {"type": "string", "description": "Agent ID"},
                    "tool_name": {"type": "string", "description": "工具名称"},
                    "arguments": {"type": "object", "description": "工具参数"},
                },
                required=["agent_id", "tool_name", "arguments"],
            ),
        )

    # ---- 消息处理入口 ----

    async def handle_message(self, raw_message: dict, session_id: str = "default") -> dict | None:
        """处理一条 JSON-RPC 消息，返回响应（如果是请求）或 None（如果是通知）

        这是 MCP Server 的主入口，外部 MCP Client 通过此方法交互。
        """
        try:
            if is_request(raw_message):
                return await self._handle_request(raw_message, session_id)
            elif is_notification(raw_message):
                await self._handle_notification(raw_message, session_id)
                return None
            else:
                return make_error_response(
                    None,
                    JSONRPCErrorCode.INVALID_REQUEST,
                    "Not a valid JSON-RPC message",
                ).model_dump()
        except Exception as e:
            logger.error(f"[MCPServer] Error handling message: {e}")
            request_id = raw_message.get("id")
            return make_error_response(
                request_id,
                JSONRPCErrorCode.INTERNAL_ERROR,
                str(e),
            ).model_dump()

    async def _handle_request(self, raw: dict, session_id: str) -> dict:
        """处理 JSON-RPC 请求"""
        request = JSONRPCRequest(**raw)
        method = request.method
        params = request.params or {}

        # 生命周期方法不需要 initialize 检查
        if method == MCPMethod.INITIALIZE:
            result = await self._handle_initialize(params)
            return make_success_response(request.id, result.model_dump()).model_dump()

        if method == MCPMethod.PING:
            return make_success_response(request.id, {}).model_dump()

        # 其他方法需要先初始化
        if session_id not in self._initialized_sessions:
            return make_error_response(
                request.id,
                JSONRPCErrorCode.SERVER_NOT_INITIALIZED,
                "Server not initialized. Call initialize first.",
            ).model_dump()

        try:
            # ---- Tools ----
            if method == MCPMethod.TOOLS_LIST:
                result = await self._handle_tools_list()
                return make_success_response(request.id, result).model_dump()

            elif method == MCPMethod.TOOLS_CALL:
                result = await self._handle_tools_call(params)
                return make_success_response(request.id, result).model_dump()

            # ---- Resources ----
            elif method == MCPMethod.RESOURCES_LIST:
                result = await self._handle_resources_list()
                return make_success_response(request.id, result).model_dump()

            elif method == MCPMethod.RESOURCES_READ:
                result = await self._handle_resources_read(params)
                return make_success_response(request.id, result).model_dump()

            # ---- Prompts ----
            elif method == MCPMethod.PROMPTS_LIST:
                result = await self._handle_prompts_list()
                return make_success_response(request.id, result).model_dump()

            elif method == MCPMethod.PROMPTS_GET:
                result = await self._handle_prompts_get(params)
                return make_success_response(request.id, result).model_dump()

            else:
                return make_error_response(
                    request.id,
                    JSONRPCErrorCode.METHOD_NOT_FOUND,
                    f"Unknown method: {method}",
                ).model_dump()

        except Exception as e:
            logger.error(f"[MCPServer] Method '{method}' error: {e}")
            return make_error_response(
                request.id,
                JSONRPCErrorCode.INTERNAL_ERROR,
                str(e),
            ).model_dump()

    async def _handle_notification(self, raw: dict, session_id: str) -> None:
        """处理 JSON-RPC 通知"""
        notification = JSONRPCNotification(**raw)
        method = notification.method

        if method == MCPMethod.INITIALIZED:
            self._initialized_sessions.add(session_id)
            logger.info(f"[MCPServer] Session {session_id} initialized")

        elif method == MCPMethod.ROOTS_LIST_CHANGED:
            logger.info(f"[MCPServer] Roots list changed (session: {session_id})")

        else:
            logger.debug(f"[MCPServer] Unhandled notification: {method}")

    # ---- 能力处理 ----

    async def _handle_initialize(self, params: dict) -> InitializeResult:
        """处理 initialize 请求"""
        client_info = params.get("clientInfo", {})
        logger.info(f"[MCPServer] Initialize from {client_info.get('name', 'unknown')} "
                     f"v{client_info.get('version', '?')}")

        return InitializeResult(
            protocolVersion="2024-11-05",
            capabilities=ServerCapabilities(
                tools={"listChanged": True},
                resources={"listChanged": True, "subscribe": False},
                prompts={"listChanged": True},
            ),
            serverInfo=Implementation(name="aibond-platform", version="1.3.0"),
            instructions=(
                "Welcome to aibond MCP Server. "
                "Use tools/list to discover all available tools from platform and connected agents. "
                "Use aibond.search_tools to find specific tools by keyword. "
                "Use aibond.call_agent_tool to invoke agent tools."
            ),
        )

    async def _handle_tools_list(self) -> dict:
        """聚合平台工具和所有 Agent 工具"""
        all_tools = []

        # 平台工具
        for tool in self._platform_tools.values():
            all_tools.append(tool.model_dump())

        # Agent 工具（从 registry）
        if self._registry:
            for agent_id in self._registry._manifests:
                manifest = self._registry.get_manifest(agent_id)
                if manifest:
                    for tool in manifest.tools:
                        # 加上 agent 前缀避免冲突
                        tool_dict = tool.model_dump()
                        tool_dict["name"] = f"{manifest.agent_name}.{tool.name}"
                        tool_dict["description"] = f"[Agent: {manifest.agent_name}] {tool.description}"
                        all_tools.append(tool_dict)

        return {"tools": all_tools}

    async def _handle_tools_call(self, params: dict) -> dict:
        """处理工具调用请求"""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        # 平台工具
        if tool_name.startswith("aibond."):
            result = await self._call_platform_tool(tool_name, arguments)
            return {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "isError": False,
            }

        # Agent 工具（通过 MCP Client 代理调用）
        # 格式: agent_name.tool_name
        if "." in tool_name and self._mcp_client and self._registry:
            parts = tool_name.split(".", 1)
            agent_name = parts[0]
            actual_tool_name = parts[1]

            # 通过 registry 找到 agent_id
            for agent_id, manifest in self._registry._manifests.items():
                if manifest.agent_name == agent_name:
                    try:
                        result = await self._mcp_client.call_agent_tool(
                            agent_id, actual_tool_name, arguments
                        )
                        return {
                            "content": result if isinstance(result, list)
                            else [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                            "isError": False,
                        }
                    except Exception as e:
                        return {
                            "content": [{"type": "text", "text": str(e)}],
                            "isError": True,
                        }

        return {
            "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
            "isError": True,
        }

    async def _call_platform_tool(self, tool_name: str, arguments: dict) -> dict:
        """执行平台自身工具"""
        if tool_name == "aibond.list_agents":
            if self._registry:
                agents = self._registry.list_all_agents()
            else:
                agents = []
            return {"agents": agents, "count": len(agents)}

        elif tool_name == "aibond.search_tools":
            if self._registry:
                results = self._registry.search_tools(arguments.get("query", ""))
            else:
                results = []
            return {"tools": results, "count": len(results)}

        elif tool_name == "aibond.create_task":
            return {"status": "created", "title": arguments.get("title"),
                    "agent_id": arguments.get("agent_id")}

        elif tool_name == "aibond.run_workflow":
            return {"status": "triggered", "workflow_id": arguments.get("workflow_id")}

        elif tool_name == "aibond.call_agent_tool":
            if self._mcp_client:
                try:
                    result = await self._mcp_client.call_agent_tool(
                        arguments["agent_id"],
                        arguments["tool_name"],
                        arguments.get("arguments", {}),
                    )
                    return {"result": result}
                except Exception as e:
                    return {"error": str(e)}
            return {"error": "MCP client not available"}

        return {"error": f"Unknown platform tool: {tool_name}"}

    async def _handle_resources_list(self) -> dict:
        """聚合平台资源和 Agent 资源"""
        all_resources = [r.model_dump() for r in self._platform_resources.values()]
        if self._registry:
            for agent_id in self._registry._manifests:
                manifest = self._registry.get_manifest(agent_id)
                if manifest:
                    for res in manifest.resources:
                        all_resources.append(res.model_dump())
        return {"resources": all_resources}

    async def _handle_resources_read(self, params: dict) -> dict:
        """读取资源"""
        uri = params.get("uri", "")
        if uri in self._platform_resources:
            return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": "Platform resource"}]}
        return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f"Resource not found: {uri}"}]}

    async def _handle_prompts_list(self) -> dict:
        """聚合平台提示词和 Agent 提示词"""
        all_prompts = [p.model_dump() for p in self._platform_prompts.values()]
        if self._registry:
            for agent_id in self._registry._manifests:
                manifest = self._registry.get_manifest(agent_id)
                if manifest:
                    for prompt in manifest.prompts:
                        all_prompts.append(prompt.model_dump())
        return {"prompts": all_prompts}

    async def _handle_prompts_get(self, params: dict) -> dict:
        """获取提示词"""
        name = params.get("name", "")
        return {"messages": [{"role": "user", "content": {"type": "text", "text": f"Prompt: {name}"}}]}


# 全局 MCP Server 实例
global_mcp_server = MCPServer(registry=None, mcp_client=None)

def init_mcp_server(registry, mcp_client):
    """初始化全局 MCP Server，注入 registry 和 mcp_client"""
    global global_mcp_server
    global_mcp_server = MCPServer(registry=registry, mcp_client=mcp_client)