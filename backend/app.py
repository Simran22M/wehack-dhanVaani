"""
VocalBridge Flask Backend
Wraps the Sarvam AI Dubbing API with two endpoints:
  POST /submit-job              - Create, upload & start a dubbing job
  GET  /job-status/<job_id>     - Poll live status of a running job
"""

import os
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
SARVAM_BASE_URL = "https://api.sarvam.ai"


def _get_headers_json():
    """Build JSON auth headers freshly so hot-reload picks up env changes."""
    key = os.environ.get("SARVAM_API_KEY", SARVAM_API_KEY)
    return {
        "api-subscription-key": key,
        "Content-Type": "application/json",
    }


def _get_headers_auth():
    key = os.environ.get("SARVAM_API_KEY", SARVAM_API_KEY)
    return {"api-subscription-key": key}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sarvam_error(message: str, status_code: int = 500):
    """Return a consistent JSON error response."""
    return jsonify({"error": message}), status_code


# ---------------------------------------------------------------------------
# POST /submit-job
# ---------------------------------------------------------------------------
@app.route("/submit-job", methods=["POST"])
def submit_job():
    """
    Accepts (multipart/form-data):
      - audio_file            (file, required)
      - target_language_code  (str, required)  e.g. "hi-IN"
      - source_language_code  (str, optional, default "en-IN")
      - num_speakers          (int, optional, default 1)

    Workflow:
      1. POST /dubbing/jobs             -> get job_id + signed upload_url
      2. PUT  <upload_url>              -> stream raw audio bytes to GCS
      3. POST /dubbing/jobs/{id}/start  -> queue the pipeline
    """

    # -- 1. Validate inputs ---------------------------------------------------
    audio_file = request.files.get("audio_file")
    if not audio_file:
        return _sarvam_error("Missing required field: audio_file", 400)

    target_language_code = request.form.get("target_language_code", "").strip()
    if not target_language_code:
        return _sarvam_error("Missing required field: target_language_code", 400)

    source_language_code = request.form.get("source_language_code", "en-IN").strip()

    try:
        num_speakers = int(request.form.get("num_speakers", 1))
    except ValueError:
        return _sarvam_error("num_speakers must be an integer", 400)

    api_key = os.environ.get("SARVAM_API_KEY", SARVAM_API_KEY)
    if not api_key:
        return _sarvam_error("Server is missing SARVAM_API_KEY configuration", 500)

    # -- 2. Create the dubbing job --------------------------------------------
    create_payload = {
        "source_language_code": source_language_code,
        "target_language_codes": [target_language_code],
        "num_speakers": num_speakers,
        "editor_flow": False,   # auto-produce exports; most cost-effective
    }

    create_resp = requests.post(
        f"{SARVAM_BASE_URL}/dubbing/jobs",
        json=create_payload,
        headers=_get_headers_json(),
        timeout=30,
    )

    if not create_resp.ok:
        return _sarvam_error(
            f"Sarvam create-job failed ({create_resp.status_code}): {create_resp.text}",
            502,
        )

    create_data = create_resp.json()
    job_id = create_data.get("job_id")
    upload_url = create_data.get("upload_url")

    if not job_id or not upload_url:
        return _sarvam_error(
            f"Unexpected response from Sarvam create-job: {create_data}",
            502,
        )

    # -- 3. Upload the audio to the signed URL --------------------------------
    audio_bytes = audio_file.read()
    audio_content_type = audio_file.content_type or "audio/mpeg"

    upload_resp = requests.put(
        upload_url,
        data=audio_bytes,
        headers={"Content-Type": audio_content_type},
        timeout=120,
    )

    if not upload_resp.ok:
        return _sarvam_error(
            f"Upload to signed URL failed ({upload_resp.status_code}): {upload_resp.text}",
            502,
        )

    # -- 4. Start the pipeline ------------------------------------------------
    start_resp = requests.post(
        f"{SARVAM_BASE_URL}/dubbing/jobs/{job_id}/start",
        headers=_get_headers_auth(),
        timeout=30,
    )

    if not start_resp.ok:
        return _sarvam_error(
            f"Sarvam start-job failed ({start_resp.status_code}): {start_resp.text}",
            502,
        )

    return jsonify({
        "job_id": job_id,
        "status": "queued",
        "message": "Job created, file uploaded, and pipeline started successfully.",
        "target_language_code": target_language_code,
        "source_language_code": source_language_code,
    }), 202


# ---------------------------------------------------------------------------
# GET /job-status/<job_id>
# ---------------------------------------------------------------------------
@app.route("/job-status/<job_id>", methods=["GET"])
def job_status(job_id: str):
    """
    Polls Sarvam live-status endpoint for the given job_id and returns the
    raw Sarvam JSON, guaranteed to include a top-level "job_id" field.

    Possible status values returned by Sarvam:
      not_started | queued | in_progress | completed | partial_failure | failed | deleted

    When status is "completed" or "partial_failure", Sarvam may also return
    export/download URLs which are forwarded transparently.
    """

    api_key = os.environ.get("SARVAM_API_KEY", SARVAM_API_KEY)
    if not api_key:
        return _sarvam_error("Server is missing SARVAM_API_KEY configuration", 500)

    live_status_resp = requests.get(
        f"{SARVAM_BASE_URL}/dubbing/jobs/{job_id}/live-status",
        headers=_get_headers_auth(),
        timeout=30,
    )

    if not live_status_resp.ok:
        return _sarvam_error(
            f"Sarvam live-status failed ({live_status_resp.status_code}): {live_status_resp.text}",
            502,
        )

    sarvam_data = live_status_resp.json()
    # Ensure job_id is always present in our response for client convenience
    sarvam_data.setdefault("job_id", job_id)

    return jsonify(sarvam_data), 200


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "vocalbridge-backend"}), 200


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV", "production") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
