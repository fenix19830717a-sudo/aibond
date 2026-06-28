"""
12 Preset Workflow Templates

Reference: Hermes Agent's 12 workflow templates, adapted for aibond's
Human-Agent collaboration scenarios across 5 architectural layers.

Each template is a dict with: id, name, description, category, icon,
trigger_type, and definition (nodes + edges).
"""

import uuid

# ---------------------------------------------------------------------------
# Helper: generate unique node IDs
# ---------------------------------------------------------------------------
def _nid() -> str:
    """Generate a short unique node ID for template definitions."""
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------------------------
# Layer 1: Scheduled Tasks (定时任务类)
# ---------------------------------------------------------------------------

TEMPLATE_MORNING_BRIEFING = {
    "id": "morning_briefing",
    "name": "晨间简报",
    "description": "每天早上推送行业新闻 + 日程 + 紧急消息到群组，帮助团队快速了解当日重点。",
    "category": "定时任务类",
    "icon": "sunrise",
    "trigger_type": "schedule",
    "trigger_config": {"cron": "0 9 * * *", "description": "每天上午9:00"},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "定时触发",
                    "config": {"trigger_type": "schedule", "cron": "0 9 * * *"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "新闻收集Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "收集今日行业新闻，按重要程度排序，输出前10条摘要。",
                        "title": "新闻收集",
                    },
                },
                "position": {"x": 350, "y": 100},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "日程整理Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "整理今日待办日程和紧急事项，按优先级排列。",
                        "title": "日程整理",
                    },
                },
                "position": {"x": 350, "y": 300},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "发送群组消息",
                    "config": {"value": "整合新闻和日程，发送到群组。", "output_type": "group_message"},
                },
                "position": {"x": 600, "y": 200},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e2", "source": "n1", "target": "n3", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e3", "source": "n2", "target": "n4", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e4", "source": "n3", "target": "n4", "sourceHandle": "output", "targetHandle": "input"},
        ],
    },
}

TEMPLATE_SERVER_HEALTH_CHECK = {
    "id": "server_health_check",
    "name": "服务器健康巡检",
    "description": "每30分钟自动检查服务器状态，发现异常立即告警通知。",
    "category": "定时任务类",
    "icon": "server",
    "trigger_type": "schedule",
    "trigger_config": {"cron": "*/30 * * * *", "description": "每30分钟"},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "定时触发",
                    "config": {"trigger_type": "schedule", "cron": "*/30 * * * *"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "监控Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "检查所有服务器状态：CPU、内存、磁盘、网络、服务进程。输出状态报告。",
                        "title": "服务器巡检",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "condition",
                    "label": "是否异常",
                    "config": {"expression": "n2.status != normal"},
                },
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "告警Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "根据异常信息生成告警通知，包含异常详情和初步排查建议。",
                        "title": "异常告警",
                    },
                },
                "position": {"x": 850, "y": 100},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "发送告警通知",
                    "config": {"value": "通过群组消息发送告警。", "output_type": "group_message"},
                },
                "position": {"x": 1100, "y": 100},
            },
            {
                "id": "n6",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "记录正常",
                    "config": {"value": "所有服务正常运行，记录巡检日志。", "output_type": "log"},
                },
                "position": {"x": 850, "y": 300},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e2", "source": "n2", "target": "n3", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e3", "source": "n3", "target": "n4", "sourceHandle": "true", "targetHandle": "input"},
            {"id": "e4", "source": "n3", "target": "n6", "sourceHandle": "false", "targetHandle": "input"},
            {"id": "e5", "source": "n4", "target": "n5", "sourceHandle": "output", "targetHandle": "input"},
        ],
    },
}

