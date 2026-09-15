"""Contratos (interfaces) de repositorios que la infraestructura deberá implementar.

Diseño pensado para el aislamiento por sucursal: los repositorios de entidades
con alcance de sucursal deberán exponer un `branch_id` obligatorio en sus consultas,
de modo que la restricción de acceso se aplique en la capa de infraestructura y no
únicamente en el frontend. Esto se implementará junto con las entidades reales.
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

EntityType = TypeVar("EntityType")
IdType = TypeVar("IdType")


class BaseRepository(ABC, Generic[EntityType, IdType]):
    """Contrato genérico de repositorio. Las entidades concretas se agregarán después."""

    @abstractmethod
    def get_by_id(self, entity_id: IdType) -> EntityType | None: ...

    @abstractmethod
    def list_all(self) -> list[EntityType]: ...

    @abstractmethod
    def add(self, entity: EntityType) -> EntityType: ...

    @abstractmethod
    def delete(self, entity_id: IdType) -> None: ...
