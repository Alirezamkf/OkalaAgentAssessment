"""Focused tests for authoritative HR role persistence (issue #249)."""

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.hr_roles import HRRole as DomainHRRole
from app.models.hr_user import HRUser
from app.models.hr_user_role import HRRole, HRUserRole
from app.services.hr_role_resolution import (
    HRRoleInvalidError,
    HRRoleNotAssignedError,
    HRRoleResolutionError,
    HRUserNotFoundError,
    assign_hr_role,
    resolve_hr_role,
    resolve_hr_role_for_user,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE hr_users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(100) NOT NULL UNIQUE, "
            "password_hash VARCHAR(255) NOT NULL, first_name VARCHAR(100) NOT NULL, "
            "last_name VARCHAR(100) NOT NULL, position VARCHAR(150) NOT NULL, "
            "profile_image_reference VARCHAR(500))"
        )
        connection.exec_driver_sql(
            "CREATE TABLE hr_user_roles ("
            "hr_user_id INTEGER PRIMARY KEY, role VARCHAR(20) NOT NULL "
            "CHECK (role IN ('HR', 'HRAdmin', 'HRManagement')), "
            "FOREIGN KEY(hr_user_id) REFERENCES hr_users(id) ON DELETE CASCADE)"
        )

    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_hr(db, user_id=1, username="hr.user"):
    hr_user = HRUser(
        id=user_id,
        username=username,
        password_hash="hash",
        first_name="Test",
        last_name="HR",
        position="Recruiter",
    )
    db.add(hr_user)
    db.flush()
    return hr_user


def test_hr_user_still_has_exactly_seven_columns():
    assert set(HRUser.__table__.columns.keys()) == {
        "id",
        "username",
        "password_hash",
        "first_name",
        "last_name",
        "position",
        "profile_image_reference",
    }


def test_role_model_has_exactly_three_approved_values():
    assert {member.value for member in HRRole} == {"HR", "HRAdmin", "HRManagement"}
    assert HRRole.HR_ADMIN.value == "HRAdmin"
    assert HRRole.HR_MANAGEMENT.value == "HRManagement"


def test_orm_and_domain_use_the_same_hr_role_enum():
    assert HRRole is DomainHRRole
    assert HRUserRole.__table__.c.role.type.enum_class is DomainHRRole


def test_exactly_one_named_check_constraint_enforces_role_values():
    checks = [
        constraint
        for constraint in HRUserRole.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    ]
    assert len(checks) == 1
    assert checks[0].name == "ck_hr_user_roles_role_allowed"
    assert HRUserRole.__table__.c.role.type.create_constraint is False


def test_role_table_uses_hr_user_id_as_primary_and_foreign_key():
    table = HRUserRole.__table__
    assert [column.name for column in table.primary_key.columns] == ["hr_user_id"]
    assert len(table.foreign_keys) == 1
    foreign_key = next(iter(table.foreign_keys))
    assert foreign_key.target_fullname == "hr_users.id"
    assert foreign_key.ondelete == "CASCADE"


@pytest.mark.parametrize("role", [HRRole.HR, HRRole.HR_ADMIN, HRRole.HR_MANAGEMENT])
def test_each_approved_role_can_be_persisted_and_resolved(db, role):
    hr_user = make_hr(db)
    assignment = assign_hr_role(db, hr_user.id, role)
    db.commit()

    assert assignment.role is role
    assert resolve_hr_role(db, hr_user.id) is role
    assert resolve_hr_role_for_user(db, hr_user) is role


def test_unsupported_role_value_is_rejected_by_database_constraint(db):
    hr_user = make_hr(db)
    with pytest.raises(IntegrityError):
        db.execute(
            text(
                "INSERT INTO hr_user_roles (hr_user_id, role) VALUES (:id, :role)"
            ),
            {"id": hr_user.id, "role": "SuperAdmin"},
        )
        db.flush()
    db.rollback()


def test_assign_hr_role_rejects_client_supplied_role_strings(db):
    hr_user = make_hr(db)
    with pytest.raises(HRRoleResolutionError):
        assign_hr_role(db, hr_user.id, "HRManagement")  # type: ignore[arg-type]
    db.rollback()