TEMPLATE_WEEKLY_REPORT = {
    "id": "weekly_report",
    "name": "周五周报生成",
    "description": "每周五下午6点自动生成项目周报，支持人工审核后发布。",
    "category": "定时任务类",
    "icon": "file-text",
    "trigger_type": "schedule",
    "trigger_config": {"cron": "0 18 * * 5", "description": "每周五下午6:00"},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "定时触发",
                    "config": {"trigger_type": "schedule", "cron": "0 18 * * 5"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "数据收集Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "收集本周各项数据：代码提交量、任务完成数、Bug修复数、文档更新等。",
                        "title": "数据收集",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "报告生成Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "根据收集的数据生成周报，包含：本周成果、关键指标、问题与风险、下周计划。",
                        "title": "周报生成",
                    },
                },
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "human_review",
                    "label": "人工审核",
                    "config": {"review_type": "approval", "timeout_hours": 2},
                },
                "position": {"x": 850, "y": 200},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "发布周报",
                    "config": {"value": "将审核通过的周报发送到群组。", "output_type": "group_message"},
                },
                "position": {"x": 1100, "y": 200},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e2", "source": "n2", "target": "n3", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e3", "source": "n3", "target": "n4", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e4", "source": "n4", "target": "n5", "sourceHandle": "output", "targetHandle": "input"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Layer 2: Intelligent Monitoring (智能监控类)
# ---------------------------------------------------------------------------

TEMPLATE_COMPETITOR_MONITOR = {
    "id": "competitor_monitor",
    "name": "竞品动态追踪",
    "description": "每周一自动扫描竞品动态，对比数据变化，生成竞品分析报告。",
    "category": "智能监控类",
    "icon": "trending-up",
    "trigger_type": "schedule",
    "trigger_config": {"cron": "0 9 * * 1", "description": "每周一上午9:00"},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "定时触发",
                    "config": {"trigger_type": "schedule", "cron": "0 9 * * 1"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "竞品分析Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "扫描竞品最新动态：产品更新、市场活动、融资动态、用户评价。",
                        "title": "竞品扫描",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "数据对比Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "对比竞品与自身数据变化，识别差距和机会点，生成对比报告。",
                        "title": "数据对比",
                    },
                },
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "生成对比报告",
                    "config": {"value": "输出竞品分析报告到群组。", "output_type": "group_message"},
                },
                "position": {"x": 850, "y": 200},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e2", "source": "n2", "target": "n3", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e3", "source": "n3", "target": "n4", "sourceHandle": "output", "targetHandle": "input"},
        ],
    },
}

TEMPLATE_CODE_REVIEW_MONITOR = {
    "id": "code_review_monitor",
    "name": "代码提交审查",
    "description": "新代码提交后自动触发评审，不通过则生成修复建议。",
    "category": "智能监控类",
    "icon": "git-branch",
    "trigger_type": "event",
    "trigger_config": {"event_type": "code_push"},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "代码提交触发",
                    "config": {"trigger_type": "event", "event_type": "code_push"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "代码审查Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "审查本次提交的代码：代码规范、安全漏洞、性能问题、逻辑错误。",
                        "title": "代码审查",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "condition",
                    "label": "是否通过",
                    "config": {"expression": "n2.review_result == pass"},
                },
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "审查通过",
                    "config": {"value": "代码审查通过，记录审查结果。", "output_type": "log"},
                },
                "position": {"x": 850, "y": 100},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "修复建议Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "根据审查发现的问题，生成详细的修复建议和代码示例。",
                        "title": "修复建议",
                    },
                },
                "position": {"x": 850, "y": 300},
            },
            {
                "id": "n6",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "发送修复建议",
                    "config": {"value": "将修复建议发送给提交者。", "output_type": "group_message"},
                },
                "position": {"x": 1100, "y": 300},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e2", "source": "n2", "target": "n3", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e3", "source": "n3", "target": "n4", "sourceHandle": "true", "targetHandle": "input"},
            {"id": "e4", "source": "n3", "target": "n5", "sourceHandle": "false", "targetHandle": "input"},
            {"id": "e5", "source": "n5", "target": "n6", "sourceHandle": "output", "targetHandle": "input"},
        ],
    },
}

