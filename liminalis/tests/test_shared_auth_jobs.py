from backend._shared.auth import read_signed_payload, read_timed_payload, sign_payload, sign_timed_payload
from backend._shared.jobs import JobStatus, TaskStatus, new_job_id
from backend.settings import Settings


def test_signed_payload_helpers_roundtrip() -> None:
    settings = Settings(session_secret="test-secret-that-is-long-enough", _env_file=None)

    token = sign_payload(settings, {"user": "admin"}, salt="test")

    assert read_signed_payload(settings, token, salt="test") == {"user": "admin"}
    assert read_signed_payload(settings, token + "bad", salt="test") is None


def test_timed_payload_helpers_roundtrip() -> None:
    settings = Settings(session_secret="test-secret-that-is-long-enough", _env_file=None)

    token = sign_timed_payload(settings, {"target": "/radar"}, salt="test")

    assert read_timed_payload(settings, token, salt="test", max_age_seconds=60) == {"target": "/radar"}


def test_job_helpers_use_shared_status_vocabulary() -> None:
    job_id = new_job_id("radar")

    assert job_id.startswith("radar_")
    assert JobStatus.QUEUED.value == "queued"
    assert JobStatus.COMPLETED.value == "completed"
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
