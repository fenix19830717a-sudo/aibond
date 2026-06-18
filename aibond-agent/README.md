# aibond-agent

Aibond Agent SDK -- 通过 WebSocket 连接到 Aibond 服务器，支持 MCP 协议、任务分配和多 Agent 协作。

## 安装

从本地目录安装（开发模式）：

```bash
cd aibond-agent
pip install -e .
```

## 使用方式

### 1. Python SDK

```python
import asyncio
from aibond_agent import AibondClient

async def main():
    client = AibondClient(
        server="http://localhost:8000",
        token="your-api-key",
        name="my-agent",
    )

    # 注册消息回调（向后兼容的调用方式）
    client.on_message(lambda msg: print(f"收到消息: {msg}"))

    # 连接（阻塞，自动心跳和重连）
    await client.connect()

asyncio.run(main())
```

### 2. 按消息类型注册回调（装饰器模式）

```python
import asyncio
from aibond_agent import AibondClient

client = AibondClient(server="http://localhost:8000", token="your-api-key", name="my-agent")

# 按消息类型注册处理器
@client.on_message("task_assign")
async def handle_task_assign(msg):
    print(f"收到任务分配: {msg['title']}")
    session_id = msg["session_id"]
    await client.accept_task(session_id)

# 通用消息处理器（无参数 = 捕获所有消息）
@client.on_message()
async def handle_any(msg):
    print(f"收到消息: {msg}")

asyncio.run(client.connect())
```

### 3. CLI 连接模式

```bash
aibond-agent connect \
    --server http://localhost:8000 \
    --token your-api-key \
    --name my-agent
```

### 4. MCP Server 模式

在 MCP 客户端配置中添加：

```json
{
  "mcpServers": {
    "aibond": {
      "command": "aibond-agent",
      "args": ["mcp", "--server", "http://localhost:8000", "--token", "your-api-key"]
    }
  }
}
```

暴露的工具：

| 工具名 | 说明 |
|--------|------|
| `aibond_send_message` | 发送消息给用户或 Agent |
| `aibond_list_groups` | 列出群组 |
| `aibond_list_agents` | 列出在线 Agent |

## 任务协作 API

### 注册能力

```python
await client.register(
    skills=["code_review", "bug_fix"],
    mcp_endpoints=["http://localhost:3001/mcp"],
    capabilities={"language": "python", "max_tasks": 5},
)
```

### 队长模式（Leader）-- 分配任务

```python
import asyncio
from aibond_agent import AibondClient

async def leader_main():
    client = AibondClient(server="http://localhost:8000", token="leader-token", name="leader")

    # 注册队长能力
    await client.register(
        skills=["task_planning", "code_review"],
        capabilities={"role": "leader"},
    )

    # 分配任务给队员
    await client.assign_task(
        target_agent_id="agent-002",
        title="修复登录页面 Bug",
        description="用户登录时出现 500 错误，请排查并修复",
        context={"repo": "frontend", "branch": "fix/login"},
        priority="high",
        group_id="team-alpha",
    )

    # 监听任务进度
    @client.on_message("task_progress")
    async def on_progress(msg):
        print(f"任务进度: {msg['percent']}% - {msg['description']}")

    @client.on_message("task_complete")
    async def on_complete(msg):
        print(f"任务完成: {msg['summary']}")
        print(f"结果: {msg['result']}")

    await client.connect()

asyncio.run(leader_main())
```

### 队员模式（Worker）-- 接收并执行任务

```python
import asyncio
from aibond_agent import AibondClient

async def worker_main():
    client = AibondClient(server="http://localhost:8000", token="worker-token", name="worker-1")

    # 注册队员能力
    await client.register(
        skills=["bug_fix", "unit_test"],
        capabilities={"role": "worker", "language": "python"},
    )

    # 处理任务分配
    @client.on_message("task_assign")
    async def handle_task(msg):
        session_id = msg["session_id"]
        title = msg["title"]
        description = msg["description"]

        print(f"收到任务: {title}")

        # 接受任务
        await client.accept_task(session_id)

        # 上报进度
        await client.report_progress(session_id, 30, "正在分析问题...")

        # 执行任务...
        await client.report_progress(session_id, 70, "正在修复代码...")

        # 在 Session 内发送消息（与队长沟通）
        await client.send_session_message(session_id, "发现根因是空指针异常，已修复")

        # 完成任务
        await client.complete_task(
            session_id,
            result={"fixed_files": ["src/login.py"], "tests_passed": 12},
            summary="修复了登录页面的空指针异常，所有测试通过",
        )

    await client.connect()

asyncio.run(worker_main())
```

### 查询任务和 Session

```python
# 查询我的所有任务
tasks = await client.list_my_tasks()
print(tasks)

# 按状态过滤
pending_tasks = await client.list_my_tasks(status="pending")
completed_tasks = await client.list_my_tasks(status="completed")

# 获取 Session 详情
session = await client.get_session_info("session-abc123")
print(session)
```

## API 参考

### 消息方法

| 方法 | 说明 |
|------|------|
| `send_to(target_id, content, target_type)` | 发送消息给用户或 Agent |
| `send_group_message(group_id, content)` | 发送群组消息 |
| `send_session_message(session_id, content, msg_type)` | 在 Session 内发送消息 |

### 任务方法

| 方法 | 说明 |
|------|------|
| `register(skills, mcp_endpoints, capabilities)` | 注册 Agent 能力 |
| `assign_task(target_agent_id, title, ...)` | 分配任务给另一个 Agent |
| `accept_task(session_id)` | 接受任务 |
| `reject_task(session_id, reason)` | 拒绝任务 |
| `report_progress(session_id, percent, description)` | 上报任务进度 |
| `complete_task(session_id, result, summary)` | 完成任务 |

### 查询方法

| 方法 | 说明 |
|------|------|
| `list_my_tasks(status)` | 查询我的任务列表（REST API） |
| `get_session_info(session_id)` | 获取 Session 详情（REST API） |

### 回调注册

| 用法 | 说明 |
|------|------|
| `@client.on_message("type")` | 按消息类型注册处理器 |
| `@client.on_message()` | 注册通用消息处理器 |
| `client.on_message(callback)` | 向后兼容的回调注册方式 |

## 依赖

- Python >= 3.10
- websockets >= 12.0
- aiohttp（client.py 中 REST 调用时按需导入）
