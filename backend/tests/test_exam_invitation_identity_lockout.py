"""Focused persistence tests for invitation identity lockout fields."""

from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.exam_invitation import ExamInvitation, InvitationStatus


def create_invitation_table(engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE candidates (id BIGINT PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE exams (id BIGINT PRIMARY KEY)")
        ExamInvitation.__table__.create(connection)
        connection.exec_driver_sql("INSERT INTO candidates (id) VALUES (1)")
        connection.exec_driver_sql("INSERT INTO exams (id) VALUES (1)")


def test_identity_lockout_fields_default_and_persist_after_reload() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    create_invitation_table(engine)
    expires_at = datetime(2027, 1, 1, tzinfo=timezone.utc)
    locked_until = datetime(2026, 12, 1, 12, 30, tzinfo=timezone.utc)

    with Session(engine) as session:
        invitation = ExamInvitation(
            id=1,
            candidate_id=1,
            exam_id=1,
            token_hash="a" * 64,
            status=InvitationStatus.PENDING,
            created_at=datetime(2026, 11, 24, tzinfo=timezone.utc),
            expires_at=expires_at,
        )
        session.add(invitation)
        session.commit()
        assert invitation.failed_identity_attempts == 0

        invitation.failed_identity_attempts = 3
        invitation.identity_locked_until = locked_until
        session.commit()
        session.expire_all()

        restored = session.get(ExamInvitation, 1)
        assert restored is not None
        assert restored.failed_identity_attempts == 3
        # SQLite stores DateTime(timezone=True) without preserving tzinfo.
        # The persisted instant is retained as a naive UTC datetime on reload.
        assert restored.identity_locked_until == locked_until.replace(tzinfo=None)

    engine.dispose()
