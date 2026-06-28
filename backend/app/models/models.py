from sqlalchemy import Column, String, Integer, Boolean, DateTime, Float, Text, ForeignKey, JSON, Index, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True)
    hashed_password = Column(String(128), nullable=False)
    display_name = Column(String(100), default="")
    avatar = Column(String(255), default="")
    role = Column(String(20), default="user")  # user, admin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    group_memberships = relationship("GroupMember", back_populates="user")
    messages = relationship("Message", back_populates="sender_user")

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    api_key = Column(String(128), unique=True, nullable=False, index=True)
    description = Column(Text, default="")
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)

    # Capabilities
    skills = Column(JSON, default=list)  # ["code_review", "git_operations"] (legacy)
    tool_schemas = Column(Text, default="[]")  # MCP ToolSchema JSON array (v1.3.0)
    resource_schemas = Column(Text, default="[]")  # MCP ResourceSchema JSON array (v1.3.0)
    mcp_endpoints = Column(JSON, default=list)
    mcp_transport = Column(String(20), default="websocket")  # stdio/sse/websocket (v1.3.0)
    callback_url = Column(String(255), default="")

    # Parliament 角色分工 (v1.2.0)
    agent_role = Column(String(20), default="executor")  # arbiter, reviewer, analyst, executor, observer
    tier = Column(Integer, default=1)  # 1=basic, 2=intermediate, 3=expert (for escalation)
    reliability_score = Column(Float, default=0.5)  # 0.0-1.0, updated by parliament outcomes

    capabilities = Column(JSON, default=lambda: {
        "accepts_websocket": True,
        "accepts_webhook": False,
        "accepts_polling": False
    })

    # CLI Adapter 模式 (v1.4.0 - Trinity Lite 集成)
    adapter_mode = Column(String(20), default="websocket")  # websocket | command | mock
    adapter_command = Column(JSON, default=list)  # CLI 命令数组
    adapter_timeout = Column(Integer, default=1800)  # 超时秒数
    adapter_cwd = Column(String(255), default="")  # 工作目录
    adapter_env = Column(JSON, default=dict)  # 环境变量
    model_tier = Column(String(20), default="standard")  # budget | standard | premium
    model_strengths = Column(JSON, default=list)  # 模型优势标签

    # Status
    status = Column(String(20), default="offline")  # online, offline, busy
    last_heartbeat = Column(DateTime, default=None)
    current_address = Column(String(255), default="")  # current reachable address

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    group_memberships = relationship("GroupMember", back_populates="agent")
    messages = relationship("Message", back_populates="sender_agent")

class Group(Base):
    __tablename__ = "groups"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    avatar = Column(String(255), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    members = relationship("GroupMember", back_populates="group")
    messages = relationship("Message", back_populates="group")
    sessions = relationship("Session", back_populates="group")

class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(String(36), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    role = Column(String(20), default="member")  # owner, lead, member, viewer
    can_auto_reply = Column(Boolean, default=False)  # Agent: can reply without being @mentioned
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="group_memberships")
    agent = relationship("Agent", back_populates="group_memberships")

    __table_args__ = (
        UniqueConstraint('group_id', 'user_id', name='uq_group_user'),
        UniqueConstraint('group_id', 'agent_id', name='uq_group_agent'),
    )

class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=False, index=True)
    title = Column(String(200), default="")
    description = Column(Text, default="")
    status = Column(String(20), default="active", index=True)  # active, paused, completed, cancelled
    priority = Column(String(10), default="normal")  # low, normal, high, urgent

    assigner_id = Column(String(36), default="")      # 分配者 ID
    assigner_type = Column(String(10), default="")    # "user" or "agent"
    assignee_ids = Column(JSON, default=list)           # 被分配者 ID 列表

    context = Column(JSON, default=dict)                # 任务上下文
    parent_session_id = Column(String(36), default="")  # 父会话 ID（子任务）

    progress = Column(Integer, default=0)  # 0-100
    progress_description = Column(Text, default="")
    assigned_at = Column(DateTime, default=None)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, default=None)

    # Relationships
    group = relationship("Group", back_populates="sessions")
    messages = relationship("Message", back_populates="session")
    members = relationship("SessionMember", back_populates="session")


class SessionMember(Base):
    __tablename__ = "session_members"

    id = Column(String(36), primary_key=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    member_type = Column(String(10), nullable=False)  # "user" or "agent"
    member_id = Column(String(36), nullable=False, index=True)
    role = Column(String(20), default="participant")  # participant, observer, lead
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    session = relationship("Session", back_populates="members")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=True, index=True)  # 新增：关联会话
    sender_type = Column(String(10), nullable=False)  # "user" or "agent"
    sender_user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    sender_agent_id = Column(String(36), ForeignKey("agents.id"), nullable=True)

    msg_type = Column(String(20), default="text")  # text, file, system, workflow_trigger, task_assign, task_complete
    content = Column(Text, default="")
    msg_metadata = Column("metadata", JSON, default=dict)  # mentions, files, etc.

    mentions = Column(JSON, default=list)  # 被提及的 agent/user ID 列表
    is_read = Column(Boolean, default=False)

    status = Column(String(20), default="sent")  # sent, delivered, read

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    group = relationship("Group", back_populates="messages")
    session = relationship("Session", back_populates="messages")
    sender_user = relationship("User", back_populates="messages", foreign_keys=[sender_user_id])
    sender_agent = relationship("Agent", back_populates="messages", foreign_keys=[sender_agent_id])

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, default="")
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)

    # Workflow definition (nodes and edges as JSON)
    definition = Column(JSON, default=dict)

    trigger_type = Column(String(20), default="manual")  # manual, message, schedule
    trigger_config = Column(JSON, default=dict)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"

    id = Column(String(36), primary_key=True)
    workflow_id = Column(String(36), ForeignKey("workflows.id"), nullable=False)
    status = Column(String(20), default="running")  # running, paused, completed, failed
    current_node_id = Column(String(36), default="")
    context = Column(JSON, default=dict)  # shared data across nodes
    node_results = Column(JSON, default=list)  # execution history

    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, default=None)


class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True)
    filename = Column(String(255), nullable=False)
    original_name = Column(String(255), nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100), default="")
    uploader_type = Column(String(10), nullable=False)  # user or agent
    uploader_id = Column(String(36), nullable=False, index=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=True)
    storage_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class OfflineMessage(Base):
    __tablename__ = "offline_messages"

    id = Column(String(36), primary_key=True)
    target_type = Column(String(10), nullable=False, index=True)  # user or agent
    target_id = Column(String(36), nullable=False, index=True)
    message_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    delivered_at = Column(DateTime, default=None)

