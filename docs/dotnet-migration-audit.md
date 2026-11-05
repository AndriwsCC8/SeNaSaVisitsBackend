# Auditoría técnica y plan de migración a .NET

**Proyecto:** SeNaSaVisitsBackend  
**Alcance:** Fase 0 — inspección y planificación, sin migración de código ni de datos  
**Fecha de auditoría:** 2026-11-05  
**Repositorio y rama inspeccionados:** `AndriwsCC8/SeNaSaVisitsBackend`, `main`

## 1. Resumen ejecutivo

El repositorio contiene una API FastAPI con funcionalidades sustanciales de autenticación, autorización, sucursales, usuarios, visitantes, visitas, auditoría, catálogos, dashboard y reportes. La inspección del código confirma **39 rutas de API bajo `/api` y una ruta raíz (`/`), para 40 endpoints definidos por la aplicación**. La metadata ORM y las revisiones de Alembic contienen las **15 entidades aprobadas**.

La suite se ejecutó en este entorno: **278 pruebas aprobadas, 0 fallidas**, en 6.60 segundos; pytest reportó 18 advertencias de dependencias/llaves de prueba. La infraestructura de pruebas usa SQLite en memoria y/o dobles de prueba. Esto **no valida comportamiento real de SQL Server**. No se conectó a la base de datos; se desconoce su revisión aplicada, datos y posible deriva respecto del esquema versionado.

La arquitectura real está organizada por carpetas de dominio, aplicación, infraestructura y API, pero no completa la inversión de dependencias que promete el README: los servicios de aplicación consultan directamente modelos SQLAlchemy y las carpetas de interfaces/repositorios de dominio e infraestructura no contienen implementaciones sustantivas. La migración puede establecer Clean Architecture de forma efectiva sin alterar reglas ni contratos.

Se encontró una contradicción funcional/documental importante: `normalize_identification` elimina espacios y convierte a mayúsculas, pero **conserva guiones**. Dos documentos indican eliminación de guiones. Asimismo, el informe antiguo de compatibilidad del frontend señala que la búsqueda por teléfono/correo no está protegida, mientras que el servicio actual y las pruebas sí restringen esa búsqueda con `VIEW_VISITOR_CONTACT`.

El único SDK .NET instalado detectado es **10.0.400** y no existe `global.json` en la raíz inspeccionada. Se recomienda evaluar **.NET 10 LTS** como destino inicial, sujeto a confirmar el estándar y ciclo de soporte institucional. La elección de versión y paquetes se debe cerrar antes de crear proyectos en la Fase 1.

**Conclusión:** el backend Python sirve como referencia funcional y contractual, pero no se deben inferir compatibilidad de SQL Server ni estado de producción a partir de las pruebas SQLite o de documentos históricos. La migración debe preservar las tablas y contratos, validar explícitamente SQL Server y mantener una sola implementación productiva al final.

## 2. Alcance, método y límites de verificación

Se inspeccionaron los archivos reales de `main.py`, `app/` (API, dependencias, servicios, DTO, validadores, core, sesión y modelos), las revisiones Alembic, las pruebas, `requirements.txt`, scripts y documentación existente. Se ejecutó la suite existente con el intérprete `.venv` seleccionado y se consultó la instalación local del SDK .NET.

No se inspeccionó el repositorio del frontend React; por ello la compatibilidad descrita se refiere a los contratos del backend/documentación y no a una comparación con pantallas o llamadas reales del cliente. No se leyeron secretos ni archivos `.env` con valores locales. No se ejecutó la aplicación, una migración, un seed, ni una consulta a SQL Server. La revisión de Alembic describe exclusivamente archivos del repositorio.

## 3. Arquitectura actual de Python

### 3.1 Inicio y configuración

- `main.py` crea FastAPI, instala CORS y manejadores globales de excepciones, registra el router API bajo el prefijo configurable (por defecto `/api`) y define `GET /`.
- `app/core/config.py` carga `Settings` desde `.env` y `.env.local`: nombre de servicio, entorno, prefijo API, `DATABASE_URL`, clave/algoritmo JWT, expiración, orígenes CORS y credenciales CORS. Rechaza `*` en CORS; advierte si la clave HS256 tiene menos de 32 caracteres y, en producción, impide ese valor.
- `app/infrastructure/database/session.py` configura SQLAlchemy; la configuración documentada usa SQL Server vía PyODBC. `migrations/env.py` obtiene conexión desde `Settings` y registra los modelos antes de exponer metadata a Alembic.
- `app/api/middleware/` no presenta middleware de aplicación sustantivo en el árbol inspeccionado. Los errores transversales se registran en `app/core/exceptions.py`.

### 3.2 Capas observadas y diferencia con el diseño declarado

| Zona | Responsabilidad real observada |
| --- | --- |
| `app/api` | Routers, dependencias de autenticación, autorización, acceso a sucursal, catálogos, reportes y dashboard; serialización por DTO de salida. |
| `app/application/dto` | Contratos Pydantic para peticiones y respuestas. |
| `app/application/services` | Casos de uso y reglas. En varios servicios se construyen consultas SQLAlchemy y se manipulan modelos ORM directamente. |
| `app/application/validators` | Normalización de visitantes, máscaras de identificación/contacto y validaciones asociadas. |
| `app/domain` | Solo estructura/paquetes; no se encontraron entidades, enums ni contratos de repositorio sustantivos. |
| `app/infrastructure/persistence/models` | Modelos ORM y registro de metadata; `database` contiene Base/sesión. |
| `app/infrastructure/repositories`, `services`, `authentication` y `app/application/interfaces` | Directorios presentes, sin implementaciones sustantivas que materialicen la separación descrita en README. |
| `app/core` | Configuración, seguridad transversal y excepciones. |

Por tanto, el sistema es una aplicación FastAPI/SQLAlchemy organizada por capas, **no una implementación completa de Clean Architecture con dominio independiente**. El README describe una arquitectura objetivo más desacoplada que la que implementa actualmente el código.

### 3.3 Dependencias actuales

Versiones fijadas en `requirements.txt`:

| Paquete | Versión |
| --- | ---: |
| FastAPI | 0.141.1 |
| Uvicorn `[standard]` | 0.52.4 |
| SQLAlchemy | 2.0.52 |
| Alembic | 1.20.0 |
| Pydantic | 2.13.5 |
| pydantic-settings | 2.15.0 |
| PyODBC | 5.3.0 |
| PyJWT | 2.14.0 |
| pwdlib `[argon2]` | 0.3.1 |
| python-multipart | 0.0.32 |
| python-dotenv | 1.2.3 |
| pytest | 9.1.1 |
| httpx | 0.28.1 |

Las advertencias de la ejecución actual incluyen deprecaciones de Starlette/httpx y advertencias de longitud de claves HMAC cortas **en algunos tests**; no son fallos de la suite. No se propone cambiar dependencias Python durante esta fase.

## 4. Inventario de funcionalidades

