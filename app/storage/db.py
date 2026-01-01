import os
import sqlite3
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Migration:
    version: int
    filename: str
    sql: str


def _migration_dir() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "migrations")
    )


def _load_migrations() -> List[Migration]:
    migrations: List[Migration] = []
    for name in sorted(os.listdir(_migration_dir())):
        if not name.endswith(".sql"):
            continue
        version_text = name.split("_", 1)[0]
        if not version_text.isdigit():
            continue
        version = int(version_text)
        path = os.path.join(_migration_dir(), name)
        with open(path, "r", encoding="utf-8") as handle:
            migrations.append(Migration(version=version, filename=name, sql=handle.read()))
    return migrations


def _ensure_schema_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        """
    )


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def _apply_migration(conn: sqlite3.Connection, migration: Migration) -> None:
    conn.executescript(migration.sql)
    conn.execute(
        "INSERT INTO schema_migrations (version, applied_at) VALUES (?, datetime('now'))",
        (migration.version,),
    )


def migrate(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_schema_table(conn)
        current = _current_version(conn)
        pending = [m for m in _load_migrations() if m.version > current]
        for migration in pending:
            _apply_migration(conn, migration)
        conn.commit()
    finally:
        conn.close()


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

