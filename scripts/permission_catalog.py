"""Approved role and permission catalog for the manual authorization seeds."""

PERMISSIONS = (
    ("VIEW_VISITS", "Ver visitas", "visits", "view", "BRANCH"),
    ("CREATE_VISIT", "Crear visitas", "visits", "create", "BRANCH"),
    ("UPDATE_VISIT", "Actualizar visitas", "visits", "update", "BRANCH"),
    ("DELETE_VISIT", "Eliminar visitas", "visits", "delete", "BRANCH"),
    ("VIEW_VISITORS", "Ver visitantes", "visitors", "view", "BRANCH"),
    ("CREATE_VISITOR", "Crear visitantes", "visitors", "create", "BRANCH"),
    ("UPDATE_VISITOR", "Actualizar visitantes", "visitors", "update", "BRANCH"),
    ("VIEW_VISITOR_CONTACT", "Ver teléfono y correo de visitantes", "visitors", "view_contact", "BRANCH"),
    ("MANAGE_VISITOR_TYPES", "Administrar tipos de visitante", "visitor_types", "manage", "GLOBAL"),
    ("MANAGE_VISIT_REASONS", "Administrar motivos de visita", "visit_reasons", "manage", "GLOBAL"),
    ("MANAGE_USERS", "Administrar usuarios", "users", "manage", "GLOBAL"),
    ("ASSIGN_USER_BRANCH", "Asignar usuarios a sucursales", "user_branch_assignments", "assign", "GLOBAL"),
    ("MOVE_USER_BRANCH", "Trasladar usuarios entre sucursales", "user_branch_assignments", "move", "GLOBAL"),
    ("VIEW_REPORTS", "Ver reportes de sucursal", "reports", "view", "BRANCH"),
    ("VIEW_GLOBAL_REPORTS", "Ver reportes globales", "reports", "view_global", "GLOBAL"),
    ("VIEW_AUDIT_LOGS", "Ver auditoría", "audit_logs", "view", "GLOBAL"),
    ("MANAGE_BRANCHES", "Administrar sucursales", "branches", "manage", "GLOBAL"),
)

ROLES = (
    ("SUPER_ADMIN", "Superadministrador", "Acceso materializado mediante todos los permisos aprobados."),
    ("ADMIN", "Administrador", "Administración institucional mediante permisos explícitos."),
    ("RECEPTIONIST", "Recepcionista", "Operación diaria de visitas y visitantes en su sucursal."),
    ("USER", "Usuario", "Consulta básica de visitas y visitantes en su sucursal."),
)

ROLE_PERMISSION_CODES = {
    "SUPER_ADMIN": {code for code, *_ in PERMISSIONS},
    "ADMIN": {
        "VIEW_VISITS", "CREATE_VISIT", "UPDATE_VISIT", "DELETE_VISIT",
        "VIEW_VISITORS", "CREATE_VISITOR", "UPDATE_VISITOR", "MANAGE_USERS",
        "ASSIGN_USER_BRANCH", "MOVE_USER_BRANCH", "VIEW_REPORTS",
        "VIEW_GLOBAL_REPORTS", "VIEW_AUDIT_LOGS", "MANAGE_BRANCHES",
        "VIEW_VISITOR_CONTACT", "MANAGE_VISITOR_TYPES", "MANAGE_VISIT_REASONS",
    },
    "RECEPTIONIST": {"VIEW_VISITS", "CREATE_VISIT", "VIEW_VISITORS", "CREATE_VISITOR", "UPDATE_VISITOR"},
    "USER": {"VIEW_VISITS", "VIEW_VISITORS"},
}
