# Turning on file storage

> ## ✅ DONE — 2026-07-23
>
> Bucket `eduflow-files-ap-south-1-210447603820` exists in **ap-south-1**, with all
> public access blocked, SSE-S3 encryption, and versioning on. `S3_BUCKET` is set on
> `Eduflow-env-1`, and the instance role `aws-elasticbeanstalk-ec2-role` carries the
> inline policy `EduFlowFileStorage`.
>
> **Health reports `"s3": "ok"`.** That check calls `list_objects_v2` *from the
> server*, so it proves the role policy, the bucket and the environment variable all
> line up. An anonymous request to the bucket returns 403.
>
> **Not yet proven from here:** writing an object as the server. The health check only
> lists. Ask Flo for a document to confirm the whole path end to end.
>
> The rest of this file is kept as the record of how it was done and how to repeat it
> for another school.

> ## ⚠️ There are TWO policies here and they go to DIFFERENT places
>
> This tripped us up once already, on 2026-07-23, because the first version of this
> document shipped one file with a generic name and hid the other inside a fenced code
> block. The file was the obvious thing to attach, so it was — and it was the wrong one.
>
> | File | Attach to | What it allows |
> |---|---|---|
> | `s3-policy-FOR-THE-CLAUDE-HOSTING-USER.json` | IAM **user** `claude-hosting` | **creating** the bucket, and granting the server access |
> | `s3-policy-FOR-THE-SERVER-ROLE.json` | IAM **role** `aws-elasticbeanstalk-ec2-role` | the running app **reading and writing files** in it |
>
> Attaching the role policy to the user grants object access but **not**
> `s3:CreateBucket`, so bucket creation still fails with AccessDenied and the user's
> permissions list *looks* correct. If you only ever do the console route (Option A),
> you need only the **role** one.
>
> **Do not add comments to these files.** An IAM policy document accepts only
> `Version` and `Statement` at the top level; anything else is rejected outright with
> "Unknown field". A first attempt at explaining the two files put `_comment` keys
> inside the JSON, and the console refused to save it. All explanation belongs here,
> in the filenames, and nowhere inside the policy.

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
policy → JSON → paste the contents of **`deploy/s3-policy-FOR-THE-SERVER-ROLE.json`** →
name it `EduFlowFileStorage` → Create.

> A **role**, not a user. This is what the running application is, so it is what needs
> to read and write the files.

> `s3:ListBucket` is in there deliberately: the readiness check calls
> `list_objects_v2`, so without it the health endpoint reports `degraded` even though
> uploads work.

**3. Tell me it is done.** Setting the `S3_BUCKET` variable on the environment is
within the assistant's existing access, and it will verify afterwards.

## Option B — grant the assistant the two permissions and it does the rest

IAM → Users → **`claude-hosting`** → Add permissions → Create inline policy → JSON →
paste **`deploy/s3-policy-FOR-THE-CLAUDE-HOSTING-USER.json`** → Create.

That is the file whose name says USER. The other one, whose name says SERVER ROLE,
does **not** contain `s3:CreateBucket` and will leave bucket creation failing.

Narrow on purpose: one named bucket and one named role. `iam:PutRolePolicy` on the
instance role is still a meaningful grant — it lets whoever holds those keys change
what the servers may do — so remove it again afterwards if you would rather not leave
it standing.

Under Option B the assistant attaches the server-role policy itself, so you do not
need to do step 2 by hand.

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
