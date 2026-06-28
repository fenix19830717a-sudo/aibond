"""CLI Adapter 模块

将本地 CLI 工具接入 aibond 平台，实现：
- CLI 命令适配器（subprocess 执行）
- Pull Queue 任务队列（SQLite 原子出队）
- Gate 状态机（审查/验证/接受流程）
- 智能模型选择器（按复杂度自动选模型）
"""

from .adapters import AgentSpec, CommandAdapter, MockAdapter, build_adapter, load_specs
from .pull_queue import PullQueue, PullWorker
from .gate import GateStatus, GateStateMachine, acceptance_evidence
from .model_selector import ModelSelector, select_model

__all__ = [
    "AgentSpec", "CommandAdapter", "MockAdapter", "build_adapter", "load_specs",
    "PullQueue", "PullWorker",
    "GateStatus", "GateStateMachine", "acceptance_evidence",
    "ModelSelector", "select_model",
]