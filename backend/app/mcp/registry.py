"""MCP Registry - 统一能力注册中心

MCP 组网核心：所有 Agent 的能力统一注册、索引和查询。

功能:
- 注册/更新 Agent 的 CapabilityManifest
- 按工具名、资源 URI、标签搜索 Agent
- 能力变更通知
- 支持本地注册（stdio/WebSocket Agent）和远程注册（SSE Agent）
"""

import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from app.mcp.protocol import (
    CapabilityManifest,
    ToolSchema,
    ResourceSchema,
    PromptSchema,
)

logger = logging.getLogger(__name__)


class MCPRegistry:
    """MCP 能力注册中心

    维护所有 Agent 的能力清单索引，支持:
    - 按工具名查找 Agent
    - 按资源 URI 查找 Agent
    - 按提示词名查找 Agent
    - 列出所有已注册 Agent 的能力摘要
    """

    def __init__(self):
        self._manifests: dict[str, CapabilityManifest] = {}
        # 倒排索引: tool_name -> set of agent_ids
        self._tool_index: dict[str, set[str]] = {}
        # 倒排索引: resource_uri -> set of agent_ids
        self._resource_index: dict[str, set[str]] = {}
        # 倒排索引: prompt_name -> set of agent_ids
        self._prompt_index: dict[str, set[str]] = {}
        # 变更监听器
        self._listeners: list[Callable] = []

    # ---- 注册 ----

    def register(self, manifest: CapabilityManifest) -> None:
        """注册或更新 Agent 能力清单"""
        old_manifest = self._manifests.get(manifest.agent_id)
        # 先从索引中移除旧数据
        if old_manifest:
            self._remove_from_index(old_manifest)

        self._manifests[manifest.agent_id] = manifest
        self._add_to_index(manifest)

        logger.info(
            f"[MCPRegistry] Registered agent {manifest.agent_name} ({manifest.agent_id}): "
            f"{len(manifest.tools)} tools, {len(manifest.resources)} resources, "
            f"{len(manifest.prompts)} prompts"
        )

        # 通知变更监听器
        self._notify_listeners("register", manifest.agent_id)

    def unregister(self, agent_id: str) -> None:
        """注销 Agent"""
        manifest = self._manifests.pop(agent_id, None)
        if manifest:
            self._remove_from_index(manifest)
            logger.info(f"[MCPRegistry] Unregistered agent {manifest.agent_name} ({agent_id})")
            self._notify_listeners("unregister", agent_id)

    def register_from_skills(
        self,
        agent_id: str,
        agent_name: str,
        skills: list[str],
        transport: str = "websocket",
        endpoint: str | None = None,
    ) -> CapabilityManifest:
        """从旧版 skills 列表生成兼容的 CapabilityManifest

        将自由文本 skills 转换为 MCP Tool 格式。
        """
        tools = []
        for skill in skills:
            tool = ToolSchema(
                name=skill.strip().lower().replace(" ", "_"),
                description=f"Agent skill: {skill}",
                inputSchema={"type": "object", "properties": {}, "required": []},
            )
            tools.append(tool)

        manifest = CapabilityManifest(
            agent_id=agent_id,
            agent_name=agent_name,
            transport=transport,
            endpoint=endpoint,
            tools=tools,
            server_capabilities={"tools": {"listChanged": False}},
        )
        self.register(manifest)
        return manifest

    # ---- 查询 ----

    def get_manifest(self, agent_id: str) -> CapabilityManifest | None:
        """获取 Agent 能力清单"""
        return self._manifests.get(agent_id)

    def list_all_agents(self) -> list[dict]:
        """列出所有已注册 Agent 的摘要"""
        return [
            {
                "agent_id": agent_id,
                "agent_name": m.agent_name,
                "transport": m.transport,
                "tool_count": len(m.tools),
                "resource_count": len(m.resources),
                "prompt_count": len(m.prompts),
                "tool_names": [t.name for t in m.tools],
                "last_updated": m.last_updated,
            }
            for agent_id, m in self._manifests.items()
        ]

    def find_agents_by_tool(self, tool_name: str) -> list[str]:
        """按工具名查找 Agent"""
        return list(self._tool_index.get(tool_name, set()))

    def find_agents_by_resource(self, uri_pattern: str) -> list[str]:
        """按资源 URI 模糊查找 Agent"""
        result = set()
        for uri, agent_ids in self._resource_index.items():
            if uri_pattern in uri:
                result.update(agent_ids)
        return list(result)

    def find_agents_by_prompt(self, prompt_name: str) -> list[str]:
        """按提示词名查找 Agent"""
        return list(self._prompt_index.get(prompt_name, set()))

    def search_tools(self, query: str) -> list[dict]:
        """搜索工具（模糊匹配名称和描述）"""
        results = []
        query_lower = query.lower()
        for agent_id, manifest in self._manifests.items():
            for tool in manifest.tools:
                if query_lower in tool.name.lower() or query_lower in tool.description.lower():
                    results.append({
                        "agent_id": agent_id,
                        "agent_name": manifest.agent_name,
                        "tool_name": tool.name,
                        "tool_description": tool.description,
                        "transport": manifest.transport,
                    })
        return results

    def list_all_tools(self) -> list[dict]:
        """列出所有已注册的 Tools"""
        results = []
        for agent_id, manifest in self._manifests.items():
            for tool in manifest.tools:
                results.append({
                    "agent_id": agent_id,
                    "agent_name": manifest.agent_name,
                    "tool": tool.model_dump(),
                })
        return results

    def list_all_resources(self) -> list[dict]:
        """列出所有已注册的 Resources"""
        results = []
        for agent_id, manifest in self._manifests.items():
            for resource in manifest.resources:
                results.append({
                    "agent_id": agent_id,
                    "agent_name": manifest.agent_name,
                    "resource": resource.model_dump(),
                })
        return results

    # ---- 变更监听 ----

    def add_listener(self, listener: Callable[[str, str], None]) -> None:
        """添加注册变更监听器"""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable) -> None:
        """移除监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, event: str, agent_id: str) -> None:
        for listener in self._listeners:
            try:
                listener(event, agent_id)
            except Exception as e:
                logger.error(f"[MCPRegistry] Listener error: {e}")

    # ---- 内部方法 ----

    def _add_to_index(self, manifest: CapabilityManifest) -> None:
        agent_id = manifest.agent_id
        for tool in manifest.tools:
            if tool.name not in self._tool_index:
                self._tool_index[tool.name] = set()
            self._tool_index[tool.name].add(agent_id)
        for resource in manifest.resources:
            if resource.uri not in self._resource_index:
                self._resource_index[resource.uri] = set()
            self._resource_index[resource.uri].add(agent_id)
        for prompt in manifest.prompts:
            if prompt.name not in self._prompt_index:
                self._prompt_index[prompt.name] = set()
            self._prompt_index[prompt.name].add(agent_id)

    def _remove_from_index(self, manifest: CapabilityManifest) -> None:
        agent_id = manifest.agent_id
        for tool in manifest.tools:
            if tool.name in self._tool_index:
                self._tool_index[tool.name].discard(agent_id)
                if not self._tool_index[tool.name]:
                    del self._tool_index[tool.name]
        for resource in manifest.resources:
            if resource.uri in self._resource_index:
                self._resource_index[resource.uri].discard(agent_id)
                if not self._resource_index[resource.uri]:
                    del self._resource_index[resource.uri]
        for prompt in manifest.prompts:
            if prompt.name in self._prompt_index:
                self._prompt_index[prompt.name].discard(agent_id)
                if not self._prompt_index[prompt.name]:
                    del self._prompt_index[prompt.name]

    @property
    def agent_count(self) -> int:
        return len(self._manifests)

    @property
    def tool_count(self) -> int:
        return len(self._tool_index)

    @property
    def resource_count(self) -> int:
        return len(self._resource_index)

    @property
    def prompt_count(self) -> int:
        return len(self._prompt_index)


# 全局注册中心实例
global_registry = MCPRegistry()