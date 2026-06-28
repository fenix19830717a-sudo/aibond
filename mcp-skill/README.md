# aibond MCP Server

aibond 平台作为 MCP (Model Context Protocol) Server，对外暴露企业级人机协同能力。

## 安装

### 方式一：Claude Desktop 配置

在 Claude Desktop 的 `claude_desktop_config.json` 中添加：

```json
{
  "mcpServers": {
    "aibond": {
      "url": "https://aib2b.bond/api/mcp/sse"
    }
  }
}
```

### 方式二：Trae IDE 配置

在 Trae IDE 的 MCP 设置中添加 SSE 端点：

```
https://aib2b.bond/api/mcp/sse
```

## 可用工具

### 1. aibond.list_agents
列出平台所有可用 Agent 及其能力。

### 2. aibond.run_workflow
触发执行一个工作流。

**参数：**
- `workflow_id` (string): 工作流 ID
- `params` (object, 可选): 工作流参数

### 3. aibond.create_task
创建任务并分配给指定 Agent。

**参数：**
- `title` (string): 任务标题
- `description` (string): 任务描述
- `agent_id` (string): 分配的 Agent ID
- `priority` (string, 可选): 优先级 (low/medium/high/critical)

### 4. aibond.search_tools
跨 Agent 搜索可用工具。

**参数：**
- `query` (string): 搜索关键词
- `agent_id` (string, 可选): 限定 Agent

### 5. aibond.call_agent_tool
调用指定 Agent 的工具。

**参数：**
- `agent_id` (string): Agent ID
- `tool_name` (string): 工具名称
- `arguments` (object): 工具参数

## 协议

基于 MCP 2024-11-05 规范，JSON-RPC 2.0 消息格式。

## 许可证

MIT