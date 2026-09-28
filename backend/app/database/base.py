"""Declarative base for Prompt Compiler SQLAlchemy models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarative class for all database persistence entities."""
    pass
