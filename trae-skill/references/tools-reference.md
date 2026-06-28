# aibond MCP 工具参考

## 平台工具列表

### aibond.list_agents
列出平台所有可用 Agent 及其能力。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 筛选状态：online / offline / all |

**返回：** Agent 列表，包含 id、name、status、skills、tools 等字段。

### aibond.run_workflow
触发执行一个工作流。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| workflow_id | string | 是 | 工作流 ID |
| params | object | 否 | 工作流参数 |

**返回：** 执行实例 ID 和状态。

### aibond.create_task
创建任务并分配给指定 Agent。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 任务标题 |
| description | string | 否 | 任务描述 |
| agent_id | string | 是 | 分配的 Agent ID |
| priority | string | 否 | 优先级：low / normal / high / urgent |

**返回：** 创建的任务对象。

### aibond.search_tools
跨 Agent 搜索可用工具。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索关键词 |
| agent_id | string | 否 | 限定 Agent |

**返回：** 匹配的工具列表，包含工具名、描述、所属 Agent。

### aibond.call_agent_tool
调用指定 Agent 的工具。

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| agent_id | string | 是 | Agent ID |
| tool_name | string | 是 | 工具名称 |
| arguments | object | 是 | 工具参数 |

**返回：** 工具执行结果。

## Workflow 节点类型

| 节点 | 说明 |
|------|------|
| trigger | 触发器节点（cron / webhook / event） |
| ai | AI 处理节点 |
| human_review | 人工审核节点 |
| condition | 条件分支节点 |
| output | 输出节点 |
| parallel | 并行执行节点 |
| webhook | HTTP 回调节点 |
| event_watcher | 事件监听节点 |

## 预置模板

基于 Hermes 5 层架构的 12 个预置模板：

1. **每日数据采集** (L1 定时任务) - 每天定时采集数据并汇总
2. **系统健康监控** (L2 智能监控) - 实时监控系统状态并告警
3. **数据处理流水线** (L3 任务执行) - 多步骤数据处理
4. **代码审查流程** (L3 任务执行) - 自动化代码审查
5. **多 Agent 协作研究** (L4 多Agent协作) - 多 Agent 分工研究
6. **Parliament 集体决策** (L4 多Agent协作) - 议会投票决策
7. **持续学习循环** (L5 持续进化) - 反馈驱动的持续改进
8. **Webhook 事件驱动** (事件驱动) - 外部事件触发工作流
9. **并行数据处理** (并行执行) - 数据并行处理与汇总
10. **人工审批流程** (人机协同) - 需要人工审批的流程
11. **条件分支决策** (智能路由) - 根据条件动态路由
12. **端到端自动化** (全流程) - 从触发到执行的完整自动化