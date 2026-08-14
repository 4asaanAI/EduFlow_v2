# The Vedmarg photographs: proven moved, and two leaks closed (2026-08-15)

Abhimanyu asked where the plan to move the students' and parents' photographs off
Vedmarg, the school's previous software vendor, had got to. Answer: **the move itself was
finished, and had never been proven.** Proving it found two reads that still handed a
browser the vendor's public address.

## The move is real, not just recorded

A key written on a record is not a photograph. Checked against the live database and the
live bucket:

| Where | Records with a photo | Still pointing at the vendor CDN | Our own copy | Stranded |
|---|---|---|---|---|
| students, own photo | 1,423 | 1,423 | 1,423 | **0** |
| students, mother | 127 | 127 | 127 | **0** |
| students, father | 128 | 128 | 128 | **0** |
| students, guardian | 1 | 1 | 1 | **0** |
| staff | 13 | 13 | 13 | **0** |
| guardians | 255 | 255 | 255 | **0** |

The bucket holds **1,692 images, 202.8 MB** under `aaryans-joya/uploads/`. That is
1,423 children plus 13 staff plus 256 parents; the guardian rows and the parent fields on
the child's record point at the same objects, which is why the record count is higher than
the object count.

**Retrieval was tested, not assumed.** A sample of 21 keys across all six fields was signed
and fetched: all 21 returned real JPEGs. A copy that has never been read back is not yet a
copy.

## Two traps hit while proving it

Both produced a convincing false alarm. Neither was a fault in the platform.

1. **`S3_BUCKET is not configured` locally.** The bucket name is set on the server and not
   in the local `backend/.env`, so signing failed on this machine and read as every
   photograph being missing.
2. **A link signed for downloading cannot be checked with a headers-only request.** The
   signature covers the method, so a `HEAD` against a `GET` link returns **403**, which is
   indistinguishable from "the file is not there". Fetch one byte with a `Range` header
   instead. This is what made 21 healthy images look like 21 missing ones.

## What was actually wrong: two reads that skipped the rule

`photo_url_service` answers a read with a short-lived signed link and **never** returns a
vendor address, even one that still works. Two responses never called it:

- **`GET /api/guardian/wards` and the ward detail behind it.** The **parent portal**
  returned the child's whole record untouched, so a parent's own browser was handed the
  vendor's public address for their child and both parents. Of every screen to miss, this
  was the worst one.
- **The guardian `PATCH` response** returned the freshly updated guardian document
  untouched.

Both now apply the service. Pinned by
`tests/backend/api/test_no_vendor_photo_link_escapes_2026_08_15.py`, which also carries a
crude alarm: any route module that returns a person and does not even import the photo
service fails. That is exactly how the parent portal came to skip it.

## One stale comment corrected

`routes/students.py` said guardian rows carry no S3 key of their own and always fall back
to no photograph. **255 of them now do carry a key**, so they resolve to a real signed
link. The comment read as a design decision and had quietly become false.

## What is NOT closed

**The photographs are still on the vendor's CDN, publicly readable by anyone holding a
link.** Nothing this platform does can remove them. What is now true is that EduFlow never
hands out one of those links and never depends on that CDN staying alive. Taking the
originals down is a conversation with Vedmarg, not a code change.

Gate: 3,784 backend tests passing, 0 failed.
