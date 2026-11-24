"""Isolated database tests for one-time positive invitation consent."""

from datetime import datetime

import pytest
from sqlalchemy import UniqueConstraint, create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.candidate_consent import CandidateConsent
from app.models.exam_invitation import ExamInvitation


@pytest.fixture
def consent_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE candidates (id BIGINT PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE exams (id BIGINT PRIMARY KEY)")
        ExamInvitation.__table__.create(connection)
        CandidateConsent.__table__.create(connection)
        connection.exec_driver_sql("INSERT INTO candidates (id) VALUES (1)")
        connection.exec_driver_sql("INSERT INTO exams (id) VALUES (1)")
        connection.exec_driver_sql(
            "INSERT INTO exam_invitations "
            "(id, candidate_id, exam_id, token_hash, status, created_at, expires_at) "
            "VALUES (1, 1, 1, :token, 'Pending', :created, :expires)",
            {"token": "a" * 64, "created": "2026-01-01", "expires": "2027-01-01"},
        )

    try:
        yield engine
    finally:
        engine.dispose()


def test_accepted_consent_uses_database_default_and_reloads_association(consent_db) -> None:
    with consent_db.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO candidate_consents (id, exam_invitation_id) VALUES (1, 1)"
        )
        raw_timestamp = connection.exec_driver_sql(
            "SELECT accepted_at FROM candidate_consents WHERE id = 1"
        ).scalar_one()
        assert raw_timestamp is not None

    with Session(consent_db) as session:
        consent = session.get(CandidateConsent, 1)
        assert consent is not None
        assert isinstance(consent.accepted_at, datetime)
        assert consent.exam_invitation_id == 1
        assert consent.exam_invitation.id == 1
        assert consent.exam_invitation.consent is consent


def test_database_rejects_second_consent_for_same_invitation(consent_db) -> None:
    with consent_db.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO candidate_consents (id, exam_invitation_id) VALUES (1, 1)"
        )
    with consent_db.begin() as connection, pytest.raises(IntegrityError):
        connection.exec_driver_sql(
            "INSERT INTO candidate_consents (id, exam_invitation_id) VALUES (2, 1)"
        )


def test_database_rejects_consent_for_nonexistent_invitation(consent_db) -> None:
    with consent_db.begin() as connection, pytest.raises(IntegrityError):
        connection.exec_driver_sql(
            "INSERT INTO candidate_consents (id, exam_invitation_id) VALUES (1, 404)"
        )


def test_candidate_consent_mapping_matches_one_time_positive_contract() -> None:
    table = CandidateConsent.__table__
    assert table.name == "candidate_consents"
    assert table.c.exam_invitation_id.nullable is False
    assert table.c.accepted_at.nullable is False
    assert table.c.accepted_at.type.timezone is True
    assert table.c.accepted_at.server_default is not None
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns) == ("exam_invitation_id",)
        for constraint in table.constraints
    )
    assert CandidateConsent.exam_invitation.property.uselist is False
    assert ExamInvitation.consent.property.uselist is False
    assert set(table.c.keys()) == {"id", "exam_invitation_id", "accepted_at"}
    assert not any("AssessmentAttempt" in str(fk.column) for fk in table.foreign_keys)