| Funcionalidad | Estado comprobado | Observaciones de implementación y límite |
| --- | --- | --- |
| Login | Implementada | `POST /api/auth/login`; credenciales no distinguen usuario inexistente, inactivo o contraseña incorrecta. Registra evento `LOGIN`; responde 503 ante fallo de base según contrato/código. |
| Usuario autenticado | Implementada | `GET /api/auth/me`; devuelve usuario, primer rol activo y sucursal solo cuando existe exactamente una asignación vigente a sucursal activa. |
| JWT | Implementada | Bearer, HS256 por defecto, claims `sub`, `type=access`, `iat`, `exp`; duración configurable (30 min por defecto). Cada petición revalida que el usuario exista y esté activo. Hay helper de refresh token, pero no rutas refresh/logout ni almacenamiento/rotación de refresh. |
| Hash de contraseñas | Implementada, compatibilidad .NET pendiente de prueba | `pwdlib` con `PasswordHash.recommended()` y Argon2. No se debe cambiar ni migrar hashes existentes sin demostrar verificación de los hashes reales; estos no se inspeccionaron. |
| Permisos | Implementada | Consulta permisos persistidos y no confía en claims del cliente. Permiso y usuario deben estar activos. `DENY` explícito prevalece sobre `ALLOW`; si no hay efecto explícito aplican roles. |
| Permisos `BRANCH` / `GLOBAL` | Implementada | Los globales rechazan `branch_id`; los de sucursal requieren una sucursal explícita y activa, más asignación vigente en esa sucursal. |
| Catálogo y asignación de permisos | Parcial | El catálogo declara 17 permisos y cuatro roles desde scripts. No hay API para administrar permisos de usuario ni grants `RolePermission`; no se halló gestión de roles completa. La materialización se ejecuta por scripts fuera de esta auditoría. |
| Asignaciones y transferencias | Implementada | Historial, vigencias `[valid_from, valid_until)`, estados y prevención de solapes. La transferencia serializa el tramo consultado con `UPDLOCK, HOLDLOCK` en SQL Server. La creación usa `with_for_update()`; su comportamiento debe comprobarse en SQL Server. |
| Usuarios | Implementada con límites | Listado/detalle/alta/edición, activación/desactivación, roles activos e historial/asignación/traslado. No hay endpoint para cambiar contraseña ni username. |
| Visitantes | Implementada | Perfil global sin `branch_id`; las operaciones requieren autorización de sucursal, pero el perfil no queda particionado por sucursal. No existe borrado físico; activación lógica. |
| Privacidad de visitantes | Implementada | Identificación enmascarada en respuestas; teléfono/correo completos solo con `VIEW_VISITOR_CONTACT`. Enmascaramiento aplica a listados y respuestas de operaciones. La búsqueda por teléfono/correo también requiere el permiso; los tests lo afirman. |
| Normalización de identificación | Implementada, requisito documental contradictorio | Quita espacios y convierte a mayúscula. **No elimina guiones.** `identification_normalized` se calcula del lado servidor y no se acepta ni expone en DTO. La búsqueda usa el término entregado; no aplica la misma normalización automáticamente. |
| Visitas | Implementada | Alta, listado, detalle, actualización de campos permitidos, completar y cancelar. Estados `ACTIVE`, `COMPLETED`, `CANCELLED`; transiciones solo desde `ACTIVE`. |
| Aislamiento de visitas | Implementado | El contexto deriva de la única asignación vigente del usuario y cada consulta/actualización filtra por `Visit.branch_id`. Una visita ajena se trata como no encontrada. El cliente no proporciona autoridad de sucursal ni registrador al crear. |
| Auditoría | Implementada parcialmente | Escritura desde casos de uso definidos; endpoint de consulta global; saneamiento de valores sensibles. No hay endpoint de escritura/edición/borrado. No todos los eventos CRUD imaginables se registran. |
| Catálogos | Parcial | Lectura de sucursales, tipos de sucursal, tipos de visitante, motivos y roles. No hay API de escritura; se cargan mediante scripts. |
| Dashboard | Implementado | Cuatro consultas agregadas; `VIEW_GLOBAL_REPORTS` da alcance global; de lo contrario `VIEW_REPORTS` limita a la sucursal actual. Serie diaria se agrupa por día UTC. |
| Reportes | Implementado | Detalle paginado y agregación por estado, motivo, usuario o sucursal. El grupo por sucursal requiere alcance global. No hay exportación CSV/Excel/PDF. |
| Notificaciones | Pendiente funcionalmente | Existe entidad `Notification`, pero no se encontraron rutas ni servicio/ciclo de creación, lectura o envío. |
| Manejo global de excepciones | Implementado | Errores de negocio se convierten en respuesta `detail`; fallo inesperado se oculta en 500 genérico. Validación FastAPI/Pydantic responde 422 con estructura propia, distinta del error funcional. |
| CORS y OpenAPI | Implementados | CORS usa lista explícita, no wildcard; permite métodos GET/POST/PUT/PATCH/DELETE/OPTIONS y headers Authorization/Content-Type. FastAPI publica Swagger y ReDoc. |
| JCE, Entra ID y mensajería | Pendiente/no implementado | No hay validación de identidad JCE, integración Microsoft Entra ID ni correo. Son futuros/decisiones, no contrato actual. |

### 4.1 Permisos definidos en código

Se encontraron estos códigos y alcances. Deben conservarse literalmente al migrar:

- `BRANCH`: `VIEW_VISITS`, `CREATE_VISIT`, `UPDATE_VISIT`, `DELETE_VISIT`, `VIEW_VISITORS`, `CREATE_VISITOR`, `UPDATE_VISITOR`, `VIEW_VISITOR_CONTACT`, `VIEW_REPORTS`.
- `GLOBAL`: `MANAGE_USERS`, `ASSIGN_USER_BRANCH`, `MOVE_USER_BRANCH`, `VIEW_GLOBAL_REPORTS`, `VIEW_AUDIT_LOGS`, `MANAGE_BRANCHES`, `MANAGE_VISITOR_TYPES`, `MANAGE_VISIT_REASONS`.

Los roles predefinidos son `SUPER_ADMIN`, `ADMIN`, `RECEPTIONIST` y `USER`. `SUPER_ADMIN` y `ADMIN` reciben el catálogo completo según el script. `RECEPTIONIST` recibe `VIEW_VISITS`, `CREATE_VISIT`, `VIEW_VISITORS`, `CREATE_VISITOR`, `UPDATE_VISITOR`; `USER` recibe `VIEW_VISITS`, `VIEW_VISITORS`. Por lo tanto, esos dos roles no reciben por defecto `UPDATE_VISIT`, `VIEW_REPORTS` ni `VIEW_VISITOR_CONTACT`. `DELETE_VISIT` está en catálogo sin ruta que lo use.

## 5. Inventario de endpoints actuales

El prefijo configurado por defecto es `/api`; se puede cambiar mediante configuración. Las rutas siguientes corresponden a declaraciones reales en `main.py` y `app/api/routes/`. Se cuentan solo rutas definidas por la aplicación: no se incluyen `/docs`, `/redoc` ni `/openapi.json` que proporciona FastAPI.

**Convenciones HTTP:** si una ruta no indica otro resultado exitoso, devuelve `200`. Errores transversales aplicables cuando corresponda: `401` sin identidad válida, `403` sin permiso/alcance, `404` recurso ausente o fuera del ámbito, `409` conflicto, `422` validación. Los endpoints POST indicados como alta responden `201`. Los errores de validación propios de FastAPI/Pydantic pueden tener lista en `detail`, mientras los errores funcionales suelen usar cadena `detail`.

### 5.1 Raíz, salud y autenticación

