"""Gate 状态机

参考 Trinity Lite 的 acceptance evidence 设计，实现结构化审查/验证/接受流程。
状态链路：
  primary_pending → review_pending → review_passed / review_attention
  → verification_pending → verification_failed / accepted
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class GateStatus(str, Enum):
    """Gate 状态枚举"""
    PRIMARY_PENDING = "primary_pending"       # 主任务等待执行
    PRIMARY_RUNNING = "primary_running"       # 主任务执行中
    PRIMARY_COMPLETED = "primary_completed"   # 主任务完成
    REVIEW_PENDING = "review_pending"         # 等待审查
    REVIEW_RUNNING = "review_running"         # 审查执行中
    REVIEW_PASSED = "review_passed"           # 审查通过
    REVIEW_ATTENTION = "review_attention"     # 审查发现问题（P0/P1）
    VERIFICATION_PENDING = "verification_pending"  # 等待验证
    VERIFICATION_FAILED = "verification_failed"    # 验证失败
    ACCEPTED = "accepted"                     # 已接受
    CANCELLED = "cancelled"                   # 已取消

    @property
    def is_terminal(self) -> bool:
        return self in (GateStatus.ACCEPTED, GateStatus.CANCELLED, GateStatus.VERIFICATION_FAILED)

    @property
    def is_blocked(self) -> bool:
        return self in (GateStatus.REVIEW_ATTENTION, GateStatus.VERIFICATION_FAILED)


# 合法状态转换
VALID_TRANSITIONS = {
    GateStatus.PRIMARY_PENDING: {GateStatus.PRIMARY_RUNNING, GateStatus.CANCELLED},
    GateStatus.PRIMARY_RUNNING: {GateStatus.PRIMARY_COMPLETED, GateStatus.CANCELLED},
    GateStatus.PRIMARY_COMPLETED: {GateStatus.REVIEW_PENDING, GateStatus.ACCEPTED},
    GateStatus.REVIEW_PENDING: {GateStatus.REVIEW_RUNNING, GateStatus.CANCELLED},
    GateStatus.REVIEW_RUNNING: {GateStatus.REVIEW_PASSED, GateStatus.REVIEW_ATTENTION, GateStatus.CANCELLED},
    GateStatus.REVIEW_PASSED: {GateStatus.VERIFICATION_PENDING, GateStatus.ACCEPTED},
    GateStatus.REVIEW_ATTENTION: {GateStatus.VERIFICATION_PENDING, GateStatus.CANCELLED},
    GateStatus.VERIFICATION_PENDING: {GateStatus.ACCEPTED, GateStatus.VERIFICATION_FAILED},
    GateStatus.VERIFICATION_FAILED: {GateStatus.VERIFICATION_PENDING, GateStatus.CANCELLED},
    GateStatus.ACCEPTED: set(),
    GateStatus.CANCELLED: set(),
}


@dataclass
class GateEvidence:
    """Gate 审计证据"""
    task_id: str
    gate_status: GateStatus
    gate_updated_at: str
    route_json: Optional[str] = None
    parent_task_id: Optional[str] = None
    review_task_id: Optional[str] = None
    verification_json: Optional[str] = None
    acceptance_status: Optional[str] = None
    acceptance_reason: Optional[str] = None
    accepted_at: Optional[str] = None


class GateStateMachine:
    """Gate 状态机

    管理任务从提交到接受的完整生命周期。
    """

    def __init__(self):
        self._states: dict[str, GateStatus] = {}

    def transition(self, task_id: str, from_status: GateStatus, to_status: GateStatus) -> bool:
        """执行状态转换，返回是否合法"""
        if to_status not in VALID_TRANSITIONS.get(from_status, set()):
            return False
        self._states[task_id] = to_status
        return True

    def get_status(self, task_id: str) -> GateStatus:
        return self._states.get(task_id, GateStatus.PRIMARY_PENDING)

    def can_transition(self, from_status: GateStatus, to_status: GateStatus) -> bool:
        return to_status in VALID_TRANSITIONS.get(from_status, set())

    @staticmethod
    def next_steps(current: GateStatus) -> list[GateStatus]:
        """获取当前状态的可选下一步"""
        return list(VALID_TRANSITIONS.get(current, set()))


def acceptance_evidence(
    task_id: str,
    gate_status: GateStatus,
    route_json: str = None,
    parent_task_id: str = None,
    review_task_id: str = None,
    verification_json: str = None,
    acceptance_status: str = None,
    acceptance_reason: str = None,
    accepted_at: str = None,
) -> GateEvidence:
    """创建 Gate 审计证据"""
    if gate_status == GateStatus.ACCEPTED and accepted_at is None:
        accepted_at = datetime.utcnow().isoformat()
    return GateEvidence(
        task_id=task_id,
        gate_status=gate_status,
        gate_updated_at=datetime.utcnow().isoformat(),
        route_json=route_json,
        parent_task_id=parent_task_id,
        review_task_id=review_task_id,
        verification_json=verification_json,
        acceptance_status=acceptance_status,
        acceptance_reason=acceptance_reason,
        accepted_at=accepted_at,
    )