"""Pull Queue 任务队列

基于 SQLite 的原子 Pull Queue，参考 Trinity Lite 的 bus.py 设计。
- 原子出队（BEGIN IMMEDIATE + UPDATE WHERE status='queued'）
- 事务性任务认领（防止多 Worker 抢同一任务）
- 委托深度限制（MAX_DEPTH=2）
- 自委托检测
- 心跳检测（超时自动回收任务）
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

MAX_DEPTH = 2
HEARTBEAT_TIMEOUT = 300  # 5 分钟无心跳视为超时


@dataclass
class PullTask:
    """Pull Queue 任务"""
    id: str
    source_agent: str
    target_agent: str
    task_type: str
    prompt: str
    cwd: str
    status: str
    depth: int
    result: Optional[str]
    error: Optional[str]
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    heartbeat_at: Optional[str]
    parent_task_id: Optional[str]
    review_task_id: Optional[str]
    gate_status: Optional[str]
    gate_updated_at: Optional[str]
    route_json: Optional[str]
    verification_json: Optional[str]
    acceptance_status: Optional[str]
    acceptance_reason: Optional[str]
    accepted_at: Optional[str]


class PullQueue:
    """Pull Queue 管理器

    使用 aiosqlite 操作 SQLite 数据库，实现原子任务出队。
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                "data", "pull_queue.db"
            )
        self.db_path = db_path
        self._initialized = False

    async def _ensure_initialized(self):
        if self._initialized:
            return
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pull_tasks (
                    id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL DEFAULT '',
                    target_agent TEXT NOT NULL,
                    task_type TEXT NOT NULL DEFAULT 'general',
                    prompt TEXT NOT NULL,
                    cwd TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'queued',
                    depth INTEGER NOT NULL DEFAULT 0,
                    result TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    heartbeat_at TEXT,
                    parent_task_id TEXT,
                    review_task_id TEXT,
                    gate_status TEXT,
                    gate_updated_at TEXT,
                    route_json TEXT,
                    verification_json TEXT,
                    acceptance_status TEXT,
                    acceptance_reason TEXT,
                    accepted_at TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS pull_messages (
                    id TEXT PRIMARY KEY,
                    source_agent TEXT NOT NULL,
                    target_agent TEXT NOT NULL,
                    task_id TEXT,
                    message TEXT NOT NULL,
                    read INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)
            await db.commit()
        self._initialized = True

    async def submit_task(
        self,
        target_agent: str,
        prompt: str,
        source_agent: str = "",
        task_type: str = "general",
        cwd: str = "",
        depth: int = 0,
    ) -> str:
        """提交任务到队列"""
        await self._ensure_initialized()

        # 安全检查
        if source_agent and source_agent == target_agent:
            raise ValueError(f"Self-delegation blocked: {source_agent}")
        if depth > MAX_DEPTH:
            raise ValueError(f"Delegation depth {depth} exceeds MAX_DEPTH={MAX_DEPTH}")

        task_id = uuid.uuid4().hex[:12]
        now = datetime.utcnow().isoformat()

        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO pull_tasks
                   (id, source_agent, target_agent, task_type, prompt, cwd, status, depth, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)""",
                (task_id, source_agent, target_agent, task_type, prompt, cwd, depth, now)
            )
            await db.commit()

        logger.info(f"Task submitted: {task_id} -> {target_agent} ({task_type})")
        return task_id

    async def task_for_worker(self, target_agent: str, task_id: str = None) -> Optional[PullTask]:
        """原子出队：Worker 领取一个排队任务

        使用事务 + UPDATE WHERE status='queued' 实现原子操作。
        同时回收超时的心跳任务。
        """
        await self._ensure_initialized()

        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("BEGIN IMMEDIATE")

            now = datetime.utcnow().isoformat()

            # 回收超时任务
            await db.execute(
                """UPDATE pull_tasks SET status='queued', started_at=NULL, heartbeat_at=NULL
                   WHERE status='running' AND heartbeat_at < ?""",
                ((datetime.utcnow() - timedelta(seconds=HEARTBEAT_TIMEOUT)).isoformat(),)
            )

            if task_id:
                cursor = await db.execute(
                    """UPDATE pull_tasks SET status='running', started_at=?, heartbeat_at=?
                       WHERE id=? AND target_agent=? AND status='queued'
                       RETURNING *""",
                    (now, now, task_id, target_agent)
                )
            else:
                # SQLite UPDATE ... RETURNING 不支持 ORDER BY/LIMIT
                # 先 SELECT 找到最早 queued 任务，再 UPDATE + RETURNING
                sel = await db.execute(
                    "SELECT id FROM pull_tasks WHERE target_agent=? AND status='queued' ORDER BY created_at ASC LIMIT 1",
                    (target_agent,)
                )
                sel_row = await sel.fetchone()
                if sel_row is None:
                    await db.commit()
                    return None
                cursor = await db.execute(
                    """UPDATE pull_tasks SET status='running', started_at=?, heartbeat_at=?
                       WHERE id=? AND status='queued'
                       RETURNING *""",
                    (now, now, sel_row[0])
                )

            row = await cursor.fetchone()
            await db.commit()

            if row is None:
                return None

            return self._row_to_task(row)

    async def heartbeat(self, task_id: str):
        """更新任务心跳"""
        await self._ensure_initialized()
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE pull_tasks SET heartbeat_at=? WHERE id=? AND status='running'",
                (datetime.utcnow().isoformat(), task_id)
            )
            await db.commit()

    async def finish_worker(self, task_id: str, result: str = None, error: str = None):
        """Worker 完成任务"""
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        status = "completed" if error is None else "failed"

        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """UPDATE pull_tasks SET status=?, result=?, error=?, finished_at=?
                   WHERE id=? AND status='running'""",
                (status, result, error, now, task_id)
            )
            await db.commit()

    async def get_task(self, task_id: str) -> Optional[PullTask]:
        """获取任务详情"""
        await self._ensure_initialized()
        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT * FROM pull_tasks WHERE id=?", (task_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_task(row)

    async def list_tasks(self, target_agent: str = None, status: str = None, limit: int = 50) -> list[PullTask]:
        """列出任务"""
        await self._ensure_initialized()
        query = "SELECT * FROM pull_tasks WHERE 1=1"
        params = []
        if target_agent:
            query += " AND target_agent=?"
            params.append(target_agent)
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [self._row_to_task(r) for r in rows]

    async def send_message(self, source_agent: str, target_agent: str, message: str, task_id: str = None):
        """发送 Agent 间消息"""
        await self._ensure_initialized()
        if source_agent == target_agent:
            raise ValueError(f"Self-messaging blocked: {source_agent}")

        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO pull_messages (id, source_agent, target_agent, task_id, message, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (uuid.uuid4().hex[:12], source_agent, target_agent, task_id, message, datetime.utcnow().isoformat())
            )
            await db.commit()

    async def get_inbox(self, target_agent: str, unread_only: bool = False, limit: int = 20) -> list[dict]:
        """获取 Agent 收件箱"""
        await self._ensure_initialized()
        query = "SELECT * FROM pull_messages WHERE target_agent=? "
        if unread_only:
            query += "AND read=0 "
        query += "ORDER BY created_at DESC LIMIT ?"

        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(query, (target_agent, limit))
            rows = await cursor.fetchall()
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, r)) for r in rows]

    async def await_task(self, task_id: str, timeout: int = 300) -> Optional[PullTask]:
        """轮询等待任务完成"""
        deadline = time.time() + timeout
        while time.time() < deadline:
            task = await self.get_task(task_id)
            if task and task.status in ("completed", "failed", "cancelled"):
                return task
            await asyncio.sleep(1)
        return await self.get_task(task_id)

    async def update_gate(self, task_id: str, gate_status: str, **kwargs):
        """更新 Gate 状态"""
        await self._ensure_initialized()
        now = datetime.utcnow().isoformat()
        fields = ["gate_status=?", "gate_updated_at=?"]
        params = [gate_status, now]

        for key, value in kwargs.items():
            if key in ("acceptance_status", "acceptance_reason", "accepted_at",
                        "verification_json", "route_json", "review_task_id"):
                fields.append(f"{key}=?")
                params.append(value)

        query = f"UPDATE pull_tasks SET {', '.join(fields)} WHERE id=?"

        import aiosqlite
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(query, params + [task_id])
            await db.commit()

    def _row_to_task(self, row) -> PullTask:
        return PullTask(
            id=row[0], source_agent=row[1], target_agent=row[2],
            task_type=row[3], prompt=row[4], cwd=row[5],
            status=row[6], depth=row[7], result=row[8], error=row[9],
            created_at=row[10], started_at=row[11], finished_at=row[12],
            heartbeat_at=row[13], parent_task_id=row[14], review_task_id=row[15],
            gate_status=row[16], gate_updated_at=row[17], route_json=row[18], verification_json=row[19],
            acceptance_status=row[20], acceptance_reason=row[21], accepted_at=row[22],
        )


class PullWorker:
    """Pull Worker 执行器

    拉取 → 执行 → 写回结果 的循环。
    """

    def __init__(self, agent_id: str, queue: PullQueue, adapter):
        self.agent_id = agent_id
        self.queue = queue
        self.adapter = adapter
        self._stop_flag = asyncio.Event()

    async def run_once(self, task_id: str = None) -> Optional[PullTask]:
        """执行一个任务"""
        task = await self.queue.task_for_worker(self.agent_id, task_id)
        if task is None:
            return None

        logger.info(f"Worker '{self.agent_id}' claimed task {task.id}")
        try:
            result = await self.adapter.run({
                "id": task.id,
                "prompt": task.prompt,
                "task_type": task.task_type,
                "cwd": task.cwd,
                "source_agent": task.source_agent,
            })
            await self.queue.finish_worker(task.id, result=result)
            logger.info(f"Worker '{self.agent_id}' completed task {task.id}")
        except Exception as e:
            await self.queue.finish_worker(task.id, error=str(e))
            logger.error(f"Worker '{self.agent_id}' failed task {task.id}: {e}")

        return await self.queue.get_task(task.id)

    async def run_loop(self, poll_seconds: int = 5):
        """持续轮询执行"""
        logger.info(f"Worker '{self.agent_id}' started, polling every {poll_seconds}s")
        while not self._stop_flag.is_set():
            task = await self.run_once()
            if task is None:
                await asyncio.sleep(poll_seconds)
            else:
                await asyncio.sleep(0.1)  # 有任务时快速轮询

    def stop(self):
        self._stop_flag.set()


# 全局单例
global_pull_queue = PullQueue()