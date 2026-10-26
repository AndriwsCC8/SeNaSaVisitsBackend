# Contrato y estado actual del backend SeNaSa Visits

**Actualizado:** 2026-10-09. Este documento describe el backend presente en el workspace; no presupone que el frontend React/Vite esté incluido aquí.

## Estado verificado

- API FastAPI con autenticación JWT, permisos, aislamiento por sucursal, administración de usuarios, visitantes, visitas, auditoría, dashboard y reportes.
- Persistencia SQL Server vía SQLAlchemy; Alembic está en `276b94986df8` y `alembic check` no detectó cambios pendientes durante la auditoría. No se requiere modificar el esquema para la integración descrita.
- Los catálogos de sucursales, tipos de sucursal, tipos de visitante, motivos y roles tienen endpoints de solo lectura (ver "API de catálogos"); se inicializan con los comandos manuales descritos abajo.
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
- Permisos `GLOBAL` (usuarios, auditoría, `VIEW_GLOBAL_REPORTS`) no usan sucursal. En rutas globales de usuarios y auditoría, `branch_id` es un filtro de búsqueda y no altera la evaluación del permiso.
- En reportes, un usuario con alcance de sucursal que envía otro `branch_id` recibe `403`.

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
- Las respuestas de visitantes y visitas enmascaran la identificación. `IdentificationNormalized` nunca se expone. Ver "Privacidad de visitantes" abajo para teléfono y correo.
- Filtros de intervalo en visitas, dashboard, reportes y auditoría: `date_from` inclusivo y `date_to` exclusivo; un rango vacío o invertido (`date_to <= date_from`) responde `422`. Ver "Fechas y timestamps".
- No hay endpoints de escritura de catálogos ni `GET /api/permissions`; los catálogos se leen en `/api/branches`, `/api/branch-types`, `/api/visitor-types`, `/api/visit-reasons` y `/api/roles`.
- Errores: cada operación declara en OpenAPI los códigos aplicables (`401`, `403`, `404`, `409`, `422`). El cuerpo funcional es `{"detail": "mensaje"}`; los `422` de validación de FastAPI usan `detail` como lista de errores por campo.

## CORS

`CORS_ORIGINS` es una lista separada por comas, con coincidencia exacta de origen. Los orígenes locales incluidos por defecto son `http://localhost:5173`, `http://localhost:8443`, `https://localhost:8443`, `http://127.0.0.1:8443` y `https://127.0.0.1:8443`. Para otro puerto, hostname, IP de red local o dominio, agregar explícitamente ese origen en la variable de entorno (ej. `CORS_ORIGINS=http://localhost:5173,http://192.168.1.50:8443`) y reiniciar. `*` se rechaza al iniciar. `CORS_ALLOW_CREDENTIALS` es `false` por defecto: la API usa `Authorization: Bearer`, no cookies. La compatibilidad HTTPS solo está probada a nivel de cabeceras CORS; no se ha probado un servidor TLS.

Métodos admitidos: GET, POST, PUT, PATCH, DELETE y OPTIONS. Headers admitidos: Authorization y Content-Type.

## Tokens, 401 y 403

- El access token dura `ACCESS_TOKEN_EXPIRE_MINUTES` (30 por defecto); no hay refresh ni logout, por lo que al expirar el cliente debe repetir el login.
- `401` (con `WWW-Authenticate: Bearer`): token ausente, malformado, expirado, de usuario inexistente o inactivo.
- `403`: identidad válida sin permiso efectivo, sin sucursal vigente, o con `branch_id` distinto a su sucursal autorizada.
- `409`: conflicto de estado (duplicados, transiciones de visita no permitidas, solapamiento de asignaciones).
- Un fallo interno o de base de datos al validar el token produce `500` genérico (`Ha ocurrido un error interno...`), nunca `401`, y no expone SQL ni trazas. El login responde `503` si la base no está disponible.
- En Swagger (`/docs`): ejecutar `POST /api/auth/login` con el JSON, copiar `access_token`, pulsar **Authorize** e ingresar solo el token (Swagger añade `Bearer`).

## Fechas y timestamps

- SQL Server almacena fechas UTC sin zona. Las respuestas serializan todos los timestamps como ISO 8601 UTC con sufijo `Z` (ej. `2026-09-01T14:30:00Z`).
- Parámetros de entrada: un valor con zona (`-04:00`, `Z`) se convierte una vez a UTC; un valor sin zona se interpreta como UTC.
- `date_from` es inclusivo y `date_to` exclusivo en visitas, dashboard, reportes y auditoría. **Cambio de compatibilidad:** `GET /api/audit-logs` antes trataba `date_to` como inclusivo. Para incluir todo un día local, enviar como `date_to` el inicio del día siguiente.
- Frontend: la zona operativa es `America/Santo_Domingo` (UTC-4, sin horario de verano). Parsear el `Z` como UTC y mostrar con `Intl.DateTimeFormat(..., { timeZone: 'America/Santo_Domingo' })`. Para filtrar el día local D, enviar `date_from` = medianoche local de D convertida a UTC (D 04:00Z) y `date_to` = medianoche local de D+1 convertida a UTC.

## Privacidad de visitantes

Campos de `VisitorResponse`: `identification` (enmascarada), `first_name`, `last_name`, `phone`, `email`, `contact_masked`, `company`, `visitor_type`, `is_active`, `created_at`, `updated_at`.

**Política vigente:** teléfono y correo se devuelven completos solo con el permiso `VIEW_VISITOR_CONTACT` (ámbito BRANCH, evaluado en la sucursal vigente del usuario). `VIEW_VISITORS`, `CREATE_VISITOR` y `UPDATE_VISITOR` no lo implican. Sin él, el teléfono se muestra como `***` + 2 últimos dígitos, el correo como `primera-letra***@dominio` y `contact_masked` es `true`; aplica a listado, detalle y a las respuestas de crear, actualizar, activar y desactivar. Visitas, reportes y auditoría no contienen estos campos. Por defecto lo reciben solo `SUPER_ADMIN` y `ADMIN`; si `RECEPTIONIST` debe verlo es una decisión institucional pendiente (se concede con una asignación de rol, no por código). Contrato completo: [api-contract.md](api-contract.md).

## Inicialización segura de primera instalación

Todos los comandos son manuales (nunca se ejecutan al arrancar FastAPI), se ejecutan desde la raíz del backend y usan una única transacción que se revierte ante cualquier error. Orden obligatorio en una instalación nueva:

```powershell
# 1. Esquema (sin cambios de modelo en esta fase)
alembic upgrade head

# 2. Roles y permisos aprobados (no requiere ningún usuario)
python -m scripts.seed_authorization

# 3. Datos oficiales: validar, comparar con la base y cargar
python -m scripts.load_reference_data --file C:\ruta\oficial.json --validate-only
python -m scripts.load_reference_data --file C:\ruta\oficial.json --dry-run
python -m scripts.load_reference_data --file C:\ruta\oficial.json --apply

# 4. Primer administrador (la contraseña se pide dos veces, sin eco)
python -m scripts.bootstrap_first_admin --confirm-initialization `
  --username <usuario> --first-name <nombre> --last-name <apellido> --branch-code <CODIGO_SUCURSAL_CARGADA>
```

**Por qué no se pueden asignar permisos a roles antes del administrador:** `RolePermission.assigned_by_user_id` es obligatorio y referencia a un usuario, y el esquema no se modifica en esta fase. Por eso el paso 2 solo crea `Role` y `Permission`, y el paso 4 crea los `RolePermission` (asignados por el propio primer administrador).

### `seed_authorization`
Crea los roles y permisos faltantes del catálogo aprobado (`scripts/permission_catalog.py`). Es idempotente. Si un rol o permiso ya existe inactivo, o un permiso con ámbito distinto, aborta sin escribir nada.

### `load_reference_data`
Entrada: JSON con las secciones `branch_types`, `branches` (con `branch_type_code`), `visitor_types` y `visit_reasons`; cada elemento lleva `code` (A-Z, 0-9, `-`, `_`) y `name`, y opcionalmente `description` (en sucursales: `region`, `address`, `phone`). No se aceptan campos desconocidos, códigos duplicados ni referencias a tipos de sucursal inexistentes. Plantilla: [examples/reference-data.example.json](examples/reference-data.example.json), con códigos `EJEMPLO_*`; con `is_example` o códigos de ejemplo se rechaza `--apply`.

- `--validate-only`: valida el archivo sin abrir la base.
- `--dry-run`: compara con la base (solo lectura) e informa qué se crearía.
- `--apply`: inserta lo que falta. Un registro existente idéntico se deja igual; uno existente con datos distintos o inactivo es un **conflicto**: se informa y se aborta toda la carga. No existe política de sobrescritura.

El archivo oficial lo debe entregar y aprobar la institución (tipos de sucursal, sucursales, tipos de visitante y motivos). No se incluyen datos reales en este repositorio, y el archivo oficial debe guardarse fuera del control de versiones salvo decisión institucional.

### `bootstrap_first_admin`
Requisitos previos: catálogo de autorización completo y la sucursal indicada existente y activa. Comportamiento:

1. exige `--confirm-initialization`; la contraseña solo se solicita por `getpass` (mínimo 12 caracteres, minúscula, mayúscula y número), se almacena con Argon2 y nunca se registra ni se imprime;
2. si no existen usuarios, crea el usuario, el rol `SUPER_ADMIN` activo, la asignación vigente a la sucursal y los `RolePermission` aprobados;
3. verifica con `PermissionService` (el mismo evaluador de la API) que el administrador obtiene **todos** los permisos del catálogo: los `GLOBAL` sin sucursal y los `BRANCH` en su sucursal; si falta alguno, revierte;
4. si el usuario indicado ya existe y está correctamente configurado, no cambia nada (idempotente);
5. aborta, sin modificar privilegios, ante usuarios existentes con otro nombre, configuración parcial (rol inactivo, asignación distinta o faltante, permisos faltantes), catálogo incompleto o sucursal inexistente/inactiva. No promueve usuarios existentes.

`SUPER_ADMIN` por sí solo no basta: la autorización se evalúa por permisos efectivos, y los permisos `BRANCH` además exigen una asignación vigente a una sucursal activa. Por eso el administrador debe tener sucursal. Los scripts `seed_roles`, `seed_permissions` y `bootstrap_user` están **obsoletos**: ya no escriben nada y indican el procedimiento vigente. `seed_role_permissions --assigned-by-user-id` sigue vigente solo para re-sincronizar grants (por ejemplo tras añadir permisos al catálogo: primero `seed_authorization`, luego `seed_role_permissions`) cuando ya existe un usuario; solo agrega, nunca revoca.

## API de catálogos

Solo lectura, sin paginación (catálogos acotados), ordenados por nombre y devueltos como listas. Por defecto solo registros activos; `include_inactive=true` incluye inactivos y exige el permiso de administración **propio de cada catálogo** (ningún otro lo sustituye): sucursales y tipos de sucursal `MANAGE_BRANCHES`, tipos de visitante `MANAGE_VISITOR_TYPES`, motivos de visita `MANAGE_VISIT_REASONS` (todos GLOBAL; sin él, 403). Roles no tiene opción de inactivos. Las visitas históricas no se filtran por el estado del catálogo asociado. Un `branch_id` enviado por el cliente se ignora: el alcance siempre se resuelve en el servidor. Errores documentados: 401, 403 y 422 (parámetro inválido). Esquemas completos en [api-contract.md](api-contract.md).

| Ruta | Pantallas | Acceso | Campos |
|---|---|---|---|
| `GET /api/branches` | Asignación/traslado de usuarios, filtros de reportes y auditoría, formularios | Global: `MANAGE_BRANCHES`, `MANAGE_USERS`, `ASSIGN_USER_BRANCH`, `MOVE_USER_BRANCH`, `VIEW_GLOBAL_REPORTS` o `VIEW_AUDIT_LOGS` ven todas las activas. Sucursal: `VIEW_VISITS`, `CREATE_VISIT`, `UPDATE_VISIT`, `VIEW_VISITORS` o `VIEW_REPORTS` ven solo su sucursal vigente. `include_inactive` requiere `MANAGE_BRANCHES` | `id`, `code`, `name`, `branch_type_id`, `is_active` |
| `GET /api/branch-types` | Administración de sucursales | `MANAGE_BRANCHES` | `id`, `code`, `name`, `is_active` |
| `GET /api/visitor-types` | Formulario de visitantes | Sucursal: `VIEW_VISITORS`, `CREATE_VISITOR`, `UPDATE_VISITOR`, `VIEW_VISITS` o `CREATE_VISIT`; global: `MANAGE_VISITOR_TYPES` | `id`, `code`, `name`, `is_active` |
| `GET /api/visit-reasons` | Formulario de visitas y filtros de reportes | Sucursal: `VIEW_VISITS`, `CREATE_VISIT`, `UPDATE_VISIT` o `VIEW_REPORTS`; global: `VIEW_GLOBAL_REPORTS` o `MANAGE_VISIT_REASONS` | `id`, `code`, `name`, `is_active` |
| `GET /api/roles` | Creación de usuarios (`role_code`) | `MANAGE_USERS`; solo roles activos | `id`, `code`, `name` |

Un usuario sin permiso relevante, o con permisos de sucursal pero sin asignación vigente, recibe 403. `GET /api/permissions` no se implementó: ningún flujo de administración actual lo necesita (no hay gestión de permisos por la API).

## Desarrollo y comprobaciones

- Configuración de ejemplo: `.env.example`; los secretos locales deben permanecer fuera de Git.
- `JWT_SECRET_KEY` debe tener al menos 32 caracteres; en `ENVIRONMENT=production` la aplicación no arranca con una clave menor, y en otros entornos solo registra una advertencia. Nunca imprimir ni versionar la clave.
- Pruebas: `pytest -q`.
- Ejecución: `uvicorn main:app --reload`.
- Estado de esquema: `alembic current`, `alembic heads`, `alembic check`.
- Documentación interactiva: `/docs`; OpenAPI JSON: `/openapi.json`.
