"""Static metadata tests for the HRUser username column."""

from sqlalchemy import String

from app.models.hr_user import HRUser


def test_hr_user_has_exactly_the_approved_columns() -> None:
    assert set(HRUser.__table__.columns.keys()) == {
        "id",
        "username",
        "password_hash",
        "first_name",
        "last_name",
        "position",
        "profile_image_reference",
    }


def test_username_is_required_and_database_unique() -> None:
    username = HRUser.__table__.c.username

    assert isinstance(username.type, String)
    assert username.type.length == 100
    assert username.nullable is False
    assert username.unique is True
    assert any(
        len(constraint.columns) == 1
        and "username" in constraint.columns
        for constraint in HRUser.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    )


def test_username_relationships_are_unchanged() -> None:
    relationship_names = {
        relationship.key
        for relationship in HRUser.__mapper__.relationships
    }
    assert relationship_names == {"hr_decided_attempts"}
