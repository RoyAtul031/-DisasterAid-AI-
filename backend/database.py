import os
import sqlite3
import aiosqlite
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configure database path. Vercel serverless environment requires writing to the /tmp folder.
if "VERCEL" in os.environ:
    DB_FILE = "/tmp/disasteraid.db"
else:
    DB_FILE = os.path.join(os.path.dirname(__file__), "disasteraid.db")

async def init_db():
    """Initializes the SQLite database tables."""
    async with aiosqlite.connect(DB_FILE) as db:
        # Create sessions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                location TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create messages table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                severity TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        """)
        await db.commit()

async def save_session_location(session_id: str, location: str):
    """Saves or updates the location for a session."""
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT INTO sessions (session_id, location)
            VALUES (?, ?)
            ON CONFLICT(session_id) DO UPDATE SET location = excluded.location
        """, (session_id, location))
        await db.commit()

async def get_session_location(session_id: str) -> Optional[str]:
    """Retrieves the stored location for a session."""
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT location FROM sessions WHERE session_id = ?", (session_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def save_message(session_id: str, role: str, content: str, severity: Optional[str] = None):
    """Saves a message to the database."""
    # Ensure session exists
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("""
            INSERT OR IGNORE INTO sessions (session_id, location)
            VALUES (?, NULL)
        """, (session_id,))
        
        await db.execute("""
            INSERT INTO messages (session_id, role, content, severity)
            VALUES (?, ?, ?, ?)
        """, (session_id, role, content, severity))
        await db.commit()

async def get_chat_history(session_id: str) -> List[Dict[str, Any]]:
    """Retrieves all messages in chronological order for a session."""
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = sqlite3.Row
        async with db.execute("""
            SELECT role, content, severity, timestamp 
            FROM messages 
            WHERE session_id = ? 
            ORDER BY timestamp ASC
        """, (session_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