| Método y ruta | Parámetros / DTO entrada → salida | HTTP | Permiso y alcance / comportamiento |
| --- | --- | --- | --- |
| `GET /` | Sin parámetros ni DTO → objeto `{service, docs}` | 200 | Público. Nombre y ruta Swagger. |
| `GET /api/health` | Sin parámetros → estado/servicio | 200 | Público; prueba de salud sin comprobar conexión DB. |
| `GET /api/health/db` | Sin parámetros → estado de salud DB | 200, 503 | Público; ejecuta `SELECT 1` cuando se invoca. No se invocó durante auditoría. |
| `POST /api/auth/login` | `LoginRequest` (`username`, `password`) → `LoginResponse` con `access_token`, `token_type`, `user` | 200, 401, 503 | Público. JWT de acceso; error genérico para credenciales inválidas, 503 ante fallo de base. Registra login exitoso. |
| `GET /api/auth/me` | Bearer → `AuthenticatedUserResponse` | 200, 401 | Identidad autenticada. No enumera permisos. |
| `GET /api/auth/permissions/{permission_code}` | Path `permission_code`; query opcional `branch_id` → `{permission, allowed}` | 200, 401 | Bearer. Diagnóstico de permiso; no concede acceso. Los permisos GLOBAL requieren omitir `branch_id`; BRANCH requiere sucursal de asignación. |

### 5.2 Catálogos

| Método y ruta | Parámetros / DTO entrada → salida | HTTP | Permiso y alcance / comportamiento |
| --- | --- | --- | --- |
| `GET /api/branches` | Query `include_inactive` (por defecto false) → lista `BranchCatalogItem` | 200, 401, 403, 422 | Bearer. Permisos globales autorizados ven sucursales activas; permisos BRANCH elegibles ven solo su sucursal. Inactivas requieren `MANAGE_BRANCHES`. |
| `GET /api/branch-types` | Query `include_inactive` (por defecto false) → lista `BranchTypeCatalogItem` | 200, 401, 403, 422 | Requiere `MANAGE_BRANCHES` global. Solo lectura. |
| `GET /api/visitor-types` | Query `include_inactive` (por defecto false) → lista `VisitorTypeCatalogItem` | 200, 401, 403, 422 | Acceso de catálogo BRANCH o `MANAGE_VISITOR_TYPES` global; inactivas requieren permiso de gestión. |
| `GET /api/visit-reasons` | Query `include_inactive` (por defecto false) → lista `VisitReasonCatalogItem` | 200, 401, 403, 422 | Acceso BRANCH elegible o permiso global de gestión/reportes; inactivas requieren `MANAGE_VISIT_REASONS`. |
| `GET /api/roles` | Sin parámetros → lista `RoleResponse` | 200, 401, 403 | `MANAGE_USERS` global; solo roles activos. |

No existen endpoints de escritura para catálogos ni endpoint general `GET /api/permissions`. Los datos de referencia se cargan con script.

### 5.3 Usuarios y asignaciones

| Método y ruta | Parámetros / DTO entrada → salida | HTTP | Permiso y alcance / comportamiento |
| --- | --- | --- | --- |
| `GET /api/users` | Query `page`, `page_size`, `search`, `is_active`, `branch_id`, `role_code` → `UserListResponse` | 200, 401, 403, 422 | `MANAGE_USERS` global. `branch_id` filtra resultados; no delega autorización. Paginación por defecto 1/20, máximo 100. |
| `GET /api/users/{user_id}` | Path `user_id` → `UserResponse` | 200, 401, 403, 404 | `MANAGE_USERS` global. |
| `POST /api/users` | `UserCreate` → `UserResponse` | 201, 401, 403, 404, 409, 422 | `MANAGE_USERS`; además `ASSIGN_USER_BRANCH` si se solicita `branch_id`. Hash de contraseña nunca se devuelve. |
| `PATCH /api/users/{user_id}` | Path `user_id`, `UserUpdate` → `UserResponse` | 200, 401, 403, 404, 409, 422 | `MANAGE_USERS` global. No cambia username ni contraseña. |
| `POST /api/users/{user_id}/activate` | Path `user_id`, sin DTO → `UserResponse` | 200, 401, 403, 404, 422 | `MANAGE_USERS` global; activación lógica. |
| `POST /api/users/{user_id}/deactivate` | Path `user_id`, sin DTO → `UserResponse` | 200, 401, 403, 404, 422 | `MANAGE_USERS` global; desactivación lógica y marca temporal. |
| `GET /api/users/{user_id}/assignments` | Path `user_id` → lista `UserAssignmentResponse` | 200, 401, 403, 404, 422 | `MANAGE_USERS` global; historial, más reciente primero. |
| `POST /api/users/{user_id}/assignments` | Path `user_id`, `UserAssignmentCreate` → `UserAssignmentResponse` | 201, 401, 403, 404, 409, 422 | `ASSIGN_USER_BRANCH` global; valida sucursal/usuario, vigencia y solape. |
| `POST /api/users/{user_id}/transfer` | Path `user_id`, `UserTransferRequest` → `UserAssignmentResponse` | 200, 401, 403, 404, 409, 422 | `MOVE_USER_BRANCH` global; termina asignación anterior y crea la nueva en transacción. |
| `GET /api/users/{user_id}/roles` | Path `user_id` → lista `RoleResponse` | 200, 401, 403, 404, 422 | `MANAGE_USERS` global; devuelve roles activos. |

`UserCreate` requiere username, nombres y password; opcionalmente email, employee_code, role_code, branch_id y fecha de asignación. `UserUpdate` admite email, nombres, employee_code y role_code. La asignación acepta branch_id y fechas/motivo opcionales; transferencia acepta new_branch_id, effective_at y reason.

### 5.4 Visitantes

| Método y ruta | Parámetros / DTO entrada → salida | HTTP | Permiso y alcance / comportamiento |
| --- | --- | --- | --- |
| `GET /api/visitors` | Query `page`, `page_size`, `search`, `is_active`, `visitor_type_id` → `VisitorListResponse` | 200, 401, 403, 422 | `VIEW_VISITORS` en sucursal vigente; el perfil retornado es global. Paginación 1/20 por defecto, máximo 100. |
| `GET /api/visitors/{visitor_id}` | Path `visitor_id` → `VisitorResponse` | 200, 401, 403, 404, 422 | `VIEW_VISITORS` de sucursal. Identificación/contacto se enmascaran según permiso adicional. |
| `POST /api/visitors` | `VisitorCreate` → `VisitorResponse` | 201, 401, 403, 404, 409, 422 | `CREATE_VISITOR` de sucursal; valida tipo activo y unicidad de identificación normalizada. |
| `PATCH /api/visitors/{visitor_id}` | Path `visitor_id`, `VisitorUpdate` → `VisitorResponse` | 200, 401, 403, 404, 409, 422 | `UPDATE_VISITOR` de sucursal. |
| `POST /api/visitors/{visitor_id}/activate` | Path `visitor_id`, sin DTO → `VisitorResponse` | 200, 401, 403, 404, 422 | `UPDATE_VISITOR`; activación lógica. |
| `POST /api/visitors/{visitor_id}/deactivate` | Path `visitor_id`, sin DTO → `VisitorResponse` | 200, 401, 403, 404, 422 | `UPDATE_VISITOR`; desactivación lógica. |

`branch_id` no aparece como autoridad en estas rutas: el contexto se obtiene del usuario. La búsqueda por teléfono/email solo participa cuando `VIEW_VISITOR_CONTACT` está autorizado en la sucursal. No se devuelve `identification_normalized`.

