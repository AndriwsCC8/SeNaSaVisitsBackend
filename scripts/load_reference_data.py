"""Load official reference data (branch types, branches, visitor types, visit reasons) from a JSON file.

  python -m scripts.load_reference_data --file ruta.json --validate-only   (sin base de datos)
  python -m scripts.load_reference_data --file ruta.json --dry-run         (lee la base, no escribe)
  python -m scripts.load_reference_data --file ruta.json --apply           (escribe en una transacción)

Existing records are never overwritten: a record with the same code but different data, or an
inactive one, is reported as a conflict and the whole load is aborted.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import Branch, BranchType, VisitReason, VisitorType

logger = logging.getLogger("senasa_visits.reference_data")

_CODE = re.compile(r"[A-Z0-9_-]+")
EXAMPLE_PREFIXES = ("EJEMPLO_", "EXAMPLE_")


class _Item(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("code", check_fields=False)
    @classmethod
    def _code_format(cls, value: str) -> str:
        if not _CODE.fullmatch(value):
            raise ValueError("el código solo admite A-Z mayúsculas, 0-9, guion y guion bajo")
        return value


class BranchTypeItem(_Item):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class BranchItem(_Item):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=1, max_length=200)
    branch_type_code: str = Field(min_length=1, max_length=30)
    region: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=30)


class VisitorTypeItem(_Item):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class VisitReasonItem(_Item):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)


class ReferenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_example: bool = False
    branch_types: list[BranchTypeItem] = []
    branches: list[BranchItem] = []
    visitor_types: list[VisitorTypeItem] = []
    visit_reasons: list[VisitReasonItem] = []

    @model_validator(mode="after")
    def _check_duplicates(self) -> "ReferenceData":
        problems: list[str] = []
        for label, items in (
            ("branch_types", self.branch_types),
            ("branches", self.branches),
            ("visitor_types", self.visitor_types),
            ("visit_reasons", self.visit_reasons),
        ):
            seen: set[str] = set()
            for item in items:
                if item.code in seen:
                    problems.append(f"{label}: código duplicado {item.code}")
                seen.add(item.code)
        if problems:
            raise ValueError("; ".join(problems))
        return self


@dataclass
class LoadReport:
    to_create: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def parse_reference_data(raw: Any) -> ReferenceData:
    """Validate a decoded JSON document; raises ValueError with readable messages."""
    try:
        return ReferenceData.model_validate(raw)
    except ValidationError as exc:
        messages = [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()]
        raise ValueError("; ".join(messages)) from None


def _differs(item: Any, values: dict[str, Any]) -> bool:
    return any(getattr(item, key) != value for key, value in values.items()) or not item.is_active


def build_report(db: Session, data: ReferenceData) -> tuple[LoadReport, list[object]]:
    """Compare the file with the database without writing; returns the report and rows to insert."""
    report = LoadReport()
    new_rows: list[object] = []

    def sync(model: type, label: str, code: str, values: dict[str, Any], make) -> None:
        existing = db.scalar(select(model).where(model.code == code))
        key = f"{label} {code}"
        if existing is None:
            report.to_create.append(key)
            new_rows.append(make())
        elif _differs(existing, values):
            report.conflicts.append(f"{key}: ya existe con datos distintos o inactivo; no se sobrescribe")
        else:
            report.unchanged.append(key)

    for item in data.branch_types:
        values = {"name": item.name, "description": item.description}
        sync(BranchType, "branch_type", item.code, values, lambda i=item: BranchType(code=i.code, name=i.name, description=i.description, is_active=True))
    for item in data.visitor_types:
        values = {"name": item.name, "description": item.description}
        sync(VisitorType, "visitor_type", item.code, values, lambda i=item: VisitorType(code=i.code, name=i.name, description=i.description, is_active=True))
    for item in data.visit_reasons:
        values = {"name": item.name, "description": item.description}
        sync(VisitReason, "visit_reason", item.code, values, lambda i=item: VisitReason(code=i.code, name=i.name, description=i.description, is_active=True))

    file_type_codes = {item.code for item in data.branch_types}
    for item in data.branches:
        branch_type = db.scalar(select(BranchType).where(BranchType.code == item.branch_type_code))
        if branch_type is None and item.branch_type_code not in file_type_codes:
            report.conflicts.append(f"branch {item.code}: el tipo de sucursal {item.branch_type_code} no existe ni está en el archivo")
            continue
        if branch_type is not None and not branch_type.is_active:
            report.conflicts.append(f"branch {item.code}: el tipo de sucursal {item.branch_type_code} está inactivo")
            continue
        existing = db.scalar(select(Branch).where(Branch.code == item.code))
        key = f"branch {item.code}"
        if existing is None:
            report.to_create.append(key)
            new_rows.append(("branch", item))
        else:
            values = {"name": item.name, "region": item.region, "address": item.address, "phone": item.phone}
            same_type = branch_type is not None and existing.branch_type_id == branch_type.id
            if _differs(existing, values) or not same_type:
                report.conflicts.append(f"{key}: ya existe con datos distintos o inactivo; no se sobrescribe")
            else:
                report.unchanged.append(key)
    return report, new_rows


def load_reference_data(db: Session, data: ReferenceData, *, dry_run: bool) -> LoadReport:
    """Plan and (unless dry_run) insert the data. Raises RuntimeError on any conflict, writing nothing."""
    report, new_rows = build_report(db, data)
    if report.conflicts:
        raise RuntimeError("Conflictos detectados; no se escribió nada: " + " | ".join(report.conflicts))
    if dry_run:
        return report

    plain = [row for row in new_rows if not isinstance(row, tuple)]
    db.add_all(plain)
    db.flush()
    for row in new_rows:
        if isinstance(row, tuple):
            item: BranchItem = row[1]
            branch_type = db.scalar(select(BranchType).where(BranchType.code == item.branch_type_code))
            db.add(
                Branch(
                    code=item.code,
                    name=item.name,
                    branch_type_id=branch_type.id,
                    region=item.region,
                    address=item.address,
                    phone=item.phone,
                    is_active=True,
                )
            )
    db.flush()
    logger.info("Datos de referencia cargados: creados=%s sin cambios=%s", len(report.to_create), len(report.unchanged))
    return report


def _print_report(report: LoadReport, *, applied: bool) -> None:
    print(("Creados" if applied else "Se crearían") + f": {len(report.to_create)}")
    for line in report.to_create:
        print(f"  + {line}")
    print(f"Sin cambios: {len(report.unchanged)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga de datos de referencia institucionales desde JSON")
    parser.add_argument("--file", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--validate-only", action="store_true", help="Solo valida el archivo; no abre la base de datos")
    mode.add_argument("--dry-run", action="store_true", help="Compara con la base y no escribe")
    mode.add_argument("--apply", action="store_true", help="Escribe en una única transacción")
    args = parser.parse_args()

    try:
        data = parse_reference_data(json.loads(args.file.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Archivo inválido: {exc}") from None
    if any(item.code.startswith(EXAMPLE_PREFIXES) for group in (data.branch_types, data.branches, data.visitor_types, data.visit_reasons) for item in group):
        data.is_example = True
    if args.apply and data.is_example:
        raise SystemExit("El archivo es una plantilla de ejemplo; no se carga con --apply")
    if args.validate_only:
        print("Archivo válido.")
        return

    from app.infrastructure.database.session import SessionLocal

    try:
        with SessionLocal.begin() as db:
            report = load_reference_data(db, data, dry_run=not args.apply)
            if not args.apply:
                db.rollback()
    except RuntimeError as exc:
        raise SystemExit(f"Abortado: {exc}") from None
    _print_report(report, applied=args.apply)


if __name__ == "__main__":
    main()