def test_cannot_persist_two_conflicting_roles_for_one_account(db):
    hr_user = make_hr(db)
    db.add_all(
        [
            HRUserRole(hr_user_id=hr_user.id, role=HRRole.HR),
            HRUserRole(hr_user_id=hr_user.id, role=HRRole.HR_MANAGEMENT),
        ]
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_assign_hr_role_updates_the_existing_assignment(db):
    hr_user = make_hr(db)
    assign_hr_role(db, hr_user.id, HRRole.HR)
    assign_hr_role(db, hr_user.id, HRRole.HR_MANAGEMENT)
    db.commit()

    assert db.query(HRUserRole).count() == 1
    assert resolve_hr_role(db, hr_user.id) is HRRole.HR_MANAGEMENT


def test_role_assignment_requires_an_existing_hr_user(db):
    with pytest.raises(IntegrityError):
        db.add(HRUserRole(hr_user_id=999, role=HRRole.HR))
        db.commit()
    db.rollback()


def test_deleting_hr_user_cascades_to_role_assignment(db):
    hr_user = make_hr(db)
    assign_hr_role(db, hr_user.id, HRRole.HR)
    db.commit()

    # Use SQL directly: the HRUser ORM also maps hr_decided_attempts, whose
    # table is outside this focused fixture.
    db.execute(text("DELETE FROM hr_users WHERE id = :id"), {"id": hr_user.id})
    db.commit()

    assert db.execute(text("SELECT COUNT(*) FROM hr_user_roles")).scalar_one() == 0


def test_missing_role_assignment_fails_closed(db):
    hr_user = make_hr(db)
    db.commit()

    with pytest.raises(HRRoleNotAssignedError):
        resolve_hr_role(db, hr_user.id)


def test_unknown_hr_user_fails_closed(db):
    with pytest.raises(HRUserNotFoundError):
        resolve_hr_role(db, 999)


def test_invalid_persisted_role_fails_closed(db, monkeypatch):
    from types import SimpleNamespace

    from app.services import hr_role_resolution

    hr_user = make_hr(db)
    db.commit()

    # The database constraint blocks junk on write; simulate a corrupted row
    # returned by the persistence layer to prove the resolver fails closed.
    original_scalar = db.scalar

    def fake_scalar(statement, *args, **kwargs):
        if "hr_user_roles" in str(statement):
            return SimpleNamespace(role="corrupt")
        return original_scalar(statement, *args, **kwargs)

    monkeypatch.setattr(db, "scalar", fake_scalar)

    with pytest.raises(HRRoleInvalidError):
        resolve_hr_role(db, hr_user.id)


def test_resolver_uses_persisted_role_not_unrelated_client_payload(db):
    hr_user = make_hr(db)
    assign_hr_role(db, hr_user.id, HRRole.HR)
    db.commit()

    client_payload = {"role": "HRManagement", "hr_role": "HRManagement"}
    assert resolve_hr_role(db, hr_user.id) is HRRole.HR
    assert resolve_hr_role_for_user(db, hr_user) is HRRole.HR
    assert client_payload["role"] == "HRManagement"


def test_role_assignment_rolls_back_with_the_caller_transaction(db):
    hr_user = make_hr(db)
    db.commit()

    assign_hr_role(db, hr_user.id, HRRole.HR_MANAGEMENT)
    db.flush()
    assert db.query(HRUserRole).count() == 1

    db.rollback()

    assert db.query(HRUserRole).count() == 0
    with pytest.raises(HRRoleNotAssignedError):
        resolve_hr_role(db, hr_user.id)


def test_account_and_role_creation_are_atomic_on_rollback(db):
    hr_user = HRUser(
        username="atomic.user",
        password_hash="hash",
        first_name="Atomic",
        last_name="User",
        position="Recruiter",
    )
    db.add(hr_user)
    db.flush()

    assign_hr_role(db, hr_user.id, HRRole.HR)
    db.flush()
    assert db.query(HRUserRole).count() == 1

    db.rollback()

    assert db.query(HRUser).count() == 0
    assert db.query(HRUserRole).count() == 0
