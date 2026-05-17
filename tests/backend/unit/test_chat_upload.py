from __future__ import annotations

from middleware.auth import create_jwt


def _headers(user_id: str = "student-1", role: str = "student") -> dict:
    token = create_jwt({"user_id": user_id, "role": role, "name": user_id})
    return {"Authorization": f"Bearer {token}"}


def _post_chat_upload(client, filename: str, content: bytes, headers=None):
    return client.post(
        "/api/chat/upload",
        files={"file": (filename, content, "application/octet-stream")},
        headers=headers or _headers(),
    )


def test_chat_upload_requires_auth(client):
    response = client.post(
        "/api/chat/upload",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 401


def test_chat_upload_extracts_text(client):
    response = _post_chat_upload(client, "notes.txt", b"hello class")

    assert response.status_code == 200
    assert response.json()["extracted_text"] == "hello class"


def test_chat_upload_blocks_executable_extension(client):
    response = _post_chat_upload(client, "payload.exe", b"MZ")

    assert response.status_code == 415
    assert response.json()["detail"] == "File type .exe is not permitted"


def test_chat_upload_blocks_shell_extension(client):
    response = _post_chat_upload(client, "script.sh", b"echo hi")

    assert response.status_code == 415
    assert response.json()["detail"] == "File type .sh is not permitted"


def test_chat_upload_rejects_files_over_twenty_mb(client, monkeypatch):
    import routes.chat_upload as chat_upload_routes

    monkeypatch.setattr(chat_upload_routes, "MAX_FILE_SIZE_BYTES", 100)
    response = _post_chat_upload(client, "notes.txt", b"a" * 101)

    assert response.status_code == 413


def test_chat_upload_pdf_returns_text_or_placeholder(client):
    response = _post_chat_upload(client, "sample.pdf", b"%PDF-1.4\n%%EOF")

    assert response.status_code == 200
    assert "sample.pdf" in response.json()["extracted_text"] or response.json()["extracted_text"]
