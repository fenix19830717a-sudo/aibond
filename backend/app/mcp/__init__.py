"""MCP (Model Context Protocol) 组网模块

为 aibond 平台提供 MCP 标准协议支持，实现：
- JSON-RPC 2.0 消息协议
- 多传输层支持 (stdio, SSE, WebSocket, Streamable HTTP)
- MCP Client（平台连接 Agent MCP Server）
- MCP Server（平台暴露能力给外部 MCP Client）
- 统一能力注册中心 (Tools / Resources / Prompts)
"""

from app.mcp.protocol import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    JSONRPCNotification,
    MCPMethod,
    ToolSchema,
    ResourceSchema,
    PromptSchema,
    CapabilityManifest,
)
from app.mcp.transport import (
    TransportType,
    MCPTransport,
    StdioTransport,
    SSETransport,
    WebSocketTransport,
    create_transport,
)
from app.mcp.client import MCPClient, MCPConnection
from app.mcp.registry import MCPRegistry, global_registry
from app.mcp.server import MCPServer

__all__ = [
    # Protocol
    "JSONRPCRequest", "JSONRPCResponse", "JSONRPCError", "JSONRPCNotification",
    "MCPMethod", "ToolSchema", "ResourceSchema", "PromptSchema", "CapabilityManifest",
    # Transport
    "TransportType", "MCPTransport", "StdioTransport", "SSETransport",
    "WebSocketTransport", "create_transport",
    # Client
    "MCPClient", "MCPConnection",
    # Registry
    "MCPRegistry", "global_registry",
    # Server
    "MCPServer",
]