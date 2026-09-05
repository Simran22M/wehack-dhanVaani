import os
import sqlite3

DB_NAME = "app.db"
SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")


def seed_database(db_path: str = DB_NAME) -> None:
    """Initializes the SQLite database using schema.sql and populates mock data."""
    if not os.path.exists(SCHEMA_FILE):
        raise FileNotFoundError(f"Schema file not found at {SCHEMA_FILE}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    with conn:
        # Execute schema script
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            conn.executescript(f.read())

        cursor = conn.cursor()

        # Insert at least 2 sample coordinators
        sample_coordinators = [
            (
                1,
                "Aarav Sharma",
                "North Region (Delhi)",
                "https://storage.googleapis.com/vocalbridge-samples/aarav_voice.wav",
            ),
            (
                2,
                "Priya Nair",
                "South Region (Kerala)",
                "https://storage.googleapis.com/vocalbridge-samples/priya_voice.wav",
            ),
        ]

        cursor.executemany(
            """
            INSERT OR REPLACE INTO coordinators (coordinator_id, name, region, voice_sample_url)
            VALUES (?, ?, ?, ?)
            """,
            sample_coordinators,
        )

        # Insert at least 2 sample dubbing_jobs linked to coordinators
        sample_jobs = [
            (
                "job_001",
                1,
                "https://storage.googleapis.com/vocalbridge-samples/lecture_hi.wav",
                "en",
                "COMPLETED",
                "https://storage.googleapis.com/vocalbridge-samples/lecture_en_dubbed.wav",
                "2026-09-05 10:00:00",
                "2026-09-05 10:15:30",
            ),
            (
                "job_002",
                2,
                "https://storage.googleapis.com/vocalbridge-samples/workshop_ml.wav",
                "ta",
                "PENDING",
                None,
                "2026-09-05 11:00:00",
                None,
            ),
        ]

        cursor.executemany(
            """
            INSERT OR REPLACE INTO dubbing_jobs (
                job_id,
                coordinator_id,
                source_audio_url,
                target_lang,
                status,
                output_audio_url,
                created_at,
                completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sample_jobs,
        )

    conn.close()
    print("Database schema created and seeded successfully in app.db!")


if __name__ == "__main__":
    seed_database()
