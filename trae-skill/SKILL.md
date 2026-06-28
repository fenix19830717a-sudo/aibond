---
name: aibond
description: 企业级人机协同平台技能。当用户需要多 Agent 协作、MCP 组网、Workflow 编排、Parliament 议会决策、Agent 管理、任务调度时使用此技能。触发关键词：agent、workflow、mcp、parliament、多agent、工作流、任务编排、人机协同。
---

# aibond - 企业级人机协同平台

## 描述

aibond 是一个企业级人机协同平台，提供多 Agent 协作、MCP 组网、Workflow 编排和 Parliament 议会决策能力。通过 MCP 协议与外部 AI 客户端集成，实现跨平台的人机协同工作流。

## 核心能力

### 1. Agent 管理
- 通过 WebSocket 实时连接 Agent
- 双认证体系：JWT + API Key
- 动态能力注册与发现
- 离线消息投递

### 2. MCP 组网
- 完整 JSON-RPC 2.0 协议实现
- 3 种传输层：stdio / SSE / WebSocket
- 统一能力注册中心（倒排索引）
- 跨 Agent 工具搜索与调用

### 3. Workflow 引擎
- 8 种节点类型：trigger / ai / human_review / condition / output / parallel / webhook / event_watcher
- 12 个预置模板（Hermes 5 层架构）
- 自然语言 Cron 解析器

### 4. Parliament 议会决策
- 5 角色架构：Arbiter / Reviewer / Analyst / Executor / Observer
- 加权投票、交叉验证、置信度升级

## 使用场景

- 需要多个 AI Agent 协作完成复杂任务时
- 需要编排自动化工作流时
- 需要跨 Agent 搜索和调用工具时
- 需要结构化决策（议会投票）时
- 需要将外部 AI 客户端接入平台时

## 连接方式

### 外部 MCP Client 配置

```json
{
  "mcpServers": {
    "aibond": {
      "url": "https://aib2b.bond/api/mcp/sse"
    }
  }
}
```

### Agent SDK 接入

```python
from aibond_agent import AgentClient

client = AgentClient(
    server_url="ws://localhost:8100/ws",
    api_key="your-api-key"
)
client.connect()
```

## 指令

当用户请求 aibond 相关操作时：

1. **连接平台**：确认 MCP 端点配置正确
2. **列出 Agent**：使用 `aibond.list_agents` 查看可用 Agent
3. **搜索工具**：使用 `aibond.search_tools` 查找所需工具
4. **执行工作流**：使用 `aibond.run_workflow` 触发工作流
5. **创建任务**：使用 `aibond.create_task` 分配任务给 Agent
6. **调用 Agent 工具**：使用 `aibond.call_agent_tool` 调用指定 Agent 的工具

## 失败策略

- 连接失败：检查 MCP 端点 URL 和 API Key 配置
- 工具调用失败：确认 Agent 在线且工具名正确
- 工作流执行失败：检查工作流 ID 和参数格式
- 超时：增加超时时间或检查网络连接

## 参考

- 平台地址：https://aib2b.bond
- GitHub：https://github.com/fenix19830717a-sudo/aibond
- MCP 规范：https://modelcontextprotocol.io