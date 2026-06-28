from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import settings

# Conditional engine args: SQLite needs check_same_thread=False, PostgreSQL does not
engine_args: dict = {}
if settings.DATABASE_URL.startswith("sqlite"):
    engine_args["connect_args"] = {"check_same_thread": False}

# Disable echo in production to prevent SQL leakage in logs
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    **engine_args,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Run migrations for existing databases
    await _migrate_db()

async def _migrate_db():
    """Add missing columns and indexes to existing tables."""
    migrations = [
        # Agent Parliament columns (v1.2.0)
        "ALTER TABLE agents ADD COLUMN agent_role VARCHAR(20) DEFAULT 'executor'",
        "ALTER TABLE agents ADD COLUMN tier INTEGER DEFAULT 1",
        "ALTER TABLE agents ADD COLUMN reliability_score FLOAT DEFAULT 0.5",

        # ── High-frequency query indexes ──

        # Message indexes
        "CREATE INDEX IF NOT EXISTS idx_messages_group_id ON messages(group_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)",

        # Session indexes
        "CREATE INDEX IF NOT EXISTS idx_sessions_group_id ON sessions(group_id)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status)",
        "CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at)",

        # GroupMember indexes
        "CREATE INDEX IF NOT EXISTS idx_group_members_group_id ON group_members(group_id)",
        "CREATE INDEX IF NOT EXISTS idx_group_members_user_id ON group_members(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_group_members_agent_id ON group_members(agent_id)",
        # GroupMember unique constraints (prevent duplicate join)
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_group_user ON group_members(group_id, user_id) WHERE user_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_group_agent ON group_members(group_id, agent_id) WHERE agent_id IS NOT NULL",

        # SessionMember indexes
        "CREATE INDEX IF NOT EXISTS idx_session_members_session_id ON session_members(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_session_members_member_id ON session_members(member_id)",

        # Task indexes
        "CREATE INDEX IF NOT EXISTS idx_tasks_group_id ON tasks(group_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_assignee_id ON tasks(assignee_id)",

        # Parliament indexes
        "CREATE INDEX IF NOT EXISTS idx_parliaments_group_id ON parliaments(group_id)",
        "CREATE INDEX IF NOT EXISTS idx_parliaments_status ON parliaments(status)",
        "CREATE INDEX IF NOT EXISTS idx_parliaments_created_at ON parliaments(created_at)",

        # ParliamentProposal indexes
        "CREATE INDEX IF NOT EXISTS idx_parliament_proposals_parliament_id ON parliament_proposals(parliament_id)",

        # ParliamentVote indexes
        "CREATE INDEX IF NOT EXISTS idx_parliament_votes_proposal_id ON parliament_votes(proposal_id)",
        "CREATE INDEX IF NOT EXISTS idx_parliament_votes_voter_id ON parliament_votes(voter_id)",

        # Workflow indexes
        "CREATE INDEX IF NOT EXISTS idx_workflows_owner_id ON workflows(owner_id)",
        "CREATE INDEX IF NOT EXISTS idx_workflows_group_id ON workflows(group_id)",

        # ScheduledTask new columns (v1.3.0 - Workflow enhancement)
        "ALTER TABLE scheduled_tasks ADD COLUMN run_count INTEGER DEFAULT 0",
        "ALTER TABLE scheduled_tasks ADD COLUMN last_result TEXT DEFAULT '{}'",

        # Agent MCP columns (v1.3.0 - MCP networking)
        "ALTER TABLE agents ADD COLUMN tool_schemas TEXT DEFAULT '[]'",
        "ALTER TABLE agents ADD COLUMN resource_schemas TEXT DEFAULT '[]'",
        "ALTER TABLE agents ADD COLUMN mcp_transport VARCHAR(20) DEFAULT 'websocket'",

        # CLI Adapter columns (v1.4.0 - Trinity Lite integration)
        "ALTER TABLE agents ADD COLUMN adapter_mode VARCHAR(20) DEFAULT 'websocket'",
        "ALTER TABLE agents ADD COLUMN adapter_command TEXT DEFAULT '[]'",
        "ALTER TABLE agents ADD COLUMN adapter_timeout INTEGER DEFAULT 1800",
        "ALTER TABLE agents ADD COLUMN adapter_cwd VARCHAR(255) DEFAULT ''",
        "ALTER TABLE agents ADD COLUMN adapter_env TEXT DEFAULT '{}'",
        "ALTER TABLE agents ADD COLUMN model_tier VARCHAR(20) DEFAULT 'standard'",
        "ALTER TABLE agents ADD COLUMN model_strengths TEXT DEFAULT '[]'",

        # AuditLog indexes
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_id ON audit_logs(actor_id)",
        "CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at)",

        # OfflineMessage indexes
        "CREATE INDEX IF NOT EXISTS idx_offline_messages_target_id ON offline_messages(target_id)",
        "CREATE INDEX IF NOT EXISTS idx_offline_messages_target_type ON offline_messages(target_type)",

        # File indexes
        "CREATE INDEX IF NOT EXISTS idx_files_group_id ON files(group_id)",
        "CREATE INDEX IF NOT EXISTS idx_files_uploader_id ON files(uploader_id)",
    ]
    async with engine.begin() as conn:
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass  # Column already exists, skip

async def get_db():
    async with async_session() as session:
        yield session
