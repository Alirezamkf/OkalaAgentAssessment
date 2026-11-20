"""Tests for conservative Candidate identity matching and anonymization."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.services.candidate_identity import (
    anonymize_candidate,
    get_or_create_candidate,
    normalize_phone,
)


def create_session() -> tuple[object, Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE candidates ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "first_name VARCHAR(100) NOT NULL, "
            "last_name VARCHAR(100) NOT NULL, "
            "email VARCHAR(320), "
            "phone VARCHAR(50)"
            ")"
        )
    return engine, Session(engine)


def test_new_candidate_splits_names_and_requires_one_contact() -> None:
    engine, db = create_session()
    try:
        candidate = get_or_create_candidate(
            db,
            first_name="Ali",
            last_name="Rezayi",
            email="  ALI@example.com  ",
        )
        assert candidate.first_name == "Ali"
        assert candidate.last_name == "Rezayi"
        assert candidate.email == "ali@example.com"
        assert candidate.phone is None

        try:
            get_or_create_candidate(db, first_name="Sara", last_name="Karimi")
            raise AssertionError("Candidate without contact information was accepted")
        except ValueError:
            pass
    finally:
        db.close()
        engine.dispose()


def test_existing_candidate_is_reused_and_contact_can_change() -> None:
    engine, db = create_session()
    try:
        original = get_or_create_candidate(
            db,
            first_name="Negin",
            last_name="Ahmadi",
            email="negin@example.com",
            phone="0912-111-2233",
        )
        original_id = original.id
        updated = get_or_create_candidate(
            db,
            first_name="Negin",
            last_name="Ahmadi",
            email="new-negin@example.com",
            phone="09121112233",
        )
        assert updated.id == original_id
        assert updated.email == "new-negin@example.com"
        assert updated.phone == "9121112233"
        assert db.query(Candidate).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_conflicting_email_and_phone_do_not_merge() -> None:
    engine, db = create_session()
    try:
        get_or_create_candidate(
            db,
            first_name="Mina",
            last_name="Salehi",
            email="mina@example.com",
        )
        get_or_create_candidate(
            db,
            first_name="Reza",
            last_name="Nouri",
            phone="09123456789",
        )

        try:
            get_or_create_candidate(
                db,
                first_name="Mina",
                last_name="Salehi",
                email="mina@example.com",
                phone="09123456789",
            )
            raise AssertionError("Cross-person email and phone conflict was accepted")
        except ValueError:
            pass

        assert db.query(Candidate).count() == 2
    finally:
        db.close()
        engine.dispose()


def test_names_alone_do_not_reuse_a_candidate() -> None:
    engine, db = create_session()
    try:
        get_or_create_candidate(
            db,
            first_name="Samira",
            last_name="Rahimi",
            email="samira@example.com",
        )
        second = get_or_create_candidate(
            db,
            first_name="Samira",
            last_name="Rahimi",
            phone="09123456780",
        )
        assert db.query(Candidate).count() == 2
        assert second.email is None
    finally:
        db.close()
        engine.dispose()


def test_anonymization_clears_pii_without_deleting_candidate() -> None:
    engine, db = create_session()
    try:
        candidate = get_or_create_candidate(
            db,
            first_name="Tara",
            last_name="Kiani",
            email="tara@example.com",
            phone="09120000000",
        )
        candidate_id = candidate.id
        anonymize_candidate(candidate)
        db.flush()

        assert candidate.id == candidate_id
        assert candidate.first_name == "Anonymized"
        assert candidate.last_name == "Candidate"
        assert candidate.email is None
        assert candidate.phone is None
        assert db.query(Candidate).count() == 1
    finally:
        db.close()
        engine.dispose()


def test_phone_normalization_is_conservative() -> None:
    assert normalize_phone("+98 912 111 2233") == "989121112233"
    assert normalize_phone("0912-111-2233") == "9121112233"
