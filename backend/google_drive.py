

import json
import io
import os
from datetime import datetime
from typing import Optional

DRIVE_FOLDER_NAME    = "BloomQuizResearch"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service_account.json")

# Sub-folder names inside BloomQuizResearch
SUBFOLDER_SESSIONS   = "quiz_sessions"
SUBFOLDER_EVALUATION = "evaluation_results"
SUBFOLDER_EXPORTS    = "exports"


def _get_service():
    """Build and return the Drive API service. Returns None if not configured."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            return None

        creds = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE,
            scopes=["https://www.googleapis.com/auth/drive"],
        )
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None


def _get_or_create_folder(service, name: str, parent_id: Optional[str] = None) -> Optional[str]:
    """Return folder ID, creating it if it doesn't exist."""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files   = results.get("files", [])
    if files:
        return files[0]["id"]

    meta = {
        "name":     name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        meta["parents"] = [parent_id]

    folder = service.files().create(body=meta, fields="id").execute()
    return folder.get("id")


YOUR_PERSONAL_EMAIL = "sharathmedijala@gmail.com"  # ← put your Gmail here at the top of the file

def _upload_json(service, folder_id: str, filename: str, data: dict) -> Optional[str]:
    from googleapiclient.http import MediaIoBaseUpload

    content   = json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")
    media     = MediaIoBaseUpload(io.BytesIO(content), mimetype="application/json")
    file_meta = {"name": filename, "parents": [folder_id]}
    result    = service.files().create(
        body=file_meta, media_body=media, fields="id, webViewLink"
    ).execute()

    file_id = result.get("id")

    # Share with your personal Gmail so you can see it
    try:
        service.permissions().create(
            fileId=file_id,
            body={
                "type":         "user",
                "role":         "writer",
                "emailAddress": YOUR_PERSONAL_EMAIL,
            },
            sendNotificationEmail=False,
        ).execute()
    except Exception:
        pass

    return result.get("webViewLink")



def is_configured() -> bool:
    """Check whether Drive is properly set up."""
    return os.path.exists(SERVICE_ACCOUNT_FILE)


def save_quiz_session(session_data: dict) -> dict:
    """
    Save a complete quiz session to Drive.
    session_data should include: topic, model, bloom_level, questions, scores, latency_sec
    Returns {"saved": bool, "link": str|None, "error": str|None}
    """
    service = _get_service()
    if not service:
        return {"saved": False, "link": None, "error": "Drive not configured"}

    try:
        root_id    = _get_or_create_folder(service, DRIVE_FOLDER_NAME)
        folder_id  = _get_or_create_folder(service, SUBFOLDER_SESSIONS, root_id)

        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        topic_slug = session_data.get("topic", "unknown")[:30].replace(" ", "_")
        level      = session_data.get("bloom_level", "?")
        model_slug = session_data.get("model", "unknown")[:20].replace(" ", "_")
        filename   = f"{timestamp}_L{level}_{topic_slug}_{model_slug}.json"

        session_data["saved_at"] = datetime.now().isoformat()
        link = _upload_json(service, folder_id, filename, session_data)
        return {"saved": True, "link": link, "error": None}
    except Exception as e:
        return {"saved": False, "link": None, "error": str(e)}


def save_evaluation_result(eval_data: dict) -> dict:
    """
    Save an LLM × Bloom evaluation result row.
    eval_data: {model, bloom_level, topic, questions, classifier_scores, latency_sec, ...}
    """
    service = _get_service()
    if not service:
        return {"saved": False, "link": None, "error": "Drive not configured"}

    try:
        root_id   = _get_or_create_folder(service, DRIVE_FOLDER_NAME)
        folder_id = _get_or_create_folder(service, SUBFOLDER_EVALUATION, root_id)

        timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_slug = eval_data.get("model", "unknown")[:20].replace(" ", "_")
        level      = eval_data.get("bloom_level", "?")
        filename   = f"{timestamp}_eval_L{level}_{model_slug}.json"

        eval_data["saved_at"] = datetime.now().isoformat()
        link = _upload_json(service, folder_id, filename, eval_data)
        return {"saved": True, "link": link, "error": None}
    except Exception as e:
        return {"saved": False, "link": None, "error": str(e)}


def save_export(export_data: dict, label: str = "export") -> dict:
    """Save a bulk export (all sessions, comparison table, etc.)."""
    service = _get_service()
    if not service:
        return {"saved": False, "link": None, "error": "Drive not configured"}

    try:
        root_id   = _get_or_create_folder(service, DRIVE_FOLDER_NAME)
        folder_id = _get_or_create_folder(service, SUBFOLDER_EXPORTS, root_id)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename  = f"{timestamp}_{label}.json"
        link      = _upload_json(service, folder_id, filename, export_data)
        return {"saved": True, "link": link, "error": None}
    except Exception as e:
        return {"saved": False, "link": None, "error": str(e)}


def list_saved_sessions() -> list:
    """Return list of saved session files from Drive."""
    service = _get_service()
    if not service:
        return []

    try:
        root_id   = _get_or_create_folder(service, DRIVE_FOLDER_NAME)
        folder_id = _get_or_create_folder(service, SUBFOLDER_SESSIONS, root_id)

        results = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, createdTime, webViewLink)",
            orderBy="createdTime desc",
            pageSize=50,
        ).execute()

        return results.get("files", [])
    except Exception:
        return []
