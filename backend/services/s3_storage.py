"""S3-backed file storage helpers for user uploads."""

from __future__ import annotations

import hashlib
import mimetypes
import os
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import BinaryIO

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException


PRESIGNED_URL_EXPIRY_SECONDS = 3600


@dataclass(frozen=True)
class StoredObject:
    bucket: str
    key: str
    etag: str | None
    sha256: str
    size_bytes: int


def get_bucket_name() -> str:
    bucket = os.environ.get("S3_BUCKET_NAME") or os.environ.get("S3_BUCKET")
    if not bucket:
        raise HTTPException(500, "S3 bucket is not configured")
    return bucket


def get_aws_region() -> str:
    return os.environ.get("AWS_REGION", "ap-south-1")


def get_s3_client():
    return boto3.client("s3", region_name=get_aws_region())


def build_upload_key(file_id: str, original_filename: str) -> str:
    suffix = PurePosixPath(original_filename or "upload").suffix.lower()
    filename = f"{file_id}{suffix}" if suffix else file_id
    return str(PurePosixPath("uploads") / file_id / filename)


def infer_content_type(filename: str, fallback: str | None = None) -> str:
    if fallback:
        return fallback
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def upload_bytes(
    *,
    content: bytes,
    key: str,
    content_type: str,
    original_filename: str,
    s3_client=None,
) -> StoredObject:
    bucket = get_bucket_name()
    client = s3_client or get_s3_client()
    checksum = sha256_hex(content)
    metadata = {
        "sha256": checksum,
        "original-filename": original_filename[:1024],
    }

    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata=metadata,
        )
        head = client.head_object(Bucket=bucket, Key=key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(502, "File upload failed") from exc

    remote_checksum = head.get("Metadata", {}).get("sha256")
    if remote_checksum != checksum:
        try:
            client.delete_object(Bucket=bucket, Key=key)
        except (BotoCoreError, ClientError):
            pass
        raise HTTPException(502, "File upload checksum verification failed")

    return StoredObject(
        bucket=bucket,
        key=key,
        etag=head.get("ETag", "").strip('"') or None,
        sha256=checksum,
        size_bytes=len(content),
    )


def upload_fileobj(
    *,
    fileobj: BinaryIO,
    key: str,
    content_type: str,
    original_filename: str,
    s3_client=None,
) -> StoredObject:
    return upload_bytes(
        content=fileobj.read(),
        key=key,
        content_type=content_type,
        original_filename=original_filename,
        s3_client=s3_client,
    )


def create_presigned_get_url(key: str, *, expires_in: int = PRESIGNED_URL_EXPIRY_SECONDS, s3_client=None) -> str:
    if expires_in > PRESIGNED_URL_EXPIRY_SECONDS:
        raise HTTPException(500, "Presigned URL expiry exceeds the 1 hour limit")
    client = s3_client or get_s3_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": get_bucket_name(), "Key": key},
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(502, "File URL generation failed") from exc


def delete_object(key: str, *, s3_client=None) -> None:
    client = s3_client or get_s3_client()
    try:
        client.delete_object(Bucket=get_bucket_name(), Key=key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(502, "File deletion failed") from exc
