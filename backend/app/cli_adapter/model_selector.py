"""智能模型选择器

参考 Trinity Lite 的 model_selector 设计，按任务复杂度自动选择模型。
三层决策：
  Layer 1: 快速旁路（正则匹配简单任务 → budget）
  Layer 2: 硬信号（关键词匹配 → premium/standard）
  Layer 2.5: 任务类型映射（task_type → tier）
  Layer 3: 复杂度分类（token 数 + 结构标记 → SC 分数）
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 快速旁路规则 — 简单任务直接走 budget
# ============================================================
BYPASS_PATTERNS = [
    re.compile(r"^(hello|hi|hey|ping|echo|test)\b", re.IGNORECASE),
    re.compile(r"^(fix|correct)\s+(typo|spelling|grammar)\b", re.IGNORECASE),
    re.compile(r"^(translate|翻译)\b", re.IGNORECASE),
    re.compile(r"^(rename|重命名)\b", re.IGNORECASE),
    re.compile(r"^(add\s+comment|加注释|add\s+docstring)\b", re.IGNORECASE),
    re.compile(r"^(format|格式化)\b", re.IGNORECASE),
    re.compile(r"^(what\s+is|什么是|how\s+to|怎么)\b", re.IGNORECASE),
    re.compile(r"^(list|列出|show|显示)\b", re.IGNORECASE),
]


# ============================================================
# 硬信号 — 关键词 → 强制需求
# ============================================================
HARD_SIGNALS = {
    "security": {
        "patterns": [re.compile(r"\b(CVE|exploit|vulnerability|XSS|SQL\s*injection|CSRF|auth\s*bypass|zero.day|penetration|渗透|漏洞|安全审计)\b", re.IGNORECASE)],
        "tier": "premium",
        "demand": "security",
    },
    "architecture": {
        "patterns": [re.compile(r"\b(architecture|system\s*design|microservice|distributed|scalab|design\s*pattern|架构|系统设计|微服务|分布式|可扩展)\b", re.IGNORECASE)],
        "tier": "premium",
        "demand": "architecture",
    },
    "diagnosis": {
        "patterns": [re.compile(r"\b(root\s*cause|troubleshoot|debug|diagnos|investigate|排查|诊断|调试|根因)\b", re.IGNORECASE)],
        "tier": "premium",
        "demand": "diagnosis",
    },
    "refactor": {
        "patterns": [re.compile(r"\b(refactor|重构|重写|rewrite|overhaul)\b", re.IGNORECASE)],
        "tier": "standard",
        "demand": "refactor",
    },
    "chinese": {
        "patterns": [re.compile(r"[\u4e00-\u9fff]{10,}")],
        "tier": "standard",
        "demand": "chinese",
    },
}


# ============================================================
# 任务类型 → Tier 映射
# ============================================================
TASK_TYPE_TIER = {
    "documentation": "budget",
    "test_writing": "budget",
    "code_review": "budget",
    "simple_fix": "budget",
    "translation": "budget",
    "refactor": "standard",
    "bug_fix_complex": "standard",
    "feature_implementation": "standard",
    "deployment": "standard",
    "architecture_design": "premium",
    "security_audit": "premium",
    "diagnosis": "premium",
    "research": "premium",
    "parliament": "premium",
}


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    tier: str  # budget | standard | premium
    strengths: list = field(default_factory=list)
    api_type: str = "openai"
    available_to: list = field(default_factory=list)  # agent 权限列表


@dataclass
class SelectResult:
    """选择结果"""
    model: str
    tier: str
    reason: str
    bypassed: bool = False


class ModelSelector:
    """智能模型选择器"""

    def __init__(self, model_pool: dict[str, ModelInfo] = None):
        self.model_pool = model_pool or _default_model_pool()

    def select(self, prompt: str, task_type: str = "general", agent_id: str = None) -> SelectResult:
        """选择最优模型"""
        # Layer 1: 快速旁路
        for pattern in BYPASS_PATTERNS:
            if pattern.search(prompt):
                return self._pick_best_model("budget", agent_id, reason="fast_bypass")

        # Layer 2: 硬信号
        max_tier = None
        max_demand = None
        for name, signal in HARD_SIGNALS.items():
            for pattern in signal["patterns"]:
                if pattern.search(prompt):
                    if max_tier is None or _tier_order(signal["tier"]) > _tier_order(max_tier):
                        max_tier = signal["tier"]
                        max_demand = signal["demand"]

        if max_tier:
            return self._pick_best_model(max_tier, agent_id, demand=max_demand, reason=f"hard_signal:{max_demand}")

        # Layer 2.5: 任务类型
        tier = TASK_TYPE_TIER.get(task_type, "budget")
        if tier != "budget":
            return self._pick_best_model(tier, agent_id, reason=f"task_type:{task_type}")

        # Layer 3: 复杂度分类
        sc = self._selector_complexity(prompt)
        if sc >= 3:
            return self._pick_best_model("premium", agent_id, reason=f"complexity:SC{sc}")
        elif sc >= 2:
            return self._pick_best_model("standard", agent_id, reason=f"complexity:SC{sc}")
        else:
            return self._pick_best_model("budget", agent_id, reason=f"complexity:SC{sc}")

    def _selector_complexity(self, prompt: str) -> int:
        """计算 Selector Complexity (0-3)"""
        token_count = len(prompt.split())
        sc = 0
        if token_count >= 800:
            sc = 3
        elif token_count >= 300:
            sc = 2
        elif token_count >= 100:
            sc = 1

        # 结构标记加分
        structural_markers = [
            (r"\b(multi.*file|多文件|多个模块)\b", 1),
            (r"\b(refactor|重构|数据库.*迁移|schema.*change)\b", 1),
            (r"\b(debug|排查|诊断|troubleshoot)\b", 1),
            (r"```", 1),  # 包含代码块
        ]
        for pattern, bonus in structural_markers:
            if re.search(pattern, prompt, re.IGNORECASE):
                sc += bonus

        return min(sc, 3)

    def _pick_best_model(self, required_tier: str, agent_id: str = None,
                          demand: str = None, reason: str = "") -> SelectResult:
        """从模型池中选最优"""
        candidates = []

        for name, info in self.model_pool.items():
            # 权限检查
            if agent_id and info.available_to and agent_id not in info.available_to:
                continue
            # Tier 检查
            if _tier_order(info.tier) < _tier_order(required_tier):
                if not candidates:
                    candidates.append((name, info, 0, 0))
                continue

            # 打分
            demand_score = 1 if demand and demand in info.strengths else 0
            exact_tier_bonus = 1 if info.tier == required_tier else 0
            tier_score = _tier_order(info.tier)
            candidates.append((name, info, demand_score + exact_tier_bonus, tier_score))

        if not candidates:
            return SelectResult(model="unknown", tier=required_tier, reason="no_candidates")

        # 排序：demand 匹配 > exact tier > tier 等级
        candidates.sort(key=lambda x: (x[2], x[3]), reverse=True)
        best_name, best_info, _, _ = candidates[0]

        return SelectResult(
            model=best_name,
            tier=best_info.tier,
            reason=reason,
        )


def _tier_order(tier: str) -> int:
    return {"budget": 0, "standard": 1, "premium": 2}.get(tier, 0)


def _default_model_pool() -> dict[str, ModelInfo]:
    return {
        "glm-5.2": ModelInfo(
            name="glm-5.2",
            tier="budget",
            strengths=["coding", "chinese"],
            api_type="openai",
        ),
        "deepseek-v4-pro": ModelInfo(
            name="deepseek-v4-pro",
            tier="standard",
            strengths=["chinese", "reasoning", "coding"],
            api_type="openai",
        ),
        "gpt-5.5": ModelInfo(
            name="gpt-5.5",
            tier="premium",
            strengths=["reasoning", "architecture", "security"],
            api_type="openai",
        ),
        "claude-sonnet-4-20250514": ModelInfo(
            name="claude-sonnet-4-20250514",
            tier="premium",
            strengths=["reasoning", "security", "architecture", "coding"],
            api_type="anthropic",
        ),
    }


# 便捷函数
_default_selector = ModelSelector()


def select_model(prompt: str, task_type: str = "general", agent_id: str = None) -> SelectResult:
    return _default_selector.select(prompt, task_type, agent_id)