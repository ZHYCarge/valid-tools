import sqlite3
from typing import Any, Dict, List, Optional


def fetch_by_hash(conn: sqlite3.Connection, hash_value: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM evidences WHERE hash = ?", (hash_value,)).fetchone()
    return dict(row) if row else None


def list_all(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = conn.execute("SELECT * FROM evidences ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]


def insert_or_ignore(conn: sqlite3.Connection, payload: Dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO evidences (
            hash, ots_status, tsa_status, ots_path, tsa_path, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
        """,
        (
            payload["hash"],
            payload["ots_status"],
            payload["tsa_status"],
            payload.get("ots_path"),
            payload.get("tsa_path"),
        ),
    )
    conn.commit()


def update_statuses(
    conn: sqlite3.Connection,
    hash_value: str,
    ots_status: str,
    tsa_status: str,
    ots_path: Optional[str],
    tsa_path: Optional[str],
) -> None:
    conn.execute(
        """
        UPDATE evidences
        SET ots_status = ?, tsa_status = ?, ots_path = ?, tsa_path = ?, updated_at = datetime('now')
        WHERE hash = ?
        """,
        (ots_status, tsa_status, ots_path, tsa_path, hash_value),
    )
    conn.commit()


def delete_by_hash(conn: sqlite3.Connection, hash_value: str) -> None:
    conn.execute("DELETE FROM evidences WHERE hash = ?", (hash_value,))
    conn.commit()
