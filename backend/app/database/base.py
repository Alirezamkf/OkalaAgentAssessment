"""Define the shared base for ORM models in the backend."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared base for models to register their SQLAlchemy mappings consistently.

    DeclarativeBase provides the SQLAlchemy 2.x mechanism for defining base
    declarative model classes. Future models should inherit from this class so
    that their mappings are available in a shared metadata object.
    """
