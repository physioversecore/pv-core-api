from datetime import datetime
from types import SimpleNamespace

NOW = datetime(2024, 6, 15, 10, 30, 0)

PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00"


def _therapist(media_urls: str = ""):
    return SimpleNamespace(
        id="therapist-1",
        userId="therapist-user-1",
        name="Dr. Therapist",
        specialty="Physiotherapy",
        city="Kathmandu",
        gender="Male",
        price=1500.0,
        experience=5,
        bio="",
        mediaUrls=media_urls,
        createdAt=NOW,
        updatedAt=NOW,
    )


class TestTherapistPhoto:
    def test_upload_photo(self, therapist_client, mock_db, tmp_path, monkeypatch):
        from app.routers import uploads as uploads_module

        monkeypatch.setattr(uploads_module, "THERAPISTS_ROOT", tmp_path)
        mock_db.therapist.find_unique.return_value = _therapist("")

        response = therapist_client.post(
            "/api/v1/uploads/therapists/therapist-1/photo",
            files={"file": ("avatar.png", PNG_BYTES, "image/png")},
        )

        assert response.status_code == 200
        body = response.json()
        assert "url" in body
        assert "/api/v1/uploads/therapists/therapist-1/photo-" in body["url"]

        mock_db.therapist.update.assert_awaited_once()
        update_kwargs = mock_db.therapist.update.await_args.kwargs
        assert body["url"] in update_kwargs["data"]["mediaUrls"]

    def test_upload_photo_rejects_non_image(self, therapist_client, mock_db, tmp_path, monkeypatch):
        from app.routers import uploads as uploads_module

        monkeypatch.setattr(uploads_module, "THERAPISTS_ROOT", tmp_path)
        mock_db.therapist.find_unique.return_value = _therapist("")

        response = therapist_client.post(
            "/api/v1/uploads/therapists/therapist-1/photo",
            files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")},
        )

        assert response.status_code == 400

    def test_upload_photo_forbidden_for_patient(self, patient_client, mock_db, tmp_path, monkeypatch):
        from app.routers import uploads as uploads_module

        monkeypatch.setattr(uploads_module, "THERAPISTS_ROOT", tmp_path)
        mock_db.therapist.find_unique.return_value = _therapist("")

        response = patient_client.post(
            "/api/v1/uploads/therapists/therapist-1/photo",
            files={"file": ("avatar.png", PNG_BYTES, "image/png")},
        )

        assert response.status_code == 403

    def test_delete_photo(self, therapist_client, mock_db, tmp_path, monkeypatch):
        from app.routers import uploads as uploads_module

        monkeypatch.setattr(uploads_module, "THERAPISTS_ROOT", tmp_path)

        photo_url = "/api/v1/uploads/therapists/therapist-1/photo-abc123.png"
        other_url = "/api/v1/uploads/therapists/therapist-1/other.png"
        (tmp_path / "therapist-1").mkdir(parents=True, exist_ok=True)
        (tmp_path / "therapist-1" / "photo-abc123.png").write_bytes(b"x")
        (tmp_path / "therapist-1" / "other.png").write_bytes(b"y")

        mock_db.therapist.find_unique.return_value = _therapist(
            f"{photo_url},{other_url}"
        )

        response = therapist_client.delete("/api/v1/uploads/therapists/therapist-1/photo")

        assert response.status_code == 200
        body = response.json()
        assert body["removed"] == 1

        update_kwargs = mock_db.therapist.update.await_args.kwargs
        assert photo_url not in update_kwargs["data"]["mediaUrls"]
        assert other_url in update_kwargs["data"]["mediaUrls"]

        assert not (tmp_path / "therapist-1" / "photo-abc123.png").exists()
        assert (tmp_path / "therapist-1" / "other.png").exists()

    def test_delete_photo_noop_when_no_photo(self, therapist_client, mock_db, tmp_path, monkeypatch):
        from app.routers import uploads as uploads_module

        monkeypatch.setattr(uploads_module, "THERAPISTS_ROOT", tmp_path)
        mock_db.therapist.find_unique.return_value = _therapist("")

        response = therapist_client.delete("/api/v1/uploads/therapists/therapist-1/photo")

        assert response.status_code == 200
        assert response.json()["removed"] == 0

    def test_delete_photo_forbidden_for_patient(self, patient_client, mock_db, tmp_path, monkeypatch):
        from app.routers import uploads as uploads_module

        monkeypatch.setattr(uploads_module, "THERAPISTS_ROOT", tmp_path)
        mock_db.therapist.find_unique.return_value = _therapist("")

        response = patient_client.delete("/api/v1/uploads/therapists/therapist-1/photo")

        assert response.status_code == 403