### 5.5 Visitas

| Método y ruta | Parámetros / DTO entrada → salida | HTTP | Permiso y alcance / comportamiento |
| --- | --- | --- | --- |
| `GET /api/visits` | Query `page`, `page_size`, `status`, `visitor_id`, `reason_id`, `date_from`, `date_to`, `search` → `VisitListResponse` | 200, 401, 403, 422 | `VIEW_VISITS` en sucursal vigente; SQL limita por `branch_id`. Paginación 1/20, máximo 100. |
| `GET /api/visits/{visit_id}` | Path `visit_id` → `VisitResponse` | 200, 401, 403, 404, 422 | `VIEW_VISITS`; fuera de sucursal se informa 404. |
| `POST /api/visits` | `VisitCreate` → `VisitResponse` | 201, 401, 403, 404, 409, 422 | `CREATE_VISIT`; `branch_id`, registrador y estado se derivan en servidor. Visitante/motivo deben existir y estar activos. |
| `PATCH /api/visits/{visit_id}` | Path `visit_id`, `VisitUpdate` → `VisitResponse` | 200, 401, 403, 404, 409, 422 | `UPDATE_VISIT`; solo visitas activas y campos permitidos; sucursal acotada. |
| `POST /api/visits/{visit_id}/complete` | Path `visit_id`, `VisitCompleteRequest` → `VisitResponse` | 200, 401, 403, 404, 409, 422 | `UPDATE_VISIT`; solo `ACTIVE`; exit_at no puede preceder a entry_at. |
| `POST /api/visits/{visit_id}/cancel` | Path `visit_id`, `VisitCancelRequest` → `VisitResponse` | 200, 401, 403, 404, 409, 422 | `UPDATE_VISIT`; solo `ACTIVE`; cancellation_reason requerido. |

Rangos temporales: `date_from` inclusivo y `date_to` exclusivo. No hay eliminación física ni vuelta a `ACTIVE`.

### 5.6 Auditoría, dashboard y reportes

| Método y ruta | Parámetros / DTO entrada → salida | HTTP | Permiso y alcance / comportamiento |
| --- | --- | --- | --- |
| `GET /api/audit-logs` | Query `page`, `page_size`, `actor_user_id`, `action`, `entity_type`, `entity_id`, `branch_id`, `date_from`, `date_to` → `AuditLogListResponse` | 200, 401, 403, 422 | `VIEW_AUDIT_LOGS` global; `branch_id` es filtro. Orden descendente por tiempo/id; page_size 50 por defecto. Solo lectura. |
| `GET /api/dashboard/summary` | Query opcionales `date_from`, `date_to` → `DashboardSummaryResponse` | 200, 401, 403, 422 | `VIEW_GLOBAL_REPORTS` global o `VIEW_REPORTS` en sucursal vigente. No acepta branch_id como autoridad. |
| `GET /api/dashboard/visits-by-day` | Query opcionales `date_from`, `date_to` → `DashboardDaySeriesResponse` | 200, 401, 403, 422 | Mismo alcance; agrupa por fecha UTC. |
| `GET /api/dashboard/visits-by-status` | Query opcionales `date_from`, `date_to` → `DashboardDistributionResponse` | 200, 401, 403, 422 | Mismo alcance; agregación SQL por estado. |
| `GET /api/dashboard/visits-by-reason` | Query opcionales `date_from`, `date_to` → `DashboardDistributionResponse` | 200, 401, 403, 422 | Mismo alcance; agregación SQL por motivo. |
| `GET /api/reports/visits` | Query `page`, `page_size`, fechas, `status`, `reason_id`, `visitor_id`, `registered_by_user_id`, `branch_id`, `search` → `VisitReportResponse` | 200, 401, 403, 404, 422 | Global: `VIEW_GLOBAL_REPORTS` y branch_id opcional como filtro; branch: `VIEW_REPORTS` solo sucursal actual. Page_size 25 por defecto; no incluye datos de contacto. |
| `GET /api/reports/visits/summary` | Mismos filtros y `group_by` obligatorio (`status`, `reason`, `registered_by`, `branch`) → `VisitReportSummaryResponse` | 200, 401, 403, 404, 422 | Mismo alcance; `group_by=branch` requiere global. |

## 6. Base de datos, entidades y relaciones

### 6.1 Convenciones ORM/SQL Server observadas

Hay exactamente 15 tablas aprobadas en el registro ORM y la migración inicial. Todas las PK usan `BIGINT IDENTITY`; las FK declaradas especifican `ON DELETE NO ACTION`. `Boolean` representa `BIT`; timestamps SQL Server usan `DATETIME2(3)`; mixin común agrega `created_at` y `updated_at` no nulos, con default UTC de servidor `SYSUTCDATETIME()` y actualización ORM para `updated_at`. Los tipos de texto declarados son `NVARCHAR`/`VARCHAR` según el campo.

La metadata no fija collation; unicidad de username, email, códigos e identificación dependerá de collation de la base SQL Server de destino. Las restricciones filtradas usan `mssql_where`. SQLite de pruebas no reproduce todas estas propiedades.

### 6.2 Entidades aprobadas

En la tabla, `id` significa `BIGINT IDENTITY NOT NULL PRIMARY KEY`. Salvo cuando se especifica otra cosa, las columnas no nullable son obligatorias y la tabla usa `TimestampMixin`.

