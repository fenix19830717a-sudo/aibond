# aibond — 企业级人机协同平台

> 多 Agent 协作、MCP 组网、Workflow 编排、Parliament 议会决策

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.2-61DAFB?logo=react)](https://react.dev/)
[![MCP](https://img.shields.io/badge/MCP-2024--11--05-blue)](https://modelcontextprotocol.io/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

---

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│                    aibond Platform                     │
│                                                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │  Agent   │  │ Workflow │  │     Parliament        │ │
│  │  Manager │  │  Engine  │  │  (多Agent议会决策)     │ │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘ │
│       │              │                   │             │
│  ┌────┴──────────────┴───────────────────┴───────────┐ │
│  │              MCP 组网层 (Model Context Protocol)    │ │
│  │   Registry │ Client │ Server │ Transport (stdio/SSE/WS) │
│  └────────────────────────────────────────────────────┘ │
│                         │                               │
│  ┌──────────────────────┴──────────────────────────────┐│
│  │  WebSocket Hub │ REST API │ JWT Auth │ Rate Limit   ││
│  └─────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────┘
```

## 核心特性

### Agent 管理
- WebSocket 长连接，支持 Agent 实时双向通信
- 双认证体系：用户 JWT + Agent API Key (`abk_xxx`)
- 动态能力注册：Agent 连接后自动声明 skills、工具、资源
- 离线消息投递：Agent 离线期间消息不丢失

### MCP 组网 (v1.3.0)
- 完整实现 JSON-RPC 2.0 协议，兼容 MCP 2024-11-05 规范
- 3 种传输层：`stdio`（本地进程）、`SSE`（远程 HTTP 长连接）、`WebSocket`（aibond 扩展）
- 统一能力注册中心：Tools/Resources/Prompts 倒排索引
- 平台作为 MCP Server：对外暴露 5 个平台工具 + 聚合所有 Agent 能力
- 外部 MCP Client（Claude Desktop / Trae IDE）可直接连接

### Workflow 引擎
- 8 种节点类型：`trigger` / `ai` / `human_review` / `condition` / `output` / `parallel` / `webhook` / `event_watcher`
- 12 个预置模板（Hermes 5 层架构：定时任务 → 智能监控 → 任务执行 → 多Agent协作 → 持续进化）
- 自然语言 Cron 解析器（"每天早上8点" → `0 8 * * *`）
- Kanban 可视化任务调度

### Parliament 议会决策
- 5 角色架构：Arbiter / Reviewer / Analyst / Executor / Observer
- 加权投票、交叉验证、置信度升级、分级模型路由
- 提案 → 审议 → 投票 → 共识 → 执行，全流程自动化

### 安全体系
- JWT 双令牌（Access 15min + Refresh 7天）
- CSP / HSTS 安全头
- 登录锁定 + 速率限制
- 全端点鉴权（`get_current_actor` 双认证）
- 审计日志（所有关键操作）

## 快速开始

### 环境要求
- Python 3.10+
- Node.js 20+
- SQLite（开发）/ PostgreSQL（生产）

### 后端启动

```bash
cd backend
pip install -r requirements.txt
python run.py
# 启动后访问 http://localhost:8100
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
# 启动后访问 http://localhost:5173
```

### Agent SDK

```bash
pip install aibond-agent
```

```python
from aibond_agent import AgentClient

client = AgentClient(
    server_url="ws://localhost:8100/ws",
    api_key="your-api-key"
)
client.connect()
```

## 项目结构

```
aibond/
├── backend/                  # FastAPI 后端
│   └── app/
│       ├── mcp/              # MCP 组网模块
│       │   ├── protocol.py   #   JSON-RPC 2.0 协议
│       │   ├── transport.py  #   stdio/SSE/WebSocket 传输
│       │   ├── client.py     #   MCP 客户端
│       │   ├── registry.py   #   能力注册中心
│       │   └── server.py     #   MCP 服务端
│       ├── parliament/       # 议会决策引擎
│       ├── workflows/        # Workflow 引擎
│       │   ├── engine.py     #   8 节点执行引擎
│       │   ├── nl_cron.py    #   自然语言 Cron 解析
│       │   └── templates.py  #   12 预置模板
│       ├── websocket/        # WebSocket 通信
│       ├── routers/          # 17 个路由模块
│       ├── models/           # 数据模型
│       └── security.py       # 安全模块
├── frontend/                 # React 19 前端
│   └── src/
│       ├── pages/            # 页面组件
│       ├── api/              # API 客户端
│       └── components/       # 通用组件
├── aibond-agent/             # Agent SDK (Python)
└── docs/                     # 设计文档
```

## MCP 组网 API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/mcp/message` | POST | JSON-RPC 消息处理 |
| `/api/mcp/sse` | GET | SSE 事件流 |
| `/api/mcp/discovery` | GET | 服务发现 |
| `/api/mcp/register-tools` | POST | Agent 注册能力 |
| `/api/mcp/search-tools` | POST | 跨 Agent 工具搜索 |
| `/api/mcp/call-tool` | POST | 代理工具调用 |
| `/api/hub/mcp/discovery` | GET | Hub MCP 发现 |

### 外部 MCP Client 配置示例

```json
{
  "mcpServers": {
    "aibond": {
      "url": "https://aib2b.bond/api/mcp/sse"
    }
  }
}
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI 0.115 + Uvicorn |
| 数据库 | SQLAlchemy 2.0 + SQLite / PostgreSQL |
| 认证 | JWT (HS256) + bcrypt |
| 实时通信 | WebSocket (websockets 12.0) |
| 前端框架 | React 19.2 + TypeScript |
| UI 组件 | Ant Design 5 |
| 构建工具 | Vite |
| 协议 | MCP 2024-11-05 (JSON-RPC 2.0) |

## 版本历史

| 版本 | 日期 | 关键更新 |
|------|------|----------|
| v1.3.0 | 2026-06 | MCP 组网、Hermes Workflow、NL Cron、Parliament 议会 |
| v1.2.0 | 2026-05 | 安全加固（CSP/HSTS、JWT 刷新、审计日志） |
| v1.1.0 | 2026-04 | Agent 对话、团队协作、Workflow 引擎 |
| v1.0.0 | 2026-03 | 基础平台：Auth、Agent、Group、Message |

## 许可证

[MIT](LICENSE) License