TEMPLATE_TASK_PROGRESS_AUDIT = {
    "id": "task_progress_audit",
    "name": "任务进度审计",
    "description": "工作日每天上午10点自动检查任务进度，发现卡点及时预警。",
    "category": "智能监控类",
    "icon": "check-circle",
    "trigger_type": "schedule",
    "trigger_config": {"cron": "0 10 * * 1-5", "description": "工作日每天上午10:00"},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "定时触发",
                    "config": {"trigger_type": "schedule", "cron": "0 10 * * 1-5"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "任务审计Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "审计所有进行中任务：检查进度是否滞后、识别阻塞卡点、评估风险等级，生成进度报告。",
                        "title": "任务审计",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "生成进度报告",
                    "config": {"value": "发送任务进度审计报告到群组。", "output_type": "group_message"},
                },
                "position": {"x": 600, "y": 200},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2", "sourceHandle": "output", "targetHandle": "input"},
            {"id": "e2", "source": "n2", "target": "n3", "sourceHandle": "output", "targetHandle": "input"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Layer 3: Task Execution (任务执行类)
# ---------------------------------------------------------------------------

TEMPLATE_CONTENT_CREATION = {
    "id": "content_creation",
    "name": "内容创作流水线",
    "description": "给定主题，AI自动完成选题、写作、SEO检查，人工审核后发布。",
    "category": "任务执行类",
    "icon": "edit",
    "trigger_type": "manual",
    "trigger_config": {},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "手动触发",
                    "config": {"trigger_type": "manual"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "选题Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "根据主题进行选题分析，列出3-5个备选角度，推荐最佳方向。",
                        "title": "选题分析",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "写作Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "根据选定的角度撰写文章，确保结构清晰、论据充分。",
                        "title": "文章撰写",
                    },
                },
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "SEO检查Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "检查文章的SEO质量：关键词密度、标题优化、元描述、可读性，给出优化建议并修改。",
                        "title": "SEO优化",
                    },
                },
                "position": {"x": 850, "y": 200},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "human_review",
                    "label": "人工审核",
                    "config": {"review_type": "approval", "timeout_hours": 24},
                },
                "position": {"x": 1100, "y": 200},
            },
            {
                "id": "n6",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "发布内容",
                    "config": {"value": "将审核通过的文章发布到目标平台。", "output_type": "publish"},
                },
                "position": {"x": 1350, "y": 200},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n4", "target": "n5"},
            {"id": "e5", "source": "n5", "target": "n6"},
        ],
    },
}

TEMPLATE_DATA_ANALYSIS = {
    "id": "data_analysis",
    "name": "数据分析自动化",
    "description": "数据采集 -> 清洗 -> 可视化 -> 异常告警，全流程自动化。",
    "category": "任务执行类",
    "icon": "bar-chart",
    "trigger_type": "manual",
    "trigger_config": {},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "手动触发",
                    "config": {"trigger_type": "manual"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "数据采集Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "从指定数据源采集原始数据，确保数据完整性。",
                        "title": "数据采集",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "数据清洗Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "清洗原始数据：去重、填充缺失值、格式标准化、异常值处理。",
                        "title": "数据清洗",
                    },
                },
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "可视化Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "对清洗后的数据生成可视化图表和分析摘要。",
                        "title": "数据可视化",
                    },
                },
                "position": {"x": 850, "y": 200},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "condition",
                    "label": "是否有异常",
                    "config": {"expression": "n4.has_anomaly == true"},
                },
                "position": {"x": 1100, "y": 200},
            },
            {
                "id": "n6",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "告警Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "针对异常数据生成告警通知，包含异常详情和可能原因。",
                        "title": "异常告警",
                    },
                },
                "position": {"x": 1350, "y": 100},
            },
            {
                "id": "n7",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "输出分析报告",
                    "config": {"value": "输出完整的分析报告和可视化图表。", "output_type": "group_message"},
                },
                "position": {"x": 1350, "y": 300},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n4", "target": "n5"},
            {"id": "e5", "source": "n5", "target": "n6", "sourceHandle": "true"},
            {"id": "e6", "source": "n5", "target": "n7", "sourceHandle": "false"},
            {"id": "e7", "source": "n6", "target": "n7"},
        ],
    },
}

TEMPLATE_GIT_WORKFLOW = {
    "id": "git_workflow",
    "name": "Git 工作流自动化",
    "description": "从创建分支到发起PR全自动：代码生成 -> 测试 -> PR描述。",
    "category": "任务执行类",
    "icon": "git-pull-request",
    "trigger_type": "manual",
    "trigger_config": {},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "手动触发",
                    "config": {"trigger_type": "manual"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "代码生成Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "根据需求描述生成代码，创建feature分支，提交代码变更。",
                        "title": "代码生成",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "测试Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "运行单元测试和集成测试，验证代码正确性，修复失败的测试。",
                        "title": "自动化测试",
                    },
                },
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "PR描述Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "生成Pull Request描述：变更摘要、测试结果、影响范围、检查清单。",
                        "title": "PR描述",
                    },
                },
                "position": {"x": 850, "y": 200},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "发起PR",
                    "config": {"value": "自动发起Pull Request并通知团队成员。", "output_type": "group_message"},
                },
                "position": {"x": 1100, "y": 200},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n4", "target": "n5"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Layer 4: Multi-Agent Collaboration (多Agent协作类)
