# Contrato y estado actual del backend SeNaSa Visits

**Actualizado:** 2026-10-09. Este documento describe el backend presente en el workspace; no presupone que el frontend React/Vite esté incluido aquí.

## Estado verificado

- API FastAPI con autenticación JWT, permisos, aislamiento por sucursal, administración de usuarios, visitantes, visitas, auditoría, dashboard y reportes.
- Persistencia SQL Server vía SQLAlchemy; Alembic está en `276b94986df8` y `alembic check` no detectó cambios pendientes durante la auditoría. No se requiere modificar el esquema para la integración descrita.
- Los catálogos no tienen endpoints HTTP de lectura/escritura. Se inicializan mediante el comando manual documentado abajo.
- La base revisada no tenía usuarios, asignaciones de rol, sucursales ni catálogos operativos. Sin una inicialización aprobada no es posible completar login o flujos de negocio con datos reales.
- Las fuentes del frontend no están en este workspace; la compatibilidad de componentes y mocks debe confirmarse en el repositorio React/Vite.

## Organización del código

- `app/api/routes`: rutas HTTP y serialización de respuestas.
- `app/api/dependencies`: autenticación, permisos y resolución del contexto de sucursal.
- `app/application/dto` y `app/application/services`: contratos y reglas de aplicación.
- `app/infrastructure/persistence/models`: modelos SQLAlchemy.
- `app/core`: configuración, errores y primitivas de seguridad.
- `migrations`: revisiones Alembic; `tests`: pruebas automatizadas.

## Contrato de autenticación

### Login

`POST /api/auth/login` recibe JSON (no `application/x-www-form-urlencoded`):

```json
{"username":"usuario","password":"contraseña"}
```

Con credenciales válidas devuelve `access_token`, `token_type: "bearer"` y `user` con `id`, `username`, `first_name`, `last_name`, `role` y `branch`. El token es de acceso y actualmente dura 30 minutos. No existen endpoints de refresh ni logout.

Errores: `401` para credenciales inválidas; `503` cuando la base de datos no está disponible. El hash de contraseña nunca forma parte de la respuesta.

Las demás rutas protegidas usan `Authorization: Bearer <access_token>`. OpenAPI presenta esquema HTTP Bearer y el body JSON del login. `GET /api/auth/me` devuelve el mismo contrato de identidad. `branch` solo se devuelve cuando hay exactamente una asignación vigente a una sucursal activa; si no existe exactamente una, es `null`.

`GET /api/auth/permissions/{permission_code}` es un diagnóstico, no una concesión. Para permiso `BRANCH`, enviar `branch_id` de la asignación actual; para un permiso `GLOBAL`, omitirlo.

## Contrato de autorización y sucursal

- `require_permission(...)` evalúa permisos globales sin interpretar los filtros de consulta como contexto de autorización.
- Las operaciones con permiso `BRANCH` resuelven la única asignación vigente en el servidor y comprueban el permiso para esa sucursal. Un `branch_id` opcional en estas dependencias solo verifica que coincida con la sucursal autorizada: nunca otorga acceso.
- Si falta una asignación vigente, la sucursal está inactiva, hay asignaciones actuales ambiguas o no existe permiso efectivo, se deniega la operación.
- Precedencia de reglas: `DENY` explícito > `ALLOW` explícito > permiso de rol (`RolePermission`) > denegar.
- Visitantes son perfiles globales sin `BranchId`, aunque sus operaciones requieren contexto y permisos de sucursal; sus resultados no se particionan por sucursal.
- En rutas globales de usuarios y auditoría, `branch_id` es un filtro de datos cuando esa ruta lo define; no altera la evaluación del permiso global.

## Rutas funcionales

| Área | Rutas |
|---|---|
| Salud | `GET /api/health`, `GET /api/health/db` |
| Autenticación | `POST /api/auth/login`, `GET /api/auth/me`, `GET /api/auth/permissions/{permission_code}` |
| Usuarios | `GET/POST /api/users`, `GET/PATCH /api/users/{user_id}`, activar/desactivar, roles, asignaciones y transferencias |
| Visitantes | `GET/POST /api/visitors`, `GET/PATCH /api/visitors/{visitor_id}`, activar/desactivar |
| Visitas | `GET/POST /api/visits`, `GET/PATCH /api/visits/{visit_id}`, completar y cancelar |
| Dashboard | `GET /api/dashboard/summary`, `visits-by-day`, `visits-by-status`, `visits-by-reason` |
| Reportes | `GET /api/reports/visits`, `GET /api/reports/visits/summary` |
| Auditoría | `GET /api/audit-logs` |

Los esquemas completos de parámetros, request y response están publicados en `/docs` y `/openapi.json`.

Reglas relevantes:

- Crear visita requiere `visitor_id` y `reason_id`; el backend deriva sucursal y usuario registrador del contexto autenticado.
- Las respuestas de visitantes y visitas enmascaran la identificación. El response de visitantes actualmente incluye teléfono y correo sin enmascarar.
- El límite superior `date_to` es exclusivo en visitas, dashboard y reportes. Auditoría actualmente trata `date_to` como inclusivo.
- No hay endpoints de catálogos para sucursales, tipos de sucursal, tipos de visitante, motivos, roles o permisos.
- OpenAPI debe consultarse para las respuestas de error por operación; las validaciones producen `422`, autenticación `401`, autorización `403` y reglas de negocio pueden producir `404`/`409`.

## CORS

`CORS_ORIGINS` es una lista separada por comas, con coincidencia exacta de origen. Los orígenes locales incluidos por defecto son `http://localhost:5173`, `http://localhost:8443`, `https://localhost:8443`, `http://127.0.0.1:8443` y `https://127.0.0.1:8443`. Para otro puerto, hostname o dominio, agregar explícitamente el origen real en el entorno; no usar `*` con credenciales.

Métodos admitidos: GET, POST, PUT, PATCH, DELETE y OPTIONS. Headers admitidos: Authorization y Content-Type.

## Inicialización segura de primera instalación

El bootstrap es manual; no se ejecuta durante el arranque de FastAPI. Ejecutar primero `alembic upgrade head` y luego, solo en la instalación inicial aprobada, ejecutar desde la raíz del backend:

```powershell
python -m scripts.bootstrap_first_admin `
  --confirm-initialization `
  --username admin `
  --first-name Administrador `
  --last-name Institucional `
  --branch-type "OFFICE=Oficina" `
  --branch "HQ=Oficina Central" `
  --visitor-type "GENERAL=Visitante" `
  --visit-reason "MEETING=Reunión"
```

Los códigos y nombres del ejemplo son ilustrativos; reemplazarlos por los aprobados institucionalmente. Se puede repetir `--visitor-type` y `--visit-reason` por cada valor. La contraseña se solicita dos veces sin eco en terminal y exige al menos 12 caracteres, minúscula, mayúscula y número. No se pasa la contraseña como argumento ni se guarda en el código.

El comando:

1. exige `--confirm-initialization`;
2. bloquea la tabla de usuarios y se niega si ya existe cualquier usuario;
3. crea en una sola transacción el primer usuario activo, el rol `SUPER_ADMIN`, su asignación de sucursal vigente, permisos/roles aprobados y catálogos iniciales;
4. revierte la transacción ante error.

El primer usuario recibe privilegios globales de superadministrador. Ejecutar solo con acceso autorizado a una base vacía y conservar la contraseña según la política institucional. Para instalaciones que ya tienen usuarios, no usar este bootstrap: aplicar el procedimiento administrativo aprobado de asignación de roles y sucursal.

## Desarrollo y comprobaciones

- Configuración de ejemplo: `.env.example`; los secretos locales deben permanecer fuera de Git.
- `JWT_SECRET_KEY` debe tener al menos 32 caracteres; la aplicación rechaza claves menores en producción.
- Pruebas: `pytest -q`.
- Estado de esquema: `alembic current`, `alembic heads`, `alembic check`.
- Documentación interactiva: `/docs`; OpenAPI JSON: `/openapi.json`.