| Entidad / tabla | Columnas, nulabilidad, claves, relaciones e índices/restricciones |
| --- | --- |
| `BranchType` / `branch_types` | `id`; `code NVARCHAR(30)` requerido y único; `name NVARCHAR(100)` requerido; `description NVARCHAR(500)` nullable; `is_active BIT` requerido, default 1; `created_at`, `updated_at`. Relación uno-a-muchos con `Branch`. |
| `Branch` / `branches` | `id`; `code NVARCHAR(30)` requerido y único; `name NVARCHAR(200)` requerido; `branch_type_id BIGINT` requerido FK a `branch_types.id`; `region NVARCHAR(100)`, `address NVARCHAR(300)`, `phone NVARCHAR(30)` nullable; `is_active BIT` requerido default 1; timestamps. Índice en `branch_type_id`. Relaciones con tipo, asignaciones, visitas, audit logs, notificaciones y permisos de usuario. |
| `User` / `users` | `id`; `username NVARCHAR(80)` requerido/único; `first_name`, `last_name NVARCHAR(100)` requeridos; `password_hash NVARCHAR(255)` requerido; `is_active BIT` requerido default 1; `email NVARCHAR(254)`, `employee_code NVARCHAR(50)`, `deactivated_at DATETIME2(3)` nullable; timestamps. Username único; índices únicos filtrados para email y employee_code no nulos. Relaciones con roles, permisos, asignaciones, visitas, auditoría y notificaciones. |
| `Role` / `roles` | `id`; `code NVARCHAR(50)` y `name NVARCHAR(100)` requeridos; `description NVARCHAR(500)` nullable; `is_active BIT` default 1; timestamps. Índice único `code`; relaciones con `UserRole`/`RolePermission`. |
| `UserRole` / `user_roles` | `id`; `user_id`, `role_id`, `assigned_by_user_id BIGINT` requeridos FK a `users`, `roles`, `users`; `assigned_at`, `created_at`, `updated_at DATETIME2(3)` default UTC; `revoked_at DATETIME2(3)` nullable; `is_active BIT` default 1. Índice único filtrado `(user_id, role_id)` donde activo. |
| `Permission` / `permissions` | `id`; `code NVARCHAR(80)`, `name NVARCHAR(120)`, `resource NVARCHAR(80)`, `action NVARCHAR(80)`, `scope NVARCHAR(20)` requeridos; `description NVARCHAR(500)` nullable; `is_active BIT` default 1; timestamps. `code` único; CHECK `scope IN ('BRANCH','GLOBAL')`. |
| `RolePermission` / `role_permissions` | `id`; `role_id`, `permission_id`, `assigned_by_user_id BIGINT` requeridos FK; `assigned_at DATETIME2(3)` default UTC; `is_active BIT` default 1. Índice único filtrado `(role_id, permission_id)` donde activo. |
| `UserPermission` / `user_permissions` | `id`; `user_id`, `permission_id`, `assigned_by_user_id BIGINT` requeridos FK; `branch_id BIGINT` nullable FK a sucursal; `effect NVARCHAR(10)` requerido; `valid_from DATETIME2(3)` requerido; `valid_until DATETIME2(3)` nullable; `is_active BIT` default 1; `created_at DATETIME2(3)` default UTC. CHECK `effect IN ('ALLOW','DENY')` y fin posterior al inicio. Índice `(user_id, branch_id, permission_id, valid_from, valid_until)`. |
| `UserBranchAssignment` / `user_branch_assignments` | `id`; `user_id`, `branch_id`, `assigned_by_user_id BIGINT` requeridos FK; `valid_from DATETIME2(3)` requerido; `valid_until DATETIME2(3)` nullable; `status NVARCHAR(30)` requerido; `reason NVARCHAR(500)` nullable; `created_at`, `updated_at DATETIME2(3)` default UTC. CHECK fin > inicio; estados permitidos ACTIVE, ENDED y CANCELLED; ACTIVE requiere fin null y estados terminados requieren fin no null. Índice único filtrado de usuario con `valid_until IS NULL AND status='ACTIVE'`; índices `(branch_id, valid_from, valid_until)` y `(user_id, valid_from, valid_until)`. |
| `VisitorType` / `visitor_types` | `id`; `code NVARCHAR(50)`, `name NVARCHAR(100)` requeridos; `description NVARCHAR(500)` nullable; `is_active BIT` default 1; timestamps. Índice único `code`; relación uno-a-muchos con visitantes. |
| `Visitor` / `visitors` | `id`; `identification NVARCHAR(50)` nullable; `identification_normalized NVARCHAR(50)` nullable; `first_name`, `last_name NVARCHAR(100)` requeridos; `phone NVARCHAR(30)`, `email NVARCHAR(254)`, `company NVARCHAR(200)` nullable; `visitor_type_id BIGINT` nullable FK a `visitor_types.id`; `is_active BIT` default 1; timestamps. Índice único filtrado `identification_normalized` donde no es null. Sin FK de sucursal; relación a tipo y visitas. |
| `VisitReason` / `visit_reasons` | `id`; `code NVARCHAR(50)`, `name NVARCHAR(120)` requeridos; `description NVARCHAR(500)` nullable; `is_active BIT` default 1; timestamps. Índice único `code`; relación uno-a-muchos con visitas. |
| `Visit` / `visits` | `id`; `visitor_id`, `branch_id`, `registered_by_user_id`, `reason_id BIGINT` requeridos FK; `entry_at DATETIME2(3)` y `status NVARCHAR(30)` requeridos; `exit_at DATETIME2(3)`, `destination NVARCHAR(200)`, `visited_person NVARCHAR(200)`, `notes NVARCHAR(1000)`, `completed_by_user_id BIGINT`, `cancelled_by_user_id BIGINT`, `cancelled_at DATETIME2(3)`, `cancellation_reason NVARCHAR(500)` nullable; timestamps. CHECK estados ACTIVE, COMPLETED y CANCELLED; salida no anterior a entrada, datos de cancelación requeridos al cancelar. Índices `(branch_id,status,entry_at)`, `(branch_id,entry_at)`, `(visitor_id,entry_at)`. Relaciones a visitante, sucursal, motivo y usuarios participantes. |
| `AuditLog` / `audit_logs` | `id`; `actor_user_id BIGINT` y `branch_id BIGINT` nullable FK; `entity_id BIGINT` nullable; `action NVARCHAR(60)`, `entity_type NVARCHAR(80)` requeridos; `old_values`, `new_values NVARCHAR(MAX)` nullable; `ip_address VARCHAR(45)`, `user_agent NVARCHAR(500)`, `correlation_id NVARCHAR(100)` nullable; `created_at DATETIME2(3)` requerido default UTC. Índices `created_at`, `(actor_user_id, created_at)`, `(entity_type, entity_id, created_at)`, `(branch_id, created_at)`. No mixin `updated_at`. |
| `Notification` / `notifications` | `id`; `user_id BIGINT` requerido FK; `branch_id BIGINT` nullable FK; `title NVARCHAR(200)`, `message NVARCHAR(1000)`, `type NVARCHAR(50)` requeridos; `is_read BIT` requerido default 0; `read_at DATETIME2(3)`, `related_entity_type NVARCHAR(80)`, `related_entity_id BIGINT` nullable; `created_at DATETIME2(3)` requerido default UTC. CHECK consistencia leído/no leído con `read_at`; índice `(user_id,is_read,created_at)`. No mixin `updated_at`. |

### 6.3 Identificación y concurrencia

- El índice único filtrado de visitantes impide identificaciones normalizadas duplicadas solo cuando el valor no es `NULL`; visitantes sin identificación pueden repetirse. Confirmar que el DDL real del servidor coincide con la revisión y collation destino.
- El valor normalizado se genera en servicio. El algoritmo actual quita todos los espacios y convierte a mayúscula; conserva guion, puntos y otros signos. Cambiarlo en .NET sin acuerdo puede causar duplicados, conflictos o búsquedas incompatibles.
- `transfer_user` usa la pista SQL Server `WITH (UPDLOCK, HOLDLOCK)` en consulta de asignaciones y maneja la operación en transacción. `create_assignment` usa `with_for_update()` de SQLAlchemy; no se afirma que el equivalente SQLite garantice exclusión. Hay que diseñar la semántica EF Core y probar carreras con SQL Server real.
- No se fija explícitamente collation. La comparación de mayúsculas/minúsculas y unicidad puede variar según la instancia/base SQL Server.

### 6.4 Alembic

- Revisión inicial `df98eb51ee34` (`down_revision=None`) crea las 15 tablas.
- Revisión actual del repositorio `276b94986df8`, descendiente de `df98eb51ee34`, corrige default de `notifications.created_at` para usar la expresión `SYSUTCDATETIME()` y no el literal `'SYSUTCDATETIME()'`.
- **Estado de archivos verificado:** la cabeza registrada en código es `276b94986df8`.
- **Estado de instancia no verificado:** no se ejecutó `alembic current`, `upgrade`, `check` ni conexión. No se sabe qué revisión está aplicada en SQL Server ni si hay drift.
- En la migración, Alembic importa `Base.metadata` con modelos actuales. Durante la transición debe definirse una única autoridad/proceso de cambios del esquema; no deben coexistir escrituras independientes de Alembic y EF Core Migrations sin coordinación.

## 7. Seguridad y reglas que deben preservarse

