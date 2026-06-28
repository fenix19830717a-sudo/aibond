"""Agent Parliament - Multi-agent consensus voting and deliberation system.

Based on the AgentParliament concept: multiple cheap models (DeepSeek, GLM, MiniMax)
for mutual review/cross-validation, with Claude as final arbiter.
"""

from app.parliament.engine import ParliamentEngine

__all__ = ["ParliamentEngine"]