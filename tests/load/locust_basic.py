import os

from locust import HttpUser, between, task


class EduFlowUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.headers = {}
        token = os.environ.get("LOCUST_AUTH_TOKEN")
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    @task(4)
    def list_students(self):
        self.client.get("/api/students", headers=self.headers, name="GET /api/students")

    @task(3)
    def today_attendance(self):
        self.client.get(
            "/api/attendance/student/today/class-1",
            headers=self.headers,
            name="GET /api/attendance/student/today/{class_id}",
        )

    @task(2)
    def fee_transactions(self):
        self.client.get(
            "/api/fees/transactions",
            headers=self.headers,
            name="GET /api/fees/transactions",
        )

    @task(1)
    def health_ready(self):
        self.client.get("/api/health/ready", name="GET /api/health/ready")
