import os
import sqlite3
from typing import Any, Dict, List, Optional

DB_NAME = os.getenv("DATABASE_URL", "app.db")


def _get_db_path(custom_path: Optional[str] = None) -> str:
    """Resolves database path from parameter or environment variable."""
    if custom_path:
        return custom_path
    db_url = os.getenv("DATABASE_URL", "app.db")
    if db_url.startswith("sqlite:///"):
        return db_url[len("sqlite:///") :]
    return db_url


class ClosingConnection(sqlite3.Connection):
    """A sqlite3 Connection that manages transactions and automatically

    closes upon exiting the top-level context manager.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._context_depth = 0

    def __enter__(self) -> "ClosingConnection":
        self._context_depth += 1
        return super().__enter__()

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Optional[bool]:
        try:
            return super().__exit__(exc_type, exc_val, exc_tb)
        finally:
            self._context_depth -= 1
            if self._context_depth <= 0:
                self.close()


def get_db(db_path: Optional[str] = None) -> ClosingConnection:
    """Returns a database connection with dictionary-like row access and foreign keys enabled."""
    target_path = _get_db_path(db_path)
    conn = sqlite3.connect(target_path, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(
    schema_path: Optional[str] = None, db_path: Optional[str] = None
) -> None:
    """Reads schema.sql and creates the database tables."""
    if schema_path is None:
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if not os.path.exists(schema_path):
            schema_path = "schema.sql"

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    with get_db(db_path) as conn:
        conn.executescript(schema_sql)
    print("Database initialized successfully!")


def insert_coordinator(
    coordinator_id: int,
    name: str,
    region: Optional[str] = None,
    voice_sample_url: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Inserts a new coordinator into the database."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO coordinators (coordinator_id, name, region, voice_sample_url)
            VALUES (?, ?, ?, ?)
            """,
            (coordinator_id, name, region, voice_sample_url),
        )


def insert_job(
    job_id: str,
    coordinator_id: int,
    target_lang: str,
    source_audio_url: Optional[str] = None,
    status: str = "PENDING",
    db_path: Optional[str] = None,
) -> None:
    """Inserts a new dubbing job into the database."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO dubbing_jobs (job_id, coordinator_id, target_lang, source_audio_url, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (job_id, coordinator_id, target_lang, source_audio_url, status),
        )


def update_job_status(
    job_id: str,
    status: str,
    output_url: Optional[str] = None,
    db_path: Optional[str] = None,
) -> None:
    """Updates status and optionally output_audio_url and completed_at."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        if output_url is not None:
            cursor.execute(
                """
                UPDATE dubbing_jobs
                SET status = ?, output_audio_url = ?, completed_at = CURRENT_TIMESTAMP
                WHERE job_id = ?
                """,
                (status, output_url, job_id),
            )
        else:
            cursor.execute(
                """
                UPDATE dubbing_jobs
                SET status = ?
                WHERE job_id = ?
                """,
                (status, job_id),
            )


def get_jobs_by_coordinator(
    coordinator_id: int, db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetches and returns all jobs for a coordinator as a list of dicts."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM dubbing_jobs WHERE coordinator_id = ?",
            (coordinator_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_job(
    job_id: str, db_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Fetches a single job by job_id as a dict or None."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM dubbing_jobs WHERE job_id = ?",
            (job_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


if __name__ == "__main__":
    init_db()
