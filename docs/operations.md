# EduFlow Operations

## Service Targets

- Availability target: 99.9% monthly uptime for production school instances.
- API latency target: p95 under 2 seconds for non-AI read endpoints during normal school-day load.
- AI latency target: first streamed token under 5 seconds where the upstream model is healthy.
- Health target: `GET /api/health/ready` returns `200` within 30 seconds of process start.

## Backup Policy

MongoDB Atlas is the source of truth for school data.

- Snapshot frequency: daily automated snapshots.
- Point-in-time recovery window: 7 days.
- RPO target: 24 hours for snapshot restore, 15 minutes when point-in-time recovery is enabled.
- RTO target: 4 hours for single-school restore after an approved rollback decision.
- Retention: keep production snapshots for at least 7 days; retain monthly exports separately when required by school policy.

## Restore Procedure

1. Freeze writes by placing the affected school instance in maintenance mode at the load balancer or application gateway.
2. In MongoDB Atlas, select the production cluster, then choose Backup.
3. Pick the last known-good snapshot or point-in-time restore timestamp.
4. Restore into a temporary cluster first.
5. Run smoke checks against the temporary restore:
   - `students`, `staff`, `fee_transactions`, `student_attendance`, and `audit_logs` have expected row counts.
   - `GET /api/health/ready` returns `200`.
   - Owner login works on a staging backend pointed at the restored cluster.
6. Promote the restored cluster by updating `MONGO_URL` on the Elastic Beanstalk environment.
7. Restart the backend environment and verify `GET /api/health/ready`.
8. Re-enable traffic and record the restore in the incident log.

## Durability Checks

- Confirmed HTTP `200` or `201` writes must be persisted before the client sees success.
- Attendance and fee payment flows should be re-queried after deploys because they are the highest-volume write paths.
- If MongoDB is unreachable, `GET /api/health/ready` must return `503`; do not route production traffic to an instance in that state.

## Monitoring

- Watch Elastic Beanstalk health, process restarts, and ALB 5xx responses.
- Watch MongoDB Atlas connection count, slow queries, CPU, and storage growth.
- Watch S3 4xx/5xx responses for uploads and signed-file serving.
- Watch SMS provider failures and `sms_logs.status` values when Twilio is configured.

## Load Validation

Run load tests only against staging or a dedicated performance environment.

Recommended baseline:

```bash
LOCUST_AUTH_TOKEN=<owner-or-test-token> locust -f tests/load/locust_basic.py --host https://staging-api.example.com
```

Use 50 concurrent users for the Part 16 baseline. Reads should stay below 2 seconds p95, and AI first-token checks should stay below 5 seconds when the provider is healthy.
