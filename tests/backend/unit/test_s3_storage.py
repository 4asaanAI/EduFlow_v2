import os

import pytest
from fastapi import HTTPException

from backend.services import s3_storage


class FakeS3Client:
    def __init__(self):
        self.objects = {}
        self.deleted = []

    def put_object(self, **kwargs):
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = kwargs

    def head_object(self, Bucket, Key):
        obj = self.objects[(Bucket, Key)]
        return {
            "ETag": '"abc123"',
            "Metadata": obj["Metadata"],
        }

    def delete_object(self, Bucket, Key):
        self.deleted.append((Bucket, Key))

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"https://signed.example/{Params['Bucket']}/{Params['Key']}?expires={ExpiresIn}"


def test_upload_bytes_stores_private_object_with_checksum(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "eduflow-test")
    fake = FakeS3Client()

    stored = s3_storage.upload_bytes(
        content=b"hello",
        key="uploads/file-id/file.pdf",
        content_type="application/pdf",
        original_filename="file.pdf",
        s3_client=fake,
    )

    assert stored.bucket == "eduflow-test"
    assert stored.key == "uploads/file-id/file.pdf"
    assert stored.etag == "abc123"
    assert stored.sha256 == s3_storage.sha256_hex(b"hello")
    put_args = fake.objects[("eduflow-test", "uploads/file-id/file.pdf")]
    assert "ACL" not in put_args
    assert put_args["Metadata"]["sha256"] == stored.sha256


def test_upload_bytes_deletes_object_when_checksum_mismatch(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "eduflow-test")
    fake = FakeS3Client()

    def bad_head_object(Bucket, Key):
        return {"ETag": '"abc123"', "Metadata": {"sha256": "wrong"}}

    fake.head_object = bad_head_object

    with pytest.raises(HTTPException) as exc:
        s3_storage.upload_bytes(
            content=b"hello",
            key="uploads/file-id/file.pdf",
            content_type="application/pdf",
            original_filename="file.pdf",
            s3_client=fake,
        )

    assert exc.value.status_code == 502
    assert fake.deleted == [("eduflow-test", "uploads/file-id/file.pdf")]


def test_presigned_url_expiry_is_capped(monkeypatch):
    monkeypatch.setenv("S3_BUCKET_NAME", "eduflow-test")

    with pytest.raises(HTTPException) as exc:
        s3_storage.create_presigned_get_url("uploads/file-id/file.pdf", expires_in=3601)

    assert exc.value.status_code == 500


def test_get_bucket_name_accepts_legacy_alias(monkeypatch):
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)
    monkeypatch.setenv("S3_BUCKET", "legacy-bucket")

    assert s3_storage.get_bucket_name() == "legacy-bucket"
