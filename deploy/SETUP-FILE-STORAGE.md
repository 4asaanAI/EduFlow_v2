# Turning on file storage

Until this is done, anything in EduFlow that produces or accepts a **file** does not
work in production:

- Flo cannot hand over a Word, Excel, PowerPoint or PDF document (it says so plainly)
- certificate generation (`routes/image_gen.py`)
- student photo uploads
- fee receipts saved as PDFs

The health endpoint reports this as `"s3": "not_configured"`, which is easy to read as
cosmetic. It is not — no bucket is set, so `services/s3_storage.get_bucket_name()`
raises on every call.

**Why this file exists rather than a script:** the two AWS logins the assistant holds
are deliberately scoped. `claude-hosting` carries `AdministratorAccess-AWSElasticBeanstalk`,
which permits Elastic Beanstalk and the EB deployment bucket and nothing else; the
`Claude` user is narrower still. Neither can call `s3:CreateBucket` or `iam:PutRolePolicy`.
That is a reasonable boundary and it is not worth widening permanently for a one-off.

---

## What to create

| | |
|---|---|
| Bucket name | `eduflow-files-ap-south-1-210447603820` |
| Region | **Asia Pacific (Mumbai) `ap-south-1`** — same as everything else, and the school's records stay in India |
| Public access | **Block all.** Non-negotiable: this holds documents about 1,802 children. Files are served by time-limited signed links, never by public URL. |
| Encryption | SSE-S3 (AES-256), bucket key on |
| Versioning | Recommended. Files are small; it protects against an accidental delete or overwrite. |

If you pick a different bucket name, change it in **three** places: the bucket itself,
`deploy/s3-file-storage-policy.json` (twice), and the `S3_BUCKET` value below.

---

## Option A — you do it in the console (recommended, ~5 minutes)

**1. Create the bucket**
S3 → Create bucket → name `eduflow-files-ap-south-1-210447603820`, region
Asia Pacific (Mumbai) ap-south-1 → leave **Block all public access ticked** →
Bucket Versioning: Enable → Default encryption: SSE-S3, Bucket Key: Enable → Create.

**2. Let the server use it**
IAM → Roles → **`aws-elasticbeanstalk-ec2-role`** → Add permissions → Create inline
policy → JSON → paste the contents of `deploy/s3-file-storage-policy.json` →
name it `EduFlowFileStorage` → Create.

> `s3:ListBucket` is in there deliberately: the readiness check calls
> `list_objects_v2`, so without it the health endpoint reports `degraded` even though
> uploads work.

**3. Tell me it is done.** Setting the `S3_BUCKET` variable on the environment is
within the assistant's existing access, and it will verify afterwards.

## Option B — grant the assistant the two permissions and it does the rest

Attach this inline policy to the IAM user **`claude-hosting`**:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:PutBucketPublicAccessBlock",
        "s3:PutEncryptionConfiguration",
        "s3:PutBucketVersioning"
      ],
      "Resource": "arn:aws:s3:::eduflow-files-ap-south-1-210447603820"
    },
    {
      "Effect": "Allow",
      "Action": "iam:PutRolePolicy",
      "Resource": "arn:aws:iam::210447603820:role/aws-elasticbeanstalk-ec2-role"
    }
  ]
}
```

Narrow on purpose: one named bucket and one named role. `iam:PutRolePolicy` on the
instance role is still a meaningful grant — it lets whoever holds those keys change
what the servers may do — so remove it again afterwards if you would rather not leave
it standing.

---

## Step 3, whichever option — set the variable

```
aws elasticbeanstalk update-environment \
  --environment-name Eduflow-env-1 \
  --option-settings \
    Namespace=aws:elasticbeanstalk:application:environment,OptionName=S3_BUCKET,Value=eduflow-files-ap-south-1-210447603820
```

This restarts the environment (about a minute).

## How to know it worked

```
curl http://eduflow.ap-south-1.elasticbeanstalk.com/api/health/ready
```

`"s3"` should read **`ok`**, not `not_configured` and not `degraded`.
Then ask Flo for a circular as a Word file: you should get a download link rather than
"saving files is not set up on this server yet".

## Cost

Negligible. Storage is about $0.025 per GB per month in Mumbai; a year of school
documents and photos is likely under a gigabyte. There is no fixed monthly charge.
