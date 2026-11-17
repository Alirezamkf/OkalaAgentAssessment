"""Database connection boundary for the backend.

The engine keeps only the configuration and connection setup, and it does not
establish a network connection during import. The session factory creates an
independent session for each request.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


# The engine manages the connection pool and creates SQLAlchemy connections to PostgreSQL.
# create_engine does not connect to the database until a query or explicit connection is made.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)


# The factory standardizes session creation so each request has its own session
# and transaction state is not shared between requests.
SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Create an independent session for a request and close it afterward.

    FastAPI executes yield dependencies before the yield and runs the finally
    block after the response or when an exception occurs, so the session is
    closed in every execution path.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