1. JWT es portador de identidad, no de permisos; se revalida usuario activo en cada petición. Mantener claims, algoritmo, expiración y respuestas del contrato o acordar cambios explícitos.
2. Precedencia efectiva: usuario/permisos inactivos deniegan; para una regla aplicable, `DENY` explícito prevalece sobre `ALLOW`; en ausencia de efecto explícito se evalúa grant vigente de rol. No cambiar orden al traducir consultas.
3. Los permisos GLOBAL requieren que no se envíe contexto de sucursal. Los BRANCH exigen sucursal activa y exactamente una asignación temporal vigente del usuario; el valor del cliente nunca concede acceso.
4. Los intervalos de asignación y permisos usan inicio inclusivo y fin exclusivo; validación de vigencia se realiza en UTC.
5. Transferencia conserva historia y termina la anterior en el instante efectivo; las visitas históricas conservan sucursal/registrador original.
6. Visitas se consultan por sucursal en la base de datos, no solo en memoria ni en frontend. Fuera de sucursal se responde 404.
7. Los datos de visitante y contacto se protegen también en listados y respuestas de mutación; autorización de búsqueda por teléfono/correo es independiente de `VIEW_VISITORS`.
8. DTOs no deben exponer `password_hash`, `identification_normalized`, ni contacto sin permiso. Auditoría redacta secretos, hashes, tokens, Authorization y datos sensibles.
9. CORS no usa `*`; JWT secret mínimo institucional y almacenamiento seguro de secretos deben definirse para el nuevo host.
10. Conservar respuesta 422 dual: error funcional `detail` textual y validación FastAPI `detail` estructurado, salvo cambio coordinado con el frontend.

## 8. Inventario de pruebas y cobertura

### 8.1 Resultado ejecutado en esta auditoría

**Comando lógico:** `pytest -q` en el entorno virtual Python seleccionado.  
**Resultado:** **278 passed, 0 failed, 18 warnings, 6.60 s**.  
Este total es la cantidad real de casos recogidos y ejecutados por pytest en esta corrida; supera el conteo estático de funciones porque puede incluir parametrización. No equivale a cobertura de línea ni certificación de producción.

Los warnings observados fueron deprecaciones de Starlette/httpx/AnyIO y advertencias PyJWT de clave HMAC corta en algunos tests. Conviene registrar/limpiar esos warnings en una tarea separada, sin alterar contrato de fase 0.

### 8.2 Matriz Python → cobertura de pruebas .NET

| Tema/regla actual | Evidencia Python principal | Reproducción requerida en .NET |
| --- | --- | --- |
| Login, hash, emisión/verificación JWT, usuario inactivo y claims | `test_auth.py`, `test_phase_a.py` | Unit tests JWT/configuración, vector de hash Argon2 heredado, integración API y códigos 401/503. |
| Precedencia DENY/ALLOW/rol, scopes y catálogos de permisos | `test_authorization.py`, `test_phase_a.py` | Matriz combinatoria de precedencia, expiración, permisos desactivados, rol/grant desactivado y scopes. |
| Asignación vigente, sucursal única, override cliente y transferencia | `test_branch_access.py`, `test_users.py`, `test_phase_a.py` | Unit tests fechas exactas/bordes; integración concurrente en SQL Server de alta/transferencia y constraint filtrado. |
| Alta/edición/activación de usuarios, roles, asignaciones | `test_users.py`, `test_bootstrap_first_admin.py` | Contratos DTO/status, conflictos únicos, transacciones/auditoría, política de bootstrap (sin ejecutar seeds en prod). |
| Normalización, unicidad y máscara de identificación | `test_visitors.py`, `test_phase_c.py` | Casos con espacios, mayúsculas, guiones y valor vacío; comprobar contrato real conserva guion antes de codificar. |
| Privacidad y búsqueda de contacto | `test_phase_e.py`, `test_visitors.py`, `test_phase_c.py` | Verificar respuestas para todas las operaciones y que la búsqueda sin permiso no filtra por contacto ni altera total. |
| CRUD lógico y filtros de visitante | `test_visitors.py`, `test_phase_e.py` | API contract tests, filtros/paginación/orden y duplicidad bajo collation SQL Server. |
| Creación, actualización y transición de visita; branch isolation | `test_visits.py`, `test_phase_a.py` | Contract tests y SQL Server integration para aislamiento, constraints y estados concurrentes. |
| Modelos, tipos, FK, restricciones, índices | `test_models.py` | DDL/model metadata tests + migración de base desechable SQL Server; SQLite no basta para filtros, tipos o locks. |
| Catálogos y permisos de inclusión inactiva | `test_phase_b.py` | Matriz de roles/alcance y SQL Server query integration. |
| Auditoría/redacción/consulta | `test_audit.py` | Prueba transaccional, contenido redactado, filtros/fechas y rol global; comprobar no exposición en otros DTO. |
| Dashboard y reportes | `test_dashboard.py`, `test_reports.py` | Fechas UTC, agregados, límites de sucursal y rendimiento/plan SQL Server. |
| Health, CORS y respuestas API | `test_health.py`, `test_cors.py`, pruebas OpenAPI dispersas | Pruebas API reales, preflight/orígenes y disponibilidad DB en ambiente de prueba controlado. |

El árbol incluye pruebas para auditoría, autenticación, autorización, acceso a sucursal, bootstrap primer administrador, CORS, dashboard, health, modelos, fases A/B/C/E, reportes, usuarios, visitantes y visitas. No hay archivo `test_phase_d.py` en la estructura observada.

### 8.3 SQLite frente a SQL Server

`tests/sqlite_support.py` crea SQLite en memoria con los modelos reales y adapta `BIGINT`/`DATETIME2` y función `SYSUTCDATETIME`. Es explícitamente una ayuda de test, no un motor SQL Server. `test_models.py` inspecciona metadata y compila parte de DDL con dialecto SQL Server, pero **compilar DDL no ejecuta ni valida** constraints, collation, defaults, índices filtrados o concurrencia contra instancia real.

Antes de retirar Python, una suite de integración .NET debe correr contra SQL Server aislado o una base de prueba aprobada, con migraciones controladas y fixtures sintéticos. Casos prioritarios: índice único filtrado para identificación, constraints `CHECK`, defaults UTC `DATETIME2(3)`, `NO ACTION`, `UPDLOCK/HOLDLOCK`, transacciones concurrentes y comportamiento de collation.

## 9. Arquitectura .NET propuesta

### 9.1 Versión y tecnologías

