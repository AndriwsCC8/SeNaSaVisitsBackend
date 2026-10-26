# Contrato de la API SeNaSa Visits

Este documento describe lo que el backend **implementa hoy** (código y OpenAPI de `/openapi.json`). No describe el frontend: no se ha inspeccionado ningún código React/Vite, por lo que no se afirma compatibilidad con sus formularios. Todos los ejemplos usan datos **sintéticos**.

Base: `http://localhost:8000`, prefijo `/api`. Documentación interactiva: `/docs`.

## 1. Convenciones comunes

### Formato
- JSON UTF-8. Nombres de campo en `snake_case`.
- **Fechas y horas:** SQL Server guarda UTC sin zona. Todas las respuestas serializan `datetime` como ISO 8601 UTC con sufijo `Z` (`2026-09-01T14:30:00Z`). En entrada, un valor con zona se convierte a UTC y uno sin zona se interpreta como UTC. Envíe siempre ISO 8601 completo con `Z` u offset. Zona operativa esperada: `America/Santo_Domingo` (UTC-4, sin horario de verano); la conversión a hora local es responsabilidad del cliente.
- **Rangos:** `date_from` inclusivo, `date_to` exclusivo, en visitas, dashboard, reportes y auditoría. `date_to <= date_from` responde `422`.
- **Excepción conocida:** `GET /api/dashboard/visits-by-day` agrupa por día **UTC** (`date`), no por día local. Una visita registrada después de las 20:00 hora local cae en el día UTC siguiente.
- **Paginación** (usuarios, visitantes, visitas, reportes, auditoría): `page` (≥1, por defecto 1) y `page_size` (1-100). Defectos: usuarios 20, visitantes 20, visitas 20, reportes 25, auditoría 50. La respuesta incluye `items`, `total`, `page`, `page_size` (reportes añade `total_pages`). Los catálogos no se paginan.
- **Orden fijo** (no configurable): usuarios y visitantes por `id` ascendente; visitas y reporte detallado por `entry_at` descendente y `id` descendente; auditoría por `created_at` descendente y `id` descendente; catálogos por `name`.

### Errores
Errores funcionales (401, 403, 404, 409, y 422 de reglas de negocio) usan:

```json
{ "detail": "Mensaje legible en español" }
```

Los `422` de validación de FastAPI/Pydantic (tipos, campos faltantes, límites, parámetros) usan **otro formato**: `detail` es una lista y cada entrada puede incluir `input` con el valor enviado:

```json
{
  "detail": [
    { "type": "missing", "loc": ["body", "first_name"], "msg": "Field required", "input": { "last_name": "Ejemplo" } }
  ]
}
```

El cliente debe aceptar ambas formas de `detail`. Los mensajes funcionales están en español y no son códigos estables; no los use para lógica. Un fallo interno responde `500` con `{"detail": "Ha ocurrido un error interno. Intente de nuevo más tarde."}` sin detalles.

| Código | Significado |
|---|---|
| 401 | Token ausente, malformado, expirado, usuario inexistente o inactivo. Incluye `WWW-Authenticate: Bearer` |
| 403 | Identidad válida sin permiso efectivo, sin sucursal vigente, o `branch_id` distinto al autorizado |
| 404 | Recurso inexistente (o fuera de la sucursal autorizada, en visitas) |
| 409 | Conflicto de estado o duplicado (identificación, username, email, transición inválida, solape de asignaciones) |
| 422 | Validación, rango de fechas inválido o referencia inactiva |

### Autorización
- Permisos `GLOBAL`: no dependen de una sucursal. Un `branch_id` en esas rutas es solo un **filtro de búsqueda**.
- Permisos `BRANCH`: se evalúan en la **única asignación vigente** del usuario (estado `ACTIVE`, fechas vigentes, sucursal activa). Si no hay exactamente una, se responde `403`. Un `branch_id` enviado por el cliente solo se compara con la sucursal autorizada; si difiere, `403`. Nunca concede acceso.
- Precedencia de reglas: `DENY` explícito > `ALLOW` explícito > permiso del rol.

## 2. Autenticación

### `POST /api/auth/login` (público)
Cuerpo JSON (no `x-www-form-urlencoded`): `username` (1-80), `password` (1-256).

```json
{ "username": "usuario.ejemplo", "password": "<contraseña>" }
```

Respuesta `200`:

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": { "id": 7, "username": "usuario.ejemplo", "first_name": "Ana", "last_name": "Ejemplo", "role": "RECEPTIONIST", "branch": { "id": 3, "code": "SUC_EJEMPLO", "name": "Sucursal de ejemplo" } }
}
```

- `user.role`: código del primer rol activo, o `null`. `user.branch`: solo si hay exactamente una asignación vigente a sucursal activa; si no, `null`.
- Errores: `401` credenciales inválidas (mensaje genérico, sin distinguir usuario inexistente, inactivo o contraseña incorrecta); `503` si la base de datos no responde (`Retry-After: 5`).

### Token
- Se envía como `Authorization: Bearer <access_token>`. OpenAPI declara solo el esquema HTTP Bearer.
- Claims: `sub` (id de usuario), `type: "access"`, `iat`, `exp`. Duración: `ACCESS_TOKEN_EXPIRE_MINUTES` (30 por defecto).
- Al expirar, cualquier ruta protegida responde `401`; el cliente debe volver a autenticar. **No existen refresh ni logout.** El backend revalida en cada petición que el usuario exista y esté activo.

### `GET /api/auth/me`
Devuelve el mismo objeto `user` del login (id, username, first_name, last_name, role, branch). No lista permisos.

### `GET /api/auth/permissions/{permission_code}?branch_id=`
Diagnóstico: `{ "permission": "VIEW_VISITS", "allowed": true }`. Para permisos `BRANCH` envíe el `branch_id` de la asignación; para `GLOBAL` omítalo (con `branch_id` responde `allowed: false`). No concede acceso. **Falta** un endpoint que devuelva todos los permisos efectivos del usuario; el frontend solo puede preguntarlos de uno en uno o inferirlos del rol (no recomendado).

### Catálogo de permisos (`scripts/permission_catalog.py`)
| Permiso | Ámbito |
|---|---|
| `VIEW_VISITS`, `CREATE_VISIT`, `UPDATE_VISIT`, `DELETE_VISIT` (sin ruta) | BRANCH |
| `VIEW_VISITORS`, `CREATE_VISITOR`, `UPDATE_VISITOR`, `VIEW_VISITOR_CONTACT` | BRANCH |
| `VIEW_REPORTS` | BRANCH |
| `MANAGE_USERS`, `ASSIGN_USER_BRANCH`, `MOVE_USER_BRANCH` | GLOBAL |
| `VIEW_GLOBAL_REPORTS`, `VIEW_AUDIT_LOGS` | GLOBAL |
| `MANAGE_BRANCHES`, `MANAGE_VISITOR_TYPES`, `MANAGE_VISIT_REASONS` | GLOBAL |

Asignación por rol (la define el código; no hay API para editarla): `SUPER_ADMIN` todos; `ADMIN` todos; `RECEPTIONIST`: `VIEW_VISITS`, `CREATE_VISIT`, `VIEW_VISITORS`, `CREATE_VISITOR`, `UPDATE_VISITOR`; `USER`: `VIEW_VISITS`, `VIEW_VISITORS`. `UPDATE_VISIT`, `VIEW_REPORTS` y `VIEW_VISITOR_CONTACT` no están en `RECEPTIONIST`/`USER` (pendiente de decisión institucional, ver §10). `DELETE_VISIT` existe en el catálogo pero no hay ruta que lo use.

## 3. Usuarios (`/api/users`, permisos GLOBAL)

Todas las rutas requieren `MANAGE_USERS`, salvo lo indicado.

| Ruta | Permiso | Notas |
|---|---|---|
| `GET /api/users` | `MANAGE_USERS` | Filtros: `page`, `page_size`, `search` (≤100; busca username, nombres y código de empleado), `is_active`, `branch_id` (filtro), `role_code` |
| `GET /api/users/{user_id}` | `MANAGE_USERS` | 404 si no existe |
| `POST /api/users` | `MANAGE_USERS`; además `ASSIGN_USER_BRANCH` si envía `branch_id` | 201 |
| `PATCH /api/users/{user_id}` | `MANAGE_USERS` | |
| `POST /api/users/{user_id}/activate` · `/deactivate` | `MANAGE_USERS` | Cambia `is_active`; no borra |
| `GET /api/users/{user_id}/roles` | `MANAGE_USERS` | Lista `RoleResponse` activos |
| `GET /api/users/{user_id}/assignments` | `MANAGE_USERS` | Historial, más reciente primero |
| `POST /api/users/{user_id}/assignments` | `ASSIGN_USER_BRANCH` | 201 |
| `POST /api/users/{user_id}/transfer` | `MOVE_USER_BRANCH` | Cierra la asignación vigente y crea otra |

**Crear** (`UserCreate`): obligatorios `username` (1-80), `first_name`, `last_name` (1-100), `password` (8-256; se guarda con Argon2 y nunca se devuelve). Opcionales: `email` (≤254), `employee_code` (≤50), `role_code`, `branch_id`, `assignment_valid_from`. **Actualizar** (`UserUpdate`, todos opcionales): `email`, `first_name`, `last_name`, `employee_code`, `role_code`. No hay cambio de contraseña ni de username por API.

**Respuesta** (`UserResponse`, solo lectura): `id`, `username`, `email`, `first_name`, `last_name`, `employee_code`, `is_active`, `created_at`, `updated_at`, `deactivated_at`, `roles[]` (`id`, `code`, `name`), `current_assignment` (`id`, `branch_id`, `branch{id,code,name}`, `valid_from`, `valid_until`, `status`, `reason`) o `null`.

```json
{ "id": 12, "username": "usuario.ejemplo", "email": null, "first_name": "Ana", "last_name": "Ejemplo", "employee_code": null,
  "is_active": true, "created_at": "2026-09-01T14:30:00Z", "updated_at": "2026-09-01T14:30:00Z", "deactivated_at": null,
  "roles": [{ "id": 3, "code": "RECEPTIONIST", "name": "Recepcionista" }],
  "current_assignment": { "id": 5, "branch_id": 3, "branch": { "id": 3, "code": "SUC_EJEMPLO", "name": "Sucursal de ejemplo" },
    "valid_from": "2026-09-01T14:30:00Z", "valid_until": null, "status": "ACTIVE", "reason": null } }
```

**Asignación** (`UserAssignmentCreate`): `branch_id` obligatorio; `valid_from`, `valid_until`, `reason` (≤500) opcionales. **Traslado** (`UserTransferRequest`): `new_branch_id` obligatorio; `effective_at`, `reason` opcionales. Los intervalos son `[valid_from, valid_until)`.

Errores de negocio: 404 usuario/sucursal/rol inexistente; 409 username, email o código de empleado duplicado, usuario ya asignado a esa sucursal, solape de intervalos; 422 usuario o sucursal inactivos, rol inactivo, `valid_until <= valid_from`.

## 4. Visitantes (`/api/visitors`, permisos BRANCH)

Un **visitante** es un perfil global de persona (sin `branch_id`); una **visita** es un evento de entrada/salida de una sucursal. Aunque el perfil es global, las operaciones exigen contexto y permisos de la sucursal del usuario.

| Ruta | Permiso |
|---|---|
| `GET /api/visitors` | `VIEW_VISITORS` |
| `GET /api/visitors/{visitor_id}` | `VIEW_VISITORS` |
| `POST /api/visitors` (201) | `CREATE_VISITOR` |
| `PATCH /api/visitors/{visitor_id}` · `POST .../activate` · `POST .../deactivate` | `UPDATE_VISITOR` |

Filtros de listado: `page`, `page_size`, `search` (≤100), `is_active`, `visitor_type_id`.

**Campos buscables (`search`, coincidencia parcial):** con `VIEW_VISITOR_CONTACT`: nombre, apellido, identificación normalizada (sin guiones si es numérica; el cliente debe normalizar el texto buscado), empresa, **correo y teléfono**. Sin `VIEW_VISITOR_CONTACT`: solo nombre, apellido, identificación normalizada y empresa; el correo y el teléfono no influyen en resultados ni en `total`. `branch_id` no amplía el acceso.

**Crear** (`VisitorCreate`): obligatorios `first_name`, `last_name` (1-100). Opcionales: `identification` (≤50), `phone` (≤30), `email` (≤254, validado), `company` (≤200), `visitor_type_id` (debe existir y estar activo). **Actualizar**: los mismos campos, todos opcionales; omitir `identification` no la borra. `identification_normalized` no se acepta ni se devuelve.

**Respuesta** (`VisitorResponse`): `id`, `identification` (**siempre enmascarada**, ej. `001****3445`), `first_name`, `last_name`, `phone`, `email`, `contact_masked`, `company`, `visitor_type` (`id`,`code`,`name`) o `null`, `is_active`, `created_at`, `updated_at`.

### Política de teléfono y correo
`phone` y `email` se devuelven completos **solo** si el usuario tiene `VIEW_VISITOR_CONTACT` (BRANCH, evaluado en su sucursal vigente). `VIEW_VISITORS`, `CREATE_VISITOR` y `UPDATE_VISITOR` **no** lo implican. Sin el permiso: teléfono `***` + últimos 2 dígitos (valores ≤4 caracteres, todo `*`), correo `primera-letra***@dominio`, `null` si no existe, y `contact_masked: true`. Aplica a listado, detalle, creación, actualización, activación y desactivación. Las visitas, reportes y auditoría no contienen teléfono ni correo.

```json
{ "id": 41, "identification": "001****3445", "first_name": "Carlos", "last_name": "Ejemplo", "phone": "***23",
  "email": "c***@example.test", "contact_masked": true, "company": null,
  "visitor_type": { "id": 1, "code": "TIPO_EJEMPLO", "name": "Tipo de ejemplo" }, "is_active": true,
  "created_at": "2026-09-01T14:30:00Z", "updated_at": "2026-09-01T14:30:00Z" }
```

Errores: 404 visitante o tipo inexistente; 409 identificación ya registrada; 422 correo inválido o tipo inactivo.

## 5. Visitas (`/api/visits`, permisos BRANCH)

Todas las consultas y escrituras se limitan a la sucursal autorizada del usuario; una visita de otra sucursal responde `404`.

| Ruta | Permiso |
|---|---|
| `GET /api/visits`, `GET /api/visits/{visit_id}` | `VIEW_VISITS` |
| `POST /api/visits` (201) | `CREATE_VISIT` |
| `PATCH /api/visits/{visit_id}`, `POST .../complete`, `POST .../cancel` | `UPDATE_VISIT` |

Filtros de listado: `page`, `page_size`, `status` (`ACTIVE`, `COMPLETED`, `CANCELLED`), `visitor_id`, `reason_id`, `date_from`/`date_to` (sobre `entry_at`), `search` (≤100; identificación normalizada, nombre, empresa, destino, persona visitada).

**Crear** (`VisitCreate`, no admite campos extra): obligatorios `visitor_id`, `reason_id`; opcionales `entry_at` (por defecto, ahora UTC), `destination` (≤200), `visited_person` (≤200), `notes` (≤1000). Derivados por el servidor y **no enviables**: `branch` (de la asignación vigente), `registered_by` (usuario del token), `status` (`ACTIVE`). Visitante y motivo deben existir y estar activos.

**Actualizar** (`VisitUpdate`, sin campos extra): `reason_id`, `destination`, `visited_person`, `notes`. Solo visitas `ACTIVE` (409 si no). `status` y `branch_id` se rechazan con 422. **Completar**: `exit_at` opcional; no puede ser anterior a `entry_at` (422). **Cancelar**: `cancellation_reason` obligatorio (1-500).

Transiciones: `ACTIVE → COMPLETED` y `ACTIVE → CANCELLED`. Una visita completada o cancelada no cambia de estado (409). No hay borrado.

**Respuesta** (`VisitResponse`): `id`, `visitor` (`id`, `identification` enmascarada, `first_name`, `last_name`, `company`), `branch` (`id`,`code`,`name`), `registered_by` (`id`,`username`,`first_name`,`last_name`), `entry_at`, `exit_at`, `reason` (`id`,`code`,`name`), `destination`, `visited_person`, `status`, `notes`, `created_at`, `updated_at`, `completed_by`, `cancelled_by`, `cancelled_at`, `cancellation_reason`. Los motivos y visitantes inactivos siguen apareciendo en visitas históricas.

```json
{ "id": 900, "visitor": { "id": 41, "identification": "001****3445", "first_name": "Carlos", "last_name": "Ejemplo", "company": null },
  "branch": { "id": 3, "code": "SUC_EJEMPLO", "name": "Sucursal de ejemplo" },
  "registered_by": { "id": 12, "username": "usuario.ejemplo", "first_name": "Ana", "last_name": "Ejemplo" },
  "entry_at": "2026-09-01T14:30:00Z", "exit_at": null, "reason": { "id": 2, "code": "MOTIVO_EJEMPLO", "name": "Motivo de ejemplo" },
  "destination": "Área de ejemplo", "visited_person": "Persona de ejemplo", "status": "ACTIVE", "notes": null,
  "created_at": "2026-09-01T14:30:00Z", "updated_at": "2026-09-01T14:30:00Z", "completed_by": null, "cancelled_by": null,
  "cancelled_at": null, "cancellation_reason": null }