# ---------------------------------------------------------------------------

TEMPLATE_AGENT_RESEARCH_TEAM = {
    "id": "agent_research_team",
    "name": "子Agent研究团队",
    "description": "3个Agent并行研究不同维度，汇总结果形成综合报告。",
    "category": "多Agent协作类",
    "icon": "users",
    "trigger_type": "manual",
    "trigger_config": {},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "手动触发",
                    "config": {"trigger_type": "manual"},
                },
                "position": {"x": 100, "y": 250},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "关键词分析Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "分析研究主题的关键词，提取核心概念和关联术语。",
                        "title": "关键词分析",
                    },
                },
                "position": {"x": 350, "y": 100},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "竞品分析Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "分析竞品在研究主题上的布局和优势。",
                        "title": "竞品分析",
                    },
                },
                "position": {"x": 350, "y": 250},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "历史分析Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "分析研究主题的历史演变和趋势。",
                        "title": "历史分析",
                    },
                },
                "position": {"x": 350, "y": 400},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "汇总Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "汇总三个Agent的研究结果，去重整合，生成综合研究报告。",
                        "title": "结果汇总",
                    },
                },
                "position": {"x": 600, "y": 250},
            },
            {
                "id": "n6",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "输出研究报告",
                    "config": {"value": "将综合研究报告发送到群组。", "output_type": "group_message"},
                },
                "position": {"x": 850, "y": 250},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n1", "target": "n3"},
            {"id": "e3", "source": "n1", "target": "n4"},
            {"id": "e4", "source": "n2", "target": "n5"},
            {"id": "e5", "source": "n3", "target": "n5"},
            {"id": "e6", "source": "n4", "target": "n5"},
            {"id": "e7", "source": "n5", "target": "n6"},
        ],
    },
}