- **SDK visto instalado:** .NET SDK `10.0.400`, ruta detectada `C:\Program Files\dotnet\dotnet.exe`.
- **`global.json`:** no se encontró en la raíz del repositorio inspeccionada.
- **Recomendación inicial:** evaluar `net10.0` / .NET 10 LTS; es compatible con el SDK instalado y evita iniciar sobre .NET 8 cerca de su fecha de fin de soporte en el momento de esta auditoría. Confirmar formalmente versión soportada, política de parches y runtime de despliegue con Arquitectura/Infraestructura institucional antes de fijarla.
- ASP.NET Core Web API con controladores o Minimal APIs: escoger una estrategia única manteniendo los paths y verbos actuales. Para preservar contratos y respuestas documentadas, se recomienda controllers con DTOs explícitos/OpenAPI.
- EF Core SQL Server para mapeo de las tablas existentes, sin rediseñar entidades. SQL Server sigue siendo motor final.
- JWT Bearer mediante middleware oficial; no meter autorizaciones solo en atributos si la regla DENY/ALLOW/rol y alcance depende de datos vigentes. Encapsular evaluación en servicio/policy propio.
- Argon2 compatible con hashes `pwdlib` existente: dependencia por seleccionar tras prueba de interoperabilidad. Implementar una interfaz de hash y un test de verificación con hashes sintéticos generados en Python y .NET; confirmar compatibilidad PHC/Argon2id y parámetros antes de producir datos reales. Rehash opcional solo tras autenticación exitosa y con decisión operativa.
- FluentValidation es opcional; puede centralizar reglas de DTO, pero no debe duplicar ni sustituir reglas transaccionales de dominio. También se puede mantener validación con atributos/servicios. Decisión de paquete y licencia institucional pendiente.
- Swagger/OpenAPI con esquema Bearer y contratos/códigos explícitos. Verificar naming JSON `snake_case`, fechas UTC con `Z` y formato de errores.
- xUnit para pruebas unitarias/API; pruebas de integración con SQL Server no reemplazables por SQLite si se validan características específicas del servidor.

### 9.2 Responsabilidades y dependencias

| Proyecto propuesto | Responsabilidad | Dependencias permitidas sugeridas |
| --- | --- | --- |
| `SeNaSaVisits.Domain` | Entidades/reglas puras, valores, estados, permisos/códigos y contratos de negocio. Sin EF Core, ASP.NET ni proveedor SQL. | BCL. |
| `SeNaSaVisits.Application` | Casos de uso, DTOs/contratos, validación y autorización de aplicación; interfaces para persistencia, reloj, hashing/token si aplica. | Domain. |
| `SeNaSaVisits.Infrastructure` | `DbContext`, mapeos EF a esquema ya aprobado, repositorios/adaptadores, Argon2, servicios externos y transacciones/consultas SQL Server específicas. | Application y Domain; EF Core SQL Server. |
| `SeNaSaVisits.API` | Host ASP.NET Core, controladores/routers, DI, JWT Bearer, CORS, filtros/middleware de excepciones y OpenAPI. | Application e Infrastructure en composition root. |
| `SeNaSaVisits.*.Tests` | Unitarias de Domain/Application y pruebas API/infraestructura. | xUnit; proveedor SQL Server aprobado para integration tests. |

La dirección de dependencias debe apuntar hacia Domain/Application; API compone Infrastructure y Application, pero casos de uso no deben importar DbContext ni ASP.NET.

### 9.3 Estructura objetivo en el mismo repositorio

No se crea esta estructura en Fase 0; es una propuesta para Fase 1:

```text
dotnet/
  SeNaSaVisits.sln
  src/
    SeNaSaVisits.Domain/
    SeNaSaVisits.Application/
    SeNaSaVisits.Infrastructure/
    SeNaSaVisits.API/
  tests/
    SeNaSaVisits.Domain.Tests/
    SeNaSaVisits.Application.Tests/
    SeNaSaVisits.API.Tests/
    SeNaSaVisits.Infrastructure.IntegrationTests/
```

La raíz conserva temporalmente `main.py`, `app/`, `migrations/`, `requirements.txt` y `tests/` Python como referencia verificable. La solución `.NET` se separa bajo `dotnet/` para evitar colisiones con `tests/` y `app/` actuales.

## 10. Estrategia de migración progresiva

1. **Fase 0 — auditoría (esta entrega):** fijar inventario, riesgos, contratos y decisiones. Sin cambios de aplicación.
2. **Fase 1 — acuerdos y línea base .NET:** confirmar versión LTS/políticas, biblioteca Argon2 y propietario de migraciones; acordar formato JSON/error/fechas; crear solución y CI en cambios futuros. Sin tocar esquema productivo.
3. **Fase 2 — persistencia compatible:** mapear las 15 tablas y restricciones existentes con EF Core; comparar DDL con migraciones/modelos; desarrollar integración con SQL Server descartable. No generar cambios de esquema automáticamente al arrancar.
4. **Fase 3 — identidad/autorización:** verificar hashes Argon2 existentes mediante fixture, mantener JWT compatible, `CurrentUser`, `DENY > ALLOW > RolePermission`, alcance global/sucursal y vigencia de asignaciones. Bloqueo de transferencia probado concurrentemente.
5. **Fase 4 — catálogos y administración:** roles, usuarios, alta/desactivación, historial, asignación/transferencia y auditoría con contratos iguales. Semillas no se ejecutan sin autorización y plan institucional.
6. **Fase 5 — visitantes:** DTO, normalización actual exacta, índice filtrado, privacidad de contacto y búsquedas. Decidir la discrepancia de guiones antes de cambiar algoritmo.
7. **Fase 6 — visitas:** CRUD permitido, transiciones, permisos, errores 404 de aislamiento y filtros/paginación equivalentes.
8. **Fase 7 — auditoría, dashboard y reportes:** mantener redacción, alcance y agregaciones; validar fecha UTC y día de `visits-by-day`.
9. **Fase 8 — paridad y validación:** contract tests de los 40 endpoints, prueba de regresión basada en los 278 casos actuales y pruebas SQL Server específicas. Ejecutar contra base aislada o ambiente de prueba autorizado; no usar SQLite como sustituto de locking/índices filtrados.
10. **Fase 9 — cutover gradual:** enrutar tráfico al .NET por API/segmentos con mecanismo reversible y monitoreo, cuidando que cada operación tenga un único escritor activo. Mantener Python temporalmente como referencia/fallback controlado, no como segundo escritor independiente.
11. **Fase 10 — retiro:** cuando todos los endpoints y flujos estén en .NET, con observabilidad y aceptación institucional, retirar Python productivo y formalizar .NET como única implementación. Archivar/eliminar Python solo con aprobación y fuera de esta Fase 0.

No se debe hacer doble escritura Python/.NET sobre la misma entidad durante la transición. Definir coordinación de despliegues/esquema, compatibilidad de JWT y rollback antes del primer corte.

## 11. Riesgos técnicos y discrepancias