# ── 新增模型 v1.1.0 ──

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String(36), primary_key=True)
    actor_type = Column(String(10), nullable=False)  # user, agent, system
    actor_id = Column(String(36), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # auth.login, group.create, etc.
    target_type = Column(String(50), default="")
    target_id = Column(String(36), default="")
    details = Column(JSON, default=dict)
    ip_address = Column(String(45), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class SocialFriend(Base):
    __tablename__ = "social_friends"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    friend_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending, accepted, rejected
    requested_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SocialMoment(Base):
    __tablename__ = "social_moments"
    id = Column(String(36), primary_key=True)
    author_type = Column(String(10), nullable=False)  # user, agent, system
    author_id = Column(String(36), nullable=False)
    content = Column(Text, default="")
    image_url = Column(String(500), default="")
    visibility = Column(String(20), default="public")  # public, friends, private
    likes = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SocialMomentComment(Base):
    __tablename__ = "social_moment_comments"
    id = Column(String(36), primary_key=True)
    moment_id = Column(String(36), ForeignKey("social_moments.id"), nullable=False)
    author_type = Column(String(10), nullable=False)
    author_id = Column(String(36), nullable=False)
    content = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class AgentHire(Base):
    __tablename__ = "agent_hires"
    id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    hirer_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    hirer_type = Column(String(10), default="user")
    status = Column(String(20), default="active")  # active, revoked
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Template(Base):
    __tablename__ = "templates"
    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    display_name = Column(String(100), default="")
    description = Column(Text, default="")
    config = Column(JSON, default=dict)  # slots, default_agents, etc.
    is_public = Column(Boolean, default=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"
    id = Column(String(36), primary_key=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    cron_expression = Column(String(100), nullable=False)
    timezone = Column(String(50), default="UTC")
    action_type = Column(String(50), nullable=False)  # delegate_task, post_moment, send_message
    action_config = Column(JSON, default=dict)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    last_run_at = Column(DateTime, default=None)
    next_run_at = Column(DateTime, default=None)
    run_count = Column(Integer, default=0)  # 执行次数
    last_result = Column(JSON, default=dict)  # 上次执行结果
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Task(Base):
    __tablename__ = "tasks"
    id = Column(String(36), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default="pending", index=True)  # pending, assigned, in_progress, done, failed, cancelled
    priority = Column(String(10), default="normal")  # low, normal, high, urgent
    assignee_type = Column(String(10), nullable=False)  # user, agent
    assignee_id = Column(String(36), nullable=False, index=True)
    delegator_type = Column(String(10), default="")
    delegator_id = Column(String(36), default="")
    result = Column(JSON, default=dict)
    progress = Column(Integer, default=0)
    due_date = Column(DateTime, default=None)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Review(Base):
    __tablename__ = "reviews"
    id = Column(String(36), primary_key=True)
    task_id = Column(String(36), ForeignKey("tasks.id"), nullable=False)
    reviewer_id = Column(String(36), nullable=False)
    reviewer_type = Column(String(10), default="user")
    conclusion = Column(String(20), default="")  # approved, changes_requested, rejected
    comment = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class GroupResource(Base):
    __tablename__ = "group_resources"
    id = Column(String(36), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=False)
    name = Column(String(200), nullable=False)
    resource_type = Column(String(50), nullable=False)  # repo, env, key, doc, tunnel, url
    value = Column(Text, default="")
    description = Column(Text, default="")
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

# ── v1.2.0 Agent Parliament 议会系统 ──

class Parliament(Base):
    """Agent 议会：多 Agent 协商、投票、共识决策"""
    __tablename__ = "parliaments"

    id = Column(String(36), primary_key=True)
    group_id = Column(String(36), ForeignKey("groups.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    topic = Column(Text, default="")  # 讨论议题
    status = Column(String(20), default="deliberating", index=True)  # deliberating, voting, consensus_reached, deadlocked, escalated, resolved
    consensus_type = Column(String(20), default="majority")  # majority, supermajority(2/3), unanimous, weighted
    min_confidence = Column(Float, default=0.6)  # 最低置信度阈值，低于此值触发升级
    round_count = Column(Integer, default=0)  # 当前协商轮次
    max_rounds = Column(Integer, default=3)  # 最大协商轮次
    resolution = Column(JSON, default=dict)  # 最终决议
    created_by = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    resolved_at = Column(DateTime, default=None)

class ParliamentMember(Base):
    """议会成员：参与协商的 Agent 及其角色/权重"""
    __tablename__ = "parliament_members"

    id = Column(String(36), primary_key=True)
    parliament_id = Column(String(36), ForeignKey("parliaments.id"), nullable=False)
    agent_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    role = Column(String(20), default="voter")  # speaker(主席), voter, reviewer, analyst, observer
    tier = Column(Integer, default=1)  # 1=basic, 2=intermediate, 3=expert
    weight = Column(Float, default=1.0)  # 投票权重 (基于 tier + reliability)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ParliamentProposal(Base):
    """议会提案：各 Agent 提出的方案"""
    __tablename__ = "parliament_proposals"

    id = Column(String(36), primary_key=True)
    parliament_id = Column(String(36), ForeignKey("parliaments.id"), nullable=False, index=True)
    proposer_id = Column(String(36), nullable=False)  # agent_id
    round_number = Column(Integer, default=1)
    content = Column(Text, default="")
    confidence = Column(Float, default=0.5)  # 提案者自身置信度
    status = Column(String(20), default="active")  # active, withdrawn, selected
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ParliamentVote(Base):
    """议会投票记录"""
    __tablename__ = "parliament_votes"

    id = Column(String(36), primary_key=True)
    parliament_id = Column(String(36), ForeignKey("parliaments.id"), nullable=False)
    proposal_id = Column(String(36), ForeignKey("parliament_proposals.id"), nullable=False, index=True)
    voter_id = Column(String(36), nullable=False, index=True)  # agent_id
    round_number = Column(Integer, default=1)
    vote = Column(String(20), nullable=False)  # approve, reject, abstain
    confidence = Column(Float, default=0.5)  # 投票者自身置信度
    reasoning = Column(Text, default="")  # 投票理由
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