TEMPLATE_KANBAN_DEVELOPMENT = {
    "id": "kanban_development",
    "name": "Kanban协作开发",
    "description": "5个AI同时协作：需求调研、测试编写、代码审查、测试执行、报告汇总。",
    "category": "多Agent协作类",
    "icon": "layout",
    "trigger_type": "manual",
    "trigger_config": {},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "手动触发",
                    "config": {"trigger_type": "manual"},
                },
                "position": {"x": 100, "y": 300},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "需求调研Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "调研需求背景、技术可行性和竞品方案。",
                        "title": "需求调研",
                    },
                },
                "position": {"x": 350, "y": 50},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "测试编写Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "根据需求编写单元测试用例和集成测试用例。",
                        "title": "测试编写",
                    },
                },
                "position": {"x": 350, "y": 175},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "代码审查Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "审查代码质量、安全性和性能，生成审查报告。",
                        "title": "代码审查",
                    },
                },
                "position": {"x": 350, "y": 300},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "测试执行Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "执行全部测试用例，记录测试结果和覆盖率。",
                        "title": "测试执行",
                    },
                },
                "position": {"x": 350, "y": 425},
            },
            {
                "id": "n6",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "报告汇总Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "汇总各Agent的输出，生成完整的开发协作报告。",
                        "title": "报告汇总",
                    },
                },
                "position": {"x": 350, "y": 550},
            },
            {
                "id": "n7",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "整合Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "整合所有Agent的产出，去重合并，形成最终交付物。",
                        "title": "结果整合",
                    },
                },
                "position": {"x": 600, "y": 300},
            },
            {
                "id": "n8",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "输出交付物",
                    "config": {"value": "将整合后的协作成果发送到群组。", "output_type": "group_message"},
                },
                "position": {"x": 850, "y": 300},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n1", "target": "n3"},
            {"id": "e3", "source": "n1", "target": "n4"},
            {"id": "e4", "source": "n1", "target": "n5"},
            {"id": "e5", "source": "n1", "target": "n6"},
            {"id": "e6", "source": "n2", "target": "n7"},
            {"id": "e7", "source": "n3", "target": "n7"},
            {"id": "e8", "source": "n4", "target": "n7"},
            {"id": "e9", "source": "n5", "target": "n7"},
            {"id": "e10", "source": "n6", "target": "n7"},
            {"id": "e11", "source": "n7", "target": "n8"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Layer 5: Continuous Evolution (持续进化类)
# ---------------------------------------------------------------------------

TEMPLATE_SKILL_AUTO_GENERATION = {
    "id": "skill_auto_generation",
    "name": "技能自生成",
    "description": "从重复任务中自动分析模式，提炼出可复用的Agent技能。",
    "category": "持续进化类",
    "icon": "zap",
    "trigger_type": "manual",
    "trigger_config": {},
    "definition": {
        "nodes": [
            {
                "id": "n1",
                "type": "custom",
                "data": {
                    "nodeType": "trigger",
                    "label": "手动触发",
                    "config": {"trigger_type": "manual"},
                },
                "position": {"x": 100, "y": 200},
            },
            {
                "id": "n2",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "任务分析Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "分析历史重复任务，提取任务模式、输入输出结构和执行流程。",
                        "title": "任务分析",
                    },
                },
                "position": {"x": 350, "y": 200},
            },
            {
                "id": "n3",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "模式识别Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "识别可复用的执行模式，归纳可参数化的通用流程。",
                        "title": "模式识别",
                    },
                },
                "position": {"x": 600, "y": 200},
            },
            {
                "id": "n4",
                "type": "custom",
                "data": {
                    "nodeType": "ai",
                    "label": "技能提炼Agent",
                    "config": {
                        "agent_id": "",
                        "prompt": "将识别出的模式提炼为可复用的Agent技能，生成技能定义和配置。",
                        "title": "技能提炼",
                    },
                },
                "position": {"x": 850, "y": 200},
            },
            {
                "id": "n5",
                "type": "custom",
                "data": {
                    "nodeType": "output",
                    "label": "生成新Skill",
                    "config": {
                        "value": "输出新技能的定义文档，提示用户确认后注册到技能库。",
                        "output_type": "skill_definition",
                    },
                },
                "position": {"x": 1100, "y": 200},
            },
        ],
        "edges": [
            {"id": "e1", "source": "n1", "target": "n2"},
            {"id": "e2", "source": "n2", "target": "n3"},
            {"id": "e3", "source": "n3", "target": "n4"},
            {"id": "e4", "source": "n4", "target": "n5"},
        ],
    },
}

# ---------------------------------------------------------------------------
# Master template list
# ---------------------------------------------------------------------------

PRESET_TEMPLATES: list[dict] = [
    # Layer 1: Scheduled Tasks
    TEMPLATE_MORNING_BRIEFING,
    TEMPLATE_SERVER_HEALTH_CHECK,
    TEMPLATE_WEEKLY_REPORT,
    # Layer 2: Intelligent Monitoring
    TEMPLATE_COMPETITOR_MONITOR,
    TEMPLATE_CODE_REVIEW_MONITOR,
    TEMPLATE_TASK_PROGRESS_AUDIT,
    # Layer 3: Task Execution
    TEMPLATE_CONTENT_CREATION,
    TEMPLATE_DATA_ANALYSIS,
    TEMPLATE_GIT_WORKFLOW,
    # Layer 4: Multi-Agent Collaboration
    TEMPLATE_AGENT_RESEARCH_TEAM,
    TEMPLATE_KANBAN_DEVELOPMENT,
    # Layer 5: Continuous Evolution
    TEMPLATE_SKILL_AUTO_GENERATION,
]


def get_template_by_id(template_id: str) -> dict | None:
    """Get a preset template by its ID."""
    for template in PRESET_TEMPLATES:
        if template["id"] == template_id:
            return template
    return None


def get_all_templates() -> list[dict]:
    """Return all 12 preset templates."""
    return PRESET_TEMPLATES


def get_templates_by_category(category: str) -> list[dict]:
    """Return templates filtered by category."""
    return [t for t in PRESET_TEMPLATES if t["category"] == category]