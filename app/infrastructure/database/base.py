"""Clase base declarativa de SQLAlchemy. Todos los modelos ORM futuros heredarán de aquí."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
