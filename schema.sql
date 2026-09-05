CREATE TABLE IF NOT EXISTS coordinators (
    coordinator_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    region TEXT,
    voice_sample_url TEXT
);

CREATE TABLE IF NOT EXISTS dubbing_jobs (
    job_id TEXT PRIMARY KEY,
    coordinator_id INTEGER,
    source_audio_url TEXT,
    target_lang TEXT NOT NULL,
    status TEXT NOT NULL,
    output_audio_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (coordinator_id) REFERENCES coordinators(coordinator_id)
);
