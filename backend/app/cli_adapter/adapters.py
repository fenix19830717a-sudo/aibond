"""CLI 命令适配器

将本地 CLI 工具（如 Codex CLI、Claude Code、Hermes 等）包装为 aibond Agent。
参考 Trinity Lite 的 adapter 模式，支持：
- 占位符替换：{prompt} / {cwd} / {task_id} / {task_type}
- 两种 prompt 传递方式：命令行参数 或 stdin 管道
- shell=False 安全执行
- 超时控制
"""

import asyncio
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentSpec:
    """Agent 规格定义"""
    agent_id: str
    agent_name: str = ""
    mode: str = "command"  # mock | command
    command: list = field(default_factory=list)
    timeout: int = 1800
    roles: list = field(default_factory=list)
    capabilities: list = field(default_factory=list)
    priority: int = 50
    cwd: str = ""
    env: dict = field(default_factory=dict)
    model_tier: str = "standard"  # budget | standard | premium
    model_strengths: list = field(default_factory=list)


class BaseAdapter:
    """适配器抽象基类"""

    def __init__(self, spec: AgentSpec):
        self.spec = spec

    async def run(self, task: dict) -> str:
        raise NotImplementedError


class MockAdapter(BaseAdapter):
    """Mock 适配器 - 用于测试，不执行真实命令"""

    async def run(self, task: dict) -> str:
        task_type = task.get("task_type", "unknown")
        prompt = task.get("prompt", "")
        return json.dumps({
            "status": "mock_completed",
            "task_type": task_type,
            "prompt_preview": prompt[:100],
            "agent": self.spec.agent_id,
            "mock": True,
        }, ensure_ascii=False, indent=2)


class CommandAdapter(BaseAdapter):
    """CLI 命令适配器 - 通过 subprocess 执行外部 CLI 工具

    支持两种 prompt 传递方式：
    1. 命令行参数：command 中包含 {prompt} 占位符
    2. stdin 管道：command 中无 {prompt}，通过 stdin 传入
    """

    PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

    async def run(self, task: dict) -> str:
        command = list(self.spec.command)
        prompt = task.get("prompt", "")
        task_id = task.get("id", "")
        task_type = task.get("task_type", "")
        cwd = self.spec.cwd or task.get("cwd", os.getcwd())

        # 占位符替换
        has_prompt_placeholder = False
        for i, arg in enumerate(command):
            def replace_match(m):
                nonlocal has_prompt_placeholder
                key = m.group(1)
                if key == "prompt":
                    has_prompt_placeholder = True
                    return prompt
                elif key == "cwd":
                    return cwd
                elif key == "task_id":
                    return task_id
                elif key == "task_type":
                    return task_type
                return m.group(0)
            command[i] = self.PLACEHOLDER_RE.sub(replace_match, arg)

        # 环境变量
        env = os.environ.copy()
        env.update(self.spec.env)

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                cwd=cwd,
                env=env,
                stdin=asyncio.subprocess.PIPE if not has_prompt_placeholder else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdin_data = None
            if not has_prompt_placeholder and prompt:
                stdin_data = prompt.encode("utf-8")

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_data),
                timeout=self.spec.timeout,
            )

            if proc.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="replace")[:500]
                raise RuntimeError(f"CLI exit code {proc.returncode}: {error_msg}")

            result = stdout.decode("utf-8", errors="replace")
            return result

        except asyncio.TimeoutError:
            raise TimeoutError(f"CLI agent '{self.spec.agent_id}' timed out after {self.spec.timeout}s")
        except Exception as e:
            logger.error(f"CLI adapter error for agent '{self.spec.agent_id}': {e}")
            raise


def build_adapter(spec: AgentSpec) -> BaseAdapter:
    """适配器工厂函数"""
    if spec.mode == "mock":
        return MockAdapter(spec)
    elif spec.mode == "command":
        return CommandAdapter(spec)
    else:
        raise ValueError(f"Unknown adapter mode: {spec.mode}")


def load_specs(path: Optional[str] = None) -> dict[str, AgentSpec]:
    """从 JSON 文件加载 Agent 规格配置"""
    if path is not None:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        return _default_specs()

    specs = {}
    for agent_id, cfg in data.get("agents", {}).items():
        specs[agent_id] = AgentSpec(
            agent_id=agent_id,
            agent_name=cfg.get("name", agent_id),
            mode=cfg.get("mode", "command"),
            command=cfg.get("command", []),
            timeout=cfg.get("timeout", 1800),
            roles=cfg.get("roles", []),
            capabilities=cfg.get("capabilities", []),
            priority=cfg.get("priority", 50),
            cwd=cfg.get("cwd", ""),
            env=cfg.get("env", {}),
            model_tier=cfg.get("model_tier", "standard"),
            model_strengths=cfg.get("model_strengths", []),
        )
    return specs


def _default_specs() -> dict[str, AgentSpec]:
    """内置默认 Agent 规格"""
    return {
        "codex": AgentSpec(
            agent_id="codex",
            agent_name="Codex CLI",
            command=["codex", "{prompt}"],
            roles=["primary_engineer"],
            capabilities=["code_edit", "test_run", "debug"],
            priority=80,
            model_tier="premium",
            model_strengths=["coding", "reasoning"],
        ),
        "claude_code": AgentSpec(
            agent_id="claude_code",
            agent_name="Claude Code",
            command=["claude", "{prompt}"],
            roles=["primary_engineer", "reviewer"],
            capabilities=["code_edit", "code_review", "architecture"],
            priority=85,
            model_tier="premium",
            model_strengths=["reasoning", "architecture", "security"],
        ),
        "hermes": AgentSpec(
            agent_id="hermes",
            agent_name="Hermes Agent",
            command=["hermes", "run", "{prompt}"],
            roles=["researcher", "analyst"],
            capabilities=["research", "analysis", "data_processing"],
            priority=60,
            model_tier="standard",
            model_strengths=["research", "chinese"],
        ),
    }