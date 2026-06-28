"""MCP 协议层 - JSON-RPC 2.0 消息类型与能力 Schema 定义

MCP (Model Context Protocol) 基于 JSON-RPC 2.0，定义了以下核心原语:
- Tools: 可调用的函数/工具
- Resources: 可读取的数据/文件
- Prompts: 预定义的提示模板
- Sampling: 服务端请求 LLM 采样（高级特性）
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# ============================================================
# JSON-RPC 2.0 消息类型
# ============================================================

class JSONRPCRequest(BaseModel):
    """JSON-RPC 2.0 请求"""
    jsonrpc: str = "2.0"
    id: str | int = Field(default_factory=lambda: str(uuid.uuid4()))
    method: str
    params: dict | None = None


class JSONRPCResponse(BaseModel):
    """JSON-RPC 2.0 成功响应"""
    jsonrpc: str = "2.0"
    id: str | int
    result: Any


class JSONRPCError(BaseModel):
    """JSON-RPC 2.0 错误响应"""
    jsonrpc: str = "2.0"
    id: str | int | None = None
    error: dict  # {"code": int, "message": str, "data": Any}


class JSONRPCNotification(BaseModel):
    """JSON-RPC 2.0 通知（无 id，无需响应）"""
    jsonrpc: str = "2.0"
    method: str
    params: dict | None = None


# ============================================================
# MCP 标准方法名
# ============================================================

class MCPMethod(str, Enum):
    """MCP 协议定义的标准方法"""
    # 生命周期
    INITIALIZE = "initialize"
    INITIALIZED = "notifications/initialized"
    PING = "ping"

    # Tools
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    TOOLS_LIST_CHANGED = "notifications/tools/list_changed"

    # Resources
    RESOURCES_LIST = "resources/list"
    RESOURCES_READ = "resources/read"
    RESOURCES_TEMPLATES_LIST = "resources/templates/list"
    RESOURCES_SUBSCRIBE = "resources/subscribe"
    RESOURCES_UNSUBSCRIBE = "resources/unsubscribe"
    RESOURCES_UPDATED = "notifications/resources/updated"
    RESOURCES_LIST_CHANGED = "notifications/resources/list_changed"

    # Prompts
    PROMPTS_LIST = "prompts/list"
    PROMPTS_GET = "prompts/get"
    PROMPTS_LIST_CHANGED = "notifications/prompts/list_changed"

    # Sampling (服务端请求 LLM)
    SAMPLING_CREATE_MESSAGE = "sampling/createMessage"

    # Roots
    ROOTS_LIST = "roots/list"
    ROOTS_LIST_CHANGED = "notifications/roots/list_changed"

    # Completion
    COMPLETION_COMPLETE = "completion/complete"

    # Logging
    LOGGING_SET_LEVEL = "logging/setLevel"
    LOGGING_MESSAGE = "notifications/message"


# ============================================================
# JSON-RPC 错误码
# ============================================================

class JSONRPCErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    # MCP 自定义错误码
    SERVER_NOT_INITIALIZED = -32002
    UNKNOWN_CAPABILITY = -32001


# ============================================================
# MCP 能力 Schema 定义
# ============================================================

class ToolInputSchema(BaseModel):
    """Tool 输入参数的 JSON Schema"""
    type: str = "object"
    properties: dict[str, dict] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolSchema(BaseModel):
    """MCP Tool 标准化描述"""
    name: str = Field(..., description="工具唯一名称")
    description: str = Field("", description="工具描述（供 LLM 理解）")
    inputSchema: ToolInputSchema = Field(default_factory=ToolInputSchema)
    annotations: dict | None = Field(None, description="元数据注解（如只读、破坏性等）")


class ResourceSchema(BaseModel):
    """MCP Resource 标准化描述"""
    uri: str = Field(..., description="资源 URI")
    name: str = Field(..., description="资源名称")
    description: str = Field("")
    mimeType: str = Field("text/plain", description="MIME 类型")
    size: int | None = Field(None, description="资源大小（字节）")


class ResourceTemplateSchema(BaseModel):
    """MCP Resource Template 描述"""
    uriTemplate: str = Field(..., description="URI 模板，如 test://resource/{id}")
    name: str = Field(..., description="模板名称")
    description: str = Field("")
    mimeType: str = Field("text/plain")


class PromptArgument(BaseModel):
    """Prompt 参数定义"""
    name: str
    description: str = ""
    required: bool = False


class PromptSchema(BaseModel):
    """MCP Prompt 标准化描述"""
    name: str = Field(..., description="提示词名称")
    description: str = Field("")
    arguments: list[PromptArgument] = Field(default_factory=list)


class PromptMessage(BaseModel):
    """Prompt 消息内容"""
    role: str = Field("user", description="user / assistant")
    content: Any = Field(..., description="文本或内容块")


class ServerCapabilities(BaseModel):
    """MCP Server 能力声明"""
    tools: dict | None = Field(None, description="是否支持 tools，可包含 listChanged")
    resources: dict | None = Field(None, description="是否支持 resources，可包含 subscribe/listChanged")
    prompts: dict | None = Field(None, description="是否支持 prompts，可包含 listChanged")
    logging: dict | None = Field(None)
    completion: dict | None = Field(None)


class ClientCapabilities(BaseModel):
    """MCP Client 能力声明"""
    roots: dict | None = Field(None, description="是否支持 roots，可包含 listChanged")
    sampling: dict | None = Field(None)


class Implementation(BaseModel):
    """客户端/服务端实现信息"""
    name: str = "aibond"
    version: str = "1.3.0"


class InitializeResult(BaseModel):
    """initialize 响应"""
    protocolVersion: str = "2024-11-05"
    capabilities: ServerCapabilities = Field(default_factory=ServerCapabilities)
    serverInfo: Implementation = Field(default_factory=Implementation)
    instructions: str | None = Field(None, description="给客户端的使用说明")


class CapabilityManifest(BaseModel):
    """Agent 完整能力清单（MCP 组网中的核心概念）"""
    agent_id: str
    agent_name: str
    transport: str = "websocket"  # stdio / sse / websocket / streamable_http
    endpoint: str | None = None  # 连接端点
    tools: list[ToolSchema] = Field(default_factory=list)
    resources: list[ResourceSchema] = Field(default_factory=list)
    resource_templates: list[ResourceTemplateSchema] = Field(default_factory=list)
    prompts: list[PromptSchema] = Field(default_factory=list)
    server_capabilities: ServerCapabilities = Field(default_factory=ServerCapabilities)
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_discovery_dict(self) -> dict:
        """转换为服务发现格式"""
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "transport": self.transport,
            "endpoint": self.endpoint,
            "tool_count": len(self.tools),
            "resource_count": len(self.resources),
            "prompt_count": len(self.prompts),
            "tool_names": [t.name for t in self.tools],
            "resource_names": [r.name for r in self.resources],
            "prompt_names": [p.name for p in self.prompts],
            "last_updated": self.last_updated,
            "capabilities": {
                "tools": self.server_capabilities.tools is not None,
                "resources": self.server_capabilities.resources is not None,
                "prompts": self.server_capabilities.prompts is not None,
            },
        }


# ============================================================
# 工具函数
# ============================================================

def make_error_response(
    request_id: str | int | None,
    code: int,
    message: str,
    data: Any = None,
) -> JSONRPCError:
    """构建 JSON-RPC 错误响应"""
    return JSONRPCError(
        id=request_id,
        error={"code": code, "message": message, "data": data},
    )


def make_success_response(request_id: str | int, result: Any) -> JSONRPCResponse:
    """构建 JSON-RPC 成功响应"""
    return JSONRPCResponse(id=request_id, result=result)


def is_jsonrpc_message(data: dict) -> bool:
    """判断是否为合法的 JSON-RPC 消息"""
    return data.get("jsonrpc") == "2.0" and "method" in data


def is_notification(data: dict) -> bool:
    """判断是否为 JSON-RPC 通知（无 id 字段）"""
    return is_jsonrpc_message(data) and "id" not in data


def is_request(data: dict) -> bool:
    """判断是否为 JSON-RPC 请求"""
    return is_jsonrpc_message(data) and "id" in data