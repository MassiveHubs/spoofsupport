import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "support.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Main tickets table — no UNIQUE on user_id so multiple tickets per user are allowed
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT NULL,
                thread_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                claimed_by INTEGER DEFAULT NULL,
                silent INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS allowed_users (
                thread_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (thread_id, user_id)
            )
        """)
        # Migration: add columns if upgrading from old schema
        for col, definition in [
            ("username", "TEXT DEFAULT NULL"),
            ("silent", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            try:
                await db.execute(f"ALTER TABLE tickets ADD COLUMN {col} {definition}")
            except Exception:
                pass  # column already exists
        await db.commit()

# ── Tickets ───────────────────────────────────────────────────────────────────

async def get_active_ticket_by_user(user_id: int) -> dict | None:
    """Return the latest open ticket for this user, or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tickets WHERE user_id = ? AND status = 'open' ORDER BY id DESC LIMIT 1",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_ticket_by_thread(thread_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tickets WHERE thread_id = ?", (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None

async def get_user_id_by_username(username: str) -> int | None:
    """Find user_id by username stored during ticket creation."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM tickets WHERE username = ? ORDER BY id DESC LIMIT 1",
            (username.lstrip("@").lower(),),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def create_ticket(user_id: int, thread_id: int, username: str | None = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO tickets (user_id, thread_id, username) VALUES (?, ?, ?)",
            (user_id, thread_id, (username or "").lower() if username else None),
        )
        await db.commit()

async def claim_ticket(thread_id: int, moderator_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT claimed_by FROM tickets WHERE thread_id = ?", (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return False
        if row["claimed_by"] is not None and row["claimed_by"] != moderator_id:
            return False
        await db.execute(
            "UPDATE tickets SET claimed_by = ? WHERE thread_id = ?",
            (moderator_id, thread_id),
        )
        await db.execute(
            "INSERT OR IGNORE INTO allowed_users (thread_id, user_id) VALUES (?, ?)",
            (thread_id, moderator_id),
        )
        await db.commit()
        return True

async def unclaim_ticket(thread_id: int, moderator_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT claimed_by FROM tickets WHERE thread_id = ?", (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None or row["claimed_by"] != moderator_id:
            return False
        await db.execute(
            "UPDATE tickets SET claimed_by = NULL WHERE thread_id = ?", (thread_id,)
        )
        await db.execute(
            "DELETE FROM allowed_users WHERE thread_id = ?", (thread_id,)
        )
        await db.commit()
        return True

async def close_ticket(thread_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tickets SET status = 'closed' WHERE thread_id = ?", (thread_id,)
        )
        await db.commit()

async def toggle_silent(thread_id: int) -> bool:
    """Toggle silent mode. Returns the NEW state (True = silent on)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT silent FROM tickets WHERE thread_id = ?", (thread_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if row is None:
            return False
        new_state = 0 if row["silent"] else 1
        await db.execute(
            "UPDATE tickets SET silent = ? WHERE thread_id = ?", (new_state, thread_id)
        )
        await db.commit()
        return bool(new_state)

async def get_all_user_ids() -> list[int]:
    """Return distinct user_ids of everyone who ever opened a ticket."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT DISTINCT user_id FROM tickets"
        ) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def get_ticket_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM tickets") as c:
            total = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM tickets WHERE status='open'") as c:
            open_ = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM tickets") as c:
            users = (await c.fetchone())[0]
    return {"total": total, "open": open_, "closed": total - open_, "users": users}

# ── Allowed users ─────────────────────────────────────────────────────────────

async def add_allowed_user(thread_id: int, user_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO allowed_users (thread_id, user_id) VALUES (?, ?)",
            (thread_id, user_id),
        )
        await db.commit()

async def get_allowed_users(thread_id: int) -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT user_id FROM allowed_users WHERE thread_id = ?", (thread_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def is_allowed(thread_id: int, user_id: int) -> bool:
    allowed = await get_allowed_users(thread_id)
    return user_id in allowed