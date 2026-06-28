mcp-name: io.github.fenix19830717a-sudo/aibond

# aibond MCP Server

aibond 平台作为 MCP (Model Context Protocol) Server，对外暴露企业级人机协同能力。

## 安装

### Claude Desktop

在 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "aibond": {
      "url": "https://aib2b.bond/api/mcp/sse"
    }
  }
}
```

### Trae IDE

在 Trae IDE 的 MCP 设置中添加 SSE 端点：`https://aib2b.bond/api/mcp/sse`

## 可用工具

| 工具 | 说明 |
|------|------|
| `aibond.list_agents` | 列出平台所有 Agent 及其能力 |
| `aibond.run_workflow` | 执行 Workflow |
| `aibond.create_task` | 创建并分配任务 |
| `aibond.search_tools` | 跨 Agent 搜索工具 |
| `aibond.call_agent_tool` | 调用 Agent 工具 |

## 协议

MCP 2024-11-05 (JSON-RPC 2.0)，传输层：Streamable HTTP (SSE)

## 许可证

MIT