```

Errores: 404 visita, visitante o motivo inexistente; 409 estado no permite la operación; 422 visitante/motivo inactivo, `exit_at` anterior a `entry_at`, `status` inválido, rango de fechas inválido.

## 6. Catálogos (solo lectura, sin paginación)

Por defecto solo registros activos. `include_inactive=true` exige el permiso de administración **específico**: ningún permiso de otro catálogo lo sustituye. Un `branch_id` del cliente se ignora. Respuesta: lista de objetos.

| Ruta | Acceso | `include_inactive` | Campos |
|---|---|---|---|
| `GET /api/branches` | GLOBAL: `MANAGE_BRANCHES`, `MANAGE_USERS`, `ASSIGN_USER_BRANCH`, `MOVE_USER_BRANCH`, `VIEW_GLOBAL_REPORTS` o `VIEW_AUDIT_LOGS` ven todas las activas. BRANCH: `VIEW_VISITS`, `CREATE_VISIT`, `UPDATE_VISIT`, `VIEW_VISITORS` o `VIEW_REPORTS` ven solo su sucursal | `MANAGE_BRANCHES` | `id`, `code`, `name`, `branch_type_id`, `is_active` |
| `GET /api/branch-types` | `MANAGE_BRANCHES` | `MANAGE_BRANCHES` | `id`, `code`, `name`, `is_active` |
| `GET /api/visitor-types` | BRANCH: `VIEW_VISITORS`, `CREATE_VISITOR`, `UPDATE_VISITOR`, `VIEW_VISITS` o `CREATE_VISIT`; GLOBAL: `MANAGE_VISITOR_TYPES` | `MANAGE_VISITOR_TYPES` | `id`, `code`, `name`, `is_active` |
| `GET /api/visit-reasons` | BRANCH: `VIEW_VISITS`, `CREATE_VISIT`, `UPDATE_VISIT` o `VIEW_REPORTS`; GLOBAL: `VIEW_GLOBAL_REPORTS` o `MANAGE_VISIT_REASONS` | `MANAGE_VISIT_REASONS` | `id`, `code`, `name`, `is_active` |
| `GET /api/roles` | `MANAGE_USERS` | No existe: solo roles activos | `id`, `code`, `name` |

`403` si el usuario no tiene ningún permiso relevante o tiene solo permisos BRANCH sin asignación vigente. No hay `GET /api/permissions` ni endpoints de escritura de catálogos: los datos se cargan con `scripts.load_reference_data`.

## 7. Dashboard (`/api/dashboard/...`)

Alcance: `VIEW_GLOBAL_REPORTS` → global (`scope: "global"`, `branch_id: null`); si no, `VIEW_REPORTS` en la sucursal vigente → `scope: "branch"`. No acepta `branch_id`. Sin ninguno: `403`. Parámetros de todas las rutas: `date_from`, `date_to` (opcionales, sobre `entry_at`).

| Ruta | Respuesta |
|---|---|
| `GET /summary` | `scope`, `branch_id`, `date_from`, `date_to`, `total_visits`, `active_visits`, `completed_visits`, `cancelled_visits`, `unique_visitors` |
| `GET /visits-by-day` | `scope`, `branch_id`, `items[{ date, total }]` (día UTC) |
| `GET /visits-by-status` | `scope`, `branch_id`, `items[{ code, label, total }]` (`label` = código) |
| `GET /visits-by-reason` | igual, con `code`/`label` del motivo |

## 8. Reportes (`/api/reports/visits`)

Alcance: `VIEW_GLOBAL_REPORTS` (global; `branch_id` opcional como filtro, `404` si la sucursal no existe o está inactiva) o `VIEW_REPORTS` (solo su sucursal; un `branch_id` distinto responde `403`).

- `GET /api/reports/visits`: `page`, `page_size` (defecto 25), `date_from`, `date_to`, `status`, `reason_id`, `visitor_id`, `registered_by_user_id`, `branch_id`, `search`. Respuesta: `items` (id, entry_at, exit_at, status, destination, visited_person, notes, visitor, branch, reason, registered_by, completed_by_user_id, cancelled_by_user_id, cancelled_at, cancellation_reason), `total`, `page`, `page_size`, `total_pages`. Sin teléfono ni correo.
- `GET /api/reports/visits/summary`: mismos filtros más `group_by` obligatorio (`status`, `reason`, `registered_by`, `branch`; `branch` solo con alcance global). Respuesta: `{ "group_by": "status", "items": [{ "code": "ACTIVE", "label": "ACTIVE", "total": 4 }] }`.
- No hay exportación CSV/Excel/PDF.

## 9. Auditoría (`GET /api/audit-logs`, `VIEW_AUDIT_LOGS`, GLOBAL)

Filtros: `page`, `page_size` (defecto 50), `actor_user_id`, `action` (≤60), `entity_type` (≤80), `entity_id`, `branch_id` (filtro, no autorización), `date_from`, `date_to` (exclusivo). Quien tenga el permiso ve los registros de **todas** las sucursales. La API es de solo lectura (append-only).

Respuesta: `id`, `actor_user_id`, `action`, `entity_type`, `entity_id`, `branch_id`, `old_values` y `new_values` (cadenas JSON, **no objetos**), `ip_address`, `user_agent`, `correlation_id`, `created_at`. Las claves sensibles (contraseñas, hashes, tokens, `Authorization`, secretos, credenciales) se redactan al escribir y de nuevo al leer; la identificación de visitantes se registra como `[REDACTED]`. Acciones emitidas: `LOGIN`, `CREATE_USER`, `UPDATE_USER`, `DEACTIVATE_USER`, `ASSIGN_USER_BRANCH`, `MOVE_USER_BRANCH`, `CREATE_VISITOR`, `UPDATE_VISITOR`, `CREATE_VISIT`, `CHECKOUT_VISIT`, `CANCEL_VISIT`.

## 10. Qué se puede consumir y qué falta

**Confirmado en código y pruebas:** login JSON y Bearer; `me`; usuarios; asignaciones y traslados; visitantes con enmascaramiento; visitas con transiciones; catálogos de solo lectura; dashboard; reportes; auditoría; errores 401/403/404/409/422 declarados en OpenAPI.

**Campos de una visita:** solo los de `VisitResponse`. `destination` y `visited_person` son texto libre: no existe catálogo de departamentos ni de empleados visitados. No existen en el modelo: número de carné/gafete, vehículo, acompañantes, fotografía, firma, cita previa ni prerregistro. Si un formulario de recepción los necesita, **requieren decisión institucional y un cambio de esquema** (no se han inventado).

**Pendiente de validar contra el frontend real:** nombres de campos y formularios, qué pantallas exigen permisos de forma individual (no hay endpoint de permisos efectivos), formato de fechas esperado y manejo del `detail` doble de los 422.

**Decisiones institucionales abiertas:**
1. Qué roles reciben `VIEW_VISITOR_CONTACT` (hoy solo `SUPER_ADMIN` y `ADMIN`; `RECEPTIONIST` lo ve enmascarado).
2. Si `RECEPTIONIST` debe tener `UPDATE_VISIT` (hoy no puede completar ni cancelar visitas) y `VIEW_REPORTS`.
3. Quién administra tipos de visitante y motivos (`MANAGE_VISITOR_TYPES`, `MANAGE_VISIT_REASONS`: hoy solo `SUPER_ADMIN`/`ADMIN`, y no hay rutas de escritura).
4. Día local vs. UTC en `visits-by-day`.
5. Datos oficiales: sucursales, tipos y motivos (se cargan con `scripts.load_reference_data`; el repositorio solo incluye una plantilla de ejemplo).
