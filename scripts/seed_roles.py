"""OBSOLETO: usar python -m scripts.seed_authorization (ver docs/backend-description.md)."""


def main() -> None:
    raise SystemExit(
        "scripts.seed_roles esta obsoleto y no escribe nada. Procedimiento vigente: alembic upgrade head; "
        "python -m scripts.seed_authorization; python -m scripts.load_reference_data; python -m scripts.bootstrap_first_admin."
    )


if __name__ == "__main__":
    main()
