"""Dependencias reutilizables de FastAPI (DB, usuario autenticado, control de sucursal).

`get_db` ya está disponible en `app.infrastructure.database.session`. Las dependencias
de autenticación/autorización (`get_current_user`, `require_role`, `require_branch_access`)
se agregarán junto con el módulo de login, respetando la regla de aislamiento por sucursal.
"""