| Riesgo / contradicción | Consecuencia | Tratamiento propuesto |
| --- | --- | --- |
| Documentos de identificación dicen eliminar guiones; código actual los conserva | Cambiarlo altera deduplicación, búsqueda e índice único | Institución/product owner decide regla; conservar comportamiento actual hasta aprobar cambio y plan de datos. |
| Auditoría de compatibilidad frontend es antigua en búsqueda de contacto | Puede llevar a omitir control de privacidad | Dar prioridad al servicio actual y pruebas; revalidar con frontend real antes de cutover. |
| `docs/database-design.md` se describe como conceptual/sin modelos aunque estos existen | Documentación puede confundir diseño futuro con estado actual | Corregir documentos en una fase documental posterior aprobada; este informe registra el estado real. |
| README afirma separación Clean Architecture que no aparece en código | Riesgo de copiar acoplamientos o creer que existen repositorios/entidades independientes | Definir dependencias por proyecto en .NET, no traducir carpetas mecánicamente. |
| SQL Server no probado en corrida actual | Riesgo en filtros, tipos, defaults, locks, DDL, índices y collation | Integration tests contra SQL Server aprobado; no certificar con SQLite. |
| Estado real de DB/Alembic desconocido | Puede existir drift o revisión aplicada distinta | Consultar estado solo en fase futura con autorización y procedimiento operativo; nunca asumir. |
| Argon2 compatible no elegido/verificado | Bloqueo de login a usuarios existentes si cambia encoding/parámetros | Prueba interoperable con hash fixture; preservar encoding y migrar/rehashear solo con decisión. |
| .NET JSON defaults difieren de FastAPI | Frontend puede dejar de reconocer nombres de campo o `detail` | Configurar `snake_case`, nulls/enum/fechas y error envelope compatibles; comparar OpenAPI. |
| Diferencias de collation SQL Server | Unicidad/capitalización puede no coincidir con pruebas | Inspeccionar collation real con autorización; no cambiarla en esta migración sin aprobación. |
| Cambio de día UTC/local en dashboard | Métricas pueden diferir en reportes operacionales | Mantener día UTC inicialmente o aprobar formalmente semántica local. |
| Dos herramientas de migración/escritores | Drift, downtime o pérdida de datos | Una autoridad de esquema durante la transición y handoff formal a EF migrations al retirar Alembic. |
| Roles actuales no reciben permisos esperables para recepción | Usuario no puede completar/cancelar visitas ni ver reportes/contacto | Decisión institucional; no ampliar permisos como parte de portabilidad técnica. |
| Notificaciones modeladas, pero sin flujo | No es funcionalidad migrable equivalente todavía | Decidir si queda fuera del alcance inicial o se especifica como funcionalidad nueva. |
| No se inspeccionó el frontend real | Contratos documentados pueden no cubrir expectativas actuales del cliente | Obtener OpenAPI/llamadas reales del frontend antes de validar compatibilidad final. |

## 12. Decisiones institucional y dependencias por confirmar

1. Estándar de runtime .NET, política LTS, SO/hosting, imagen/base aprobada y ventana de soporte; validar .NET 10 LTS.
2. Estándar de autenticación futuro: mantener JWT HS256 compartido y gestión segura de secreto; eventual identidad corporativa/Entra ID no está implementada.
3. Biblioteca Argon2 aprobada y tratamiento/rehash de hashes actuales; probar formato real sin exponer hashes productivos.
4. Propietario de esquema durante convivencia: Alembic hasta retiro de Python y luego EF Core, u otra política acordada. Prohibir cambios automáticos de schema al iniciar API.
5. Catálogo oficial de sucursales, tipos y motivos, y quién puede modificarlos; hoy hay solo lectura en API y scripts de carga.
6. Concesión de `VIEW_VISITOR_CONTACT`, `UPDATE_VISIT` y `VIEW_REPORTS` a `RECEPTIONIST`/`USER`.
7. Regla institucional final de normalización de identificaciones (guiones/puntuación) y si se permite buscar sin normalizar input.
8. Día de negocio para series por día (UTC actual frente a `America/Santo_Domingo`).
9. Confirmar campos de visita adicionales excluidos hoy: citas/prerregistro, fotos/documentos/firma, vehículos/acompañantes, identificación institucional, duración, área/planta/equipos.
10. Confirmar respuesta de validación esperada y compatibilidad real con React para nombres JSON, errores, paginación y tokens.
11. Ambiente/base SQL Server de integración con datos sintéticos, política de acceso, backups y ventanas de prueba.
12. Decidir si notificaciones, cambio/reset de contraseña, refresh/logout, endpoints de permisos efectivos y exportaciones forman parte del alcance de migración o quedan fuera.

## 13. Funcionalidades pendientes o no expuestas por API

- Refresh/logout, cambio/recuperación de contraseña.
- Consulta de todos los permisos efectivos del usuario; gestión API de roles/grants/permisos directos.
- Ruta que use `DELETE_VISIT` (la visita no tiene borrado).
- Escritura de catálogos desde API.
- Notificaciones y envío/lectura de notificaciones.
- Exportación de reportes.
- Integraciones JCE/Entra ID/correo y frontend: no se comprobaron/implementaron en este backend.
- Datos operativos oficiales en el repositorio; plantilla de referencia es ejemplo y no debe usarse como dato institucional.
- Funciones de cita/pre-registro y campos de visita no existentes en el modelo.
- Confirmación de los permisos de recepción, normalización con guiones y día de negocio.
- Verificación de estado/datos reales de SQL Server.

## 14. Lista de verificaciones para iniciar la Fase 1

- [ ] Aprobación institucional de target framework/runtime y estrategia de soporte; confirmar .NET 10 LTS.
- [ ] Acordar estructura de solución bajo `dotnet/` dentro de este mismo repositorio.
- [ ] Definir política de propiedad/versionado del esquema y convivencia Alembic/EF Core.
- [ ] Obtener DDL/metadata y revisión Alembic de un ambiente SQL Server de prueba autorizado; comparar con los 15 modelos sin modificar producción.
- [ ] Confirmar collation, schema/owner, versión SQL Server y driver/credenciales administradas fuera del repositorio.
- [ ] Crear fixtures no sensibles que prueben verificación mutua de hashes Argon2 de formato compatible.
- [ ] Congelar contratos de API y OpenAPI: 40 endpoints, snake_case, status codes, errores, fechas UTC `Z`, paginación y Bearer.
- [ ] Decidir explícitamente normalización de identificación y permisos de roles; no inferirlos en implementación.
- [ ] Diseñar políticas de autorización con precedencia DENY/ALLOW/rol y contexto BRANCH/GLOBAL, incluyendo pruebas de regresión.
- [ ] Diseñar pruebas concurrentes SQL Server de asignación/transferencia y pruebas de índices filtrados/constraints.
- [ ] Preparar pruebas xUnit unitarias, API contract y SQL Server integration; mapear las 278 pruebas actuales a escenarios verificables.
- [ ] Confirmar frontend React/base URL y consumidor de campos/errores mediante inspección del repositorio correspondiente.
- [ ] Definir despliegue gradual, observabilidad, rollback, único escritor y criterios de aceptación/retiro de Python.
- [ ] Mantener Python como referencia temporal; no borrar ni modificarlo hasta completar migración y aceptación.

## 15. Referencias inspeccionadas

- Inicio/configuración: `main.py`, `app/core/config.py`, `app/core/security.py`, `app/core/exceptions.py`.
- Autorización/acceso: `app/application/services/authorization.py`, `app/application/services/branch_access.py`, dependencias en `app/api/dependencies/`.
- Rutas/contratos: `app/api/routes/`, `app/application/dto/`, `docs/api-contract.md`.
- Modelos: `app/infrastructure/persistence/models/`.
- Alembic: `migrations/env.py`, `migrations/versions/df98eb51ee34_initial_schema.py`, `migrations/versions/276b94986df8_fix_notification_utc_default.py`.
- Pruebas: `tests/`, especialmente `tests/sqlite_support.py` y `tests/test_models.py`.
- Dependencias/scripts/documentos: `requirements.txt`, `scripts/`, `README.md`, `docs/backend-description.md`, `docs/database-design.md`, `docs/frontend-compatibility-audit.md`, `docs/visit-requirements-analysis.md`.

---

**Declaración de alcance:** esta entrega corresponde exclusivamente a auditoría y planificación. No se modificó código Python ni configuración del proyecto; no se creó ningún proyecto .NET ni archivo C#; no se ejecutaron migraciones, seeds o scripts de inicialización; no se conectó ni se realizaron escrituras en SQL Server.
**Fin de la auditoría de Fase 0.**