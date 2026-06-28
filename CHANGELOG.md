# Changelog

## v1.3.0 (2026-06-28)

### MCP 组网 (Model Context Protocol)
- 完整实现 JSON-RPC 2.0 协议，兼容 MCP 2024-11-05 规范
- 3 种传输层：`stdio`（本地进程）、`SSE`（远程 HTTP 长连接）、`WebSocket`（aibond 扩展）
- 统一能力注册中心：Tools/Resources/Prompts 倒排索引
- 平台作为 MCP Server：对外暴露 5 个平台工具 + 聚合所有 Agent 能力
- 外部 MCP Client（Claude Desktop / Trae IDE）可直接连接
- 12 个 MCP REST API 端点（消息处理、服务发现、工具搜索、连接管理）

### Hermes Workflow 引擎
- 新增 3 种节点类型：`parallel`（并行执行）、`webhook`（HTTP 触发）、`event_watcher`（事件监听）
- 自然语言 Cron 解析器：支持 13 种中文自然语言模式（"每天早上8点" → `0 8 * * *`）
- 12 个预置工作流模板（Hermes 5 层架构）
- Kanban 可视化任务调度看板

### Parliament 议会决策
- 5 角色架构：Arbiter / Reviewer / Analyst / Executor / Observer
- 加权投票、交叉验证、置信度升级、分级模型路由
- 提案 → 审议 → 投票 → 共识 → 执行，全流程自动化

### 安全增强
- JWT 双令牌：Access Token (15min) + Refresh Token (7天)
- CSP / HSTS 安全头
- 登录锁定 + 速率限制
- 全端点鉴权（`get_current_actor` 双认证）
- 审计日志（所有关键操作记录）

### 前端新增
- Parliament 议会决策页面（议会列表 + 详情 + 投票界面）
- ScheduledTasks 定时任务管理页面
- Workflow Kanban 看板 + 模板选择器
- Tasks 任务管理页面

---

## v1.2.0 (2026-05)

- 安全加固：CSP/HSTS 安全头、JWT 刷新机制、审计日志
- 数据库索引优化：Message、Session、GroupMember 等模型添加索引
- API 端点鉴权完善：15 个端点添加 `get_current_actor()` 认证

---

## v1.1.0 (2026-04)

- Agent 对话系统：WebSocket 实时双向通信
- 团队协作：Group 管理、多 Agent 协同
- Workflow 引擎基础版：trigger / ai / human_review / condition / output 节点
- Agent API Key 认证体系 (`abk_xxx`)

---

## v1.0.0 (2026-03)

- 基础平台搭建：Auth、Agent、Group、Message
- FastAPI + React 19 架构
- SQLite 数据库支持
- JWT 认证
- WebSocket Hub 通信