# S3 Bucket Policy Requirements

Part 6 requires the upload bucket to be private by default.

Production checklist:

- Block all public access is enabled at the bucket level.
- No bucket policy grants public read, public write, or broad cross-account access.
- Server-side encryption is enabled with AES-256 or KMS.
- Application reads use presigned URLs with expiry no greater than 3600 seconds.
- Objects are written under the tenant prefix: `{schoolId}/uploads/{fileId}/{fileId}.{ext}`.

Legacy objects may still exist under `uploads/{fileId}/{fileId}.{ext}`. Do not rewrite or reconstruct those keys during delete operations; use the `s3_key` stored in `file_uploads`.
