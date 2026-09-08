import pytest
from fastapi import HTTPException

from app.upload_utils import (
    EXTENSION_TO_MIME,
    MAX_UPLOAD_SIZE,
    check_magic_bytes,
    serve_upload_response,
    validate_upload_file,
)
from pathlib import Path


class TestCheckMagicBytes:
    def test_rejects_html_disguised_as_pdf(self):
        assert check_magic_bytes("malware.pdf", b"<html>alert(1)</html>") is False

    def test_accepts_real_pdf(self):
        assert check_magic_bytes("doc.pdf", b"%PDF-1.4\n...") is True

    def test_accepts_png(self):
        assert check_magic_bytes("img.png", b"\x89PNG\r\n\x1a\nrest") is True

    def test_accepts_webp(self):
        assert check_magic_bytes("img.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ") is True

    def test_accepts_docx(self):
        assert check_magic_bytes("report.docx", b"PK\x03\x04remainder") is True

    def test_accepts_doc(self):
        assert check_magic_bytes("old.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1data") is True

    def test_rejects_wrong_extension(self):
        assert check_magic_bytes("img.png", b"PK\x03\x04notapng") is False

    def test_rejects_unknown_extension(self):
        assert check_magic_bytes("evil.exe", b"\x4d\x5abinary") is False

    def test_rejects_empty_content(self):
        assert check_magic_bytes("doc.pdf", b"") is False


class TestValidateUploadFile:
    def test_rejects_pdf_with_html_content(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_file("malware.pdf", b"<html>alert(1)</html>")
        assert exc.value.status_code == 400
        assert exc.value.detail == "File content does not match its type"

    def test_rejects_unknown_extension(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_file("evil.sh", b"#!/bin/sh")
        assert exc.value.status_code == 400
        assert exc.value.detail == "File type not allowed"

    def test_rejects_oversize(self):
        with pytest.raises(HTTPException) as exc:
            validate_upload_file("big.png", b"\x00" * (MAX_UPLOAD_SIZE + 1))
        assert exc.value.status_code == 413

    def test_accepts_valid_docx(self):
        ext, content = validate_upload_file("report.docx", b"PK\x03\x04data")
        assert ext == ".docx"
        assert content == b"PK\x03\x04data"

    def test_accepts_valid_doc(self):
        ext, _ = validate_upload_file("old.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1data")
        assert ext == ".doc"

    def test_returns_lowercased_extension(self):
        ext, _ = validate_upload_file("photo.JPG", b"\xff\xd8\xffrest")
        assert ext == ".jpg"


class TestServeUploadResponse:
    def test_docx_served_as_attachment_with_nosniff(self, tmp_path):
        p = tmp_path / "file.docx"
        p.write_bytes(b"PK\x03\x04data")

        resp = serve_upload_response(p, "report.docx")

        assert resp.media_type == "application/octet-stream"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert "attachment" in resp.headers["Content-Disposition"]

    def test_png_served_inline_with_nosniff(self, tmp_path):
        p = tmp_path / "img.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\nrest")

        resp = serve_upload_response(p, "img.png")

        assert resp.media_type == "image/png"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Disposition" not in resp.headers

    def test_unknown_extension_served_as_attachment(self, tmp_path):
        p = tmp_path / "evil.sh"
        p.write_bytes(b"#!/bin/sh")
        p.touch()

        resp = serve_upload_response(p, "evil.sh")

        assert resp.media_type == "application/octet-stream"
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert "attachment" in resp.headers["Content-Disposition"]
