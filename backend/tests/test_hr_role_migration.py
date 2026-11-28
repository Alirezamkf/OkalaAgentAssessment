"""Verify the HR role migration on an isolated SQLite database.

The baseline migration uses PostgreSQL-only DDL (CREATE TYPE), so this test
creates a minimal hr_users table directly and runs the new revision's
upgrade()/downgrade() functions through an isolated Alembic Operations context.
The revision chain is checked separately from the real script directory.
"""

import importlib.util
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    BACKEND_ROOT / "alembic" / "versions" / "20261128_0700_add_hr_user_roles.py"
)


@pytest.fixture
def migration_db(tmp_path):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE hr_users ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, username VARCHAR(100) NOT NULL UNIQUE, "
            "password_hash VARCHAR(255) NOT NULL, first_name VARCHAR(100) NOT NULL, "
            "last_name VARCHAR(100) NOT NULL, position VARCHAR(150) NOT NULL, "
            "profile_image_reference VARCHAR(500))"
        )
        connection.exec_driver_sql(
            "INSERT INTO hr_users "
            "(username, password_hash, first_name, last_name, position) "
            "VALUES ('existing', 'hash', 'Existing', 'User', 'Staff')"
        )
    yield engine
    engine.dispose()


def _migration_module():
    spec = importlib.util.spec_from_file_location("hr_role_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_with_operations(engine, action):
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with Operations.context(context):
            action()


def test_migration_chain_has_one_head_after_role_revision():
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["20261128_0700"]
    revision = scripts.get_revision("20261128_0700")
    assert revision.down_revision == "20261120_0710"


def test_upgrade_creates_role_table_and_preserves_hr_users(migration_db):
    module = _migration_module()
    _run_with_operations(migration_db, module.upgrade)

    inspector = inspect(migration_db)
    columns = [column["name"] for column in inspector.get_columns("hr_users")]
    assert columns == [
        "id",
        "username",
        "password_hash",
        "first_name",
        "last_name",
        "position",
        "profile_image_reference",
    ]

    role_columns = [column["name"] for column in inspector.get_columns("hr_user_roles")]
    assert role_columns == ["hr_user_id", "role"]

    primary_key = inspector.get_pk_constraint("hr_user_roles")
    assert primary_key["constrained_columns"] == ["hr_user_id"]

    foreign_keys = inspector.get_foreign_keys("hr_user_roles")
    assert len(foreign_keys) == 1
    assert foreign_keys[0]["referred_table"] == "hr_users"
    assert foreign_keys[0]["constrained_columns"] == ["hr_user_id"]
    assert foreign_keys[0]["referred_columns"] == ["id"]
    assert foreign_keys[0]["options"].get("ondelete") == "CASCADE"

    with migration_db.connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM hr_user_roles")
        ).scalar_one() == 0
        assert connection.execute(
            text("SELECT username FROM hr_users")
        ).scalar_one() == "existing"


def test_downgrade_removes_only_role_table(migration_db):
    module = _migration_module()
    _run_with_operations(
        migration_db,
        lambda: (module.upgrade(), module.downgrade()),
    )

    inspector = inspect(migration_db)
    assert "hr_user_roles" not in inspector.get_table_names()
    assert "hr_users" in inspector.get_table_names()
    with migration_db.connect() as connection:
        assert connection.execute(
            text("SELECT username FROM hr_users")
        ).scalar_one() == "existing"
