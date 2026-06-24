"""
SQLite -> PostgreSQL migration script.

Reads all data from the existing SQLite database and copies it into PostgreSQL.
Uses SQLAlchemy metadata to create tables in PostgreSQL automatically.

Usage:
    python scripts/migrate_to_pg.py --pg-url "postgresql+asyncpg://user:pass@host:5432/aibond"

The SQLite database path defaults to ./aibond.db (relative to backend/).
Use --sqlite-path to override.
"""

import argparse
import asyncio
import sys
import os

# Ensure backend/ is on sys.path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker


# ── Models import (registers all models with Base.metadata) ──────────────────
from app.database import Base
from app.models.models import (  # noqa: F401  – needed for metadata registration
    User,
    Agent,
    Group,
    GroupMember,
    Session,
    SessionMember,
    Message,
    Workflow,
    WorkflowInstance,
    File,
    OfflineMessage,
)

# Ordered list of tables – respects foreign-key dependencies
TABLE_ORDER = [
    "users",
    "agents",
    "groups",
    "group_members",
    "sessions",
    "session_members",
    "messages",
    "workflows",
    "workflow_instances",
    "files",
    "offline_messages",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL")
    parser.add_argument(
        "--pg-url",
        required=True,
        help="PostgreSQL connection URL, e.g. postgresql+asyncpg://user:pass@host:5432/aibond",
    )
    parser.add_argument(
        "--sqlite-path",
        default="sqlite+aiosqlite:///./aibond.db",
        help="SQLite connection URL (default: sqlite+aiosqlite:///./aibond.db)",
    )
    return parser.parse_args()


async def migrate(pg_url: str, sqlite_url: str):
    # ── Create engines ──────────────────────────────────────────────────────
    sqlite_engine = create_async_engine(
        sqlite_url, connect_args={"check_same_thread": False}
    )
    pg_engine = create_async_engine(pg_url)

    sqlite_session_factory = async_sessionmaker(
        sqlite_engine, class_=AsyncSession, expire_on_commit=False
    )
    pg_session_factory = async_sessionmaker(
        pg_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with sqlite_engine.begin() as pg_conn:
        # ── Create all tables in PostgreSQL (drops existing!) ────────────────
        print("[1/3] Creating tables in PostgreSQL ...")
        await pg_conn.run_sync(Base.metadata.create_all)
        print("       Tables created successfully.")

    # ── Copy data table by table ─────────────────────────────────────────────
    print("[2/3] Copying data from SQLite to PostgreSQL ...")
    async with sqlite_session_factory() as sqlite_session:
        async with pg_session_factory() as pg_session:
            for table_name in TABLE_ORDER:
                table_cls = Base.metadata.tables[table_name]
                result = await sqlite_session.execute(
                    select(table_cls)
                )
                rows = result.scalars().all()
                if not rows:
                    print(f"       {table_name}: 0 rows (skipped)")
                    continue

                # Convert each ORM row to a plain dict and insert
                count = 0
                for row in rows:
                    data = {c.name: getattr(row, c.name) for c in table_cls.columns}
                    pg_session.add(table_cls(**data))
                    count += 1
                    # Flush in batches to avoid huge memory usage
                    if count % 500 == 0:
                        await pg_session.flush()

                await pg_session.flush()
                print(f"       {table_name}: {count} rows copied")

            await pg_session.commit()

    # ── Verify row counts ────────────────────────────────────────────────────
    print("[3/3] Verifying row counts ...")
    async with sqlite_session_factory() as sqlite_session:
        async with pg_session_factory() as pg_session:
            all_ok = True
            for table_name in TABLE_ORDER:
                table_cls = Base.metadata.tables[table_name]
                sqlite_count = (await sqlite_session.execute(
                    select(text(f"COUNT(*)")).select_from(table_cls)
                )).scalar()
                pg_count = (await pg_session.execute(
                    select(text(f"COUNT(*)")).select_from(table_cls)
                )).scalar()

                status = "OK" if sqlite_count == pg_count else "MISMATCH"
                if status != "OK":
                    all_ok = False
                print(f"       {table_name}: SQLite={sqlite_count}  PG={pg_count}  [{status}]")

    # ── Cleanup ──────────────────────────────────────────────────────────────
    await sqlite_engine.dispose()
    await pg_engine.dispose()

    if all_ok:
        print("\nMigration completed successfully!")
    else:
        print("\nMigration completed with row-count mismatches – please verify.")
        sys.exit(1)


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(migrate(args.pg_url, args.sqlite_path))
