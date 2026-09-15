# Descripción completa del backend SeNaSa Visits

**Proyecto:** SeNaSa Visits Backend  
**Tecnología principal:** Python + FastAPI  
**Propósito:** API institucional para la gestión y el registro de visitas de SeNaSa  
**Estado documentado:** Fases 1 a 13 completadas para la base local `SeNaSaVisitsDB`; Notificaciones y citas/pre-registro siguen pendientes.

> Este documento describe el estado real del backend en el workspace actual. Distingue entre funcionalidades implementadas, infraestructura preparada y componentes que todavía no existen.

## 1. Qué es este proyecto

SeNaSa Visits Backend es una API REST independiente del frontend React/Vite. Su objetivo es soportar un sistema institucional para registrar visitantes y visitas en múltiples sucursales, centros y puntos de servicio de SeNaSa.

El backend fue diseñado para conservar información histórica y aplicar las reglas de seguridad en el servidor. La regla más importante es el aislamiento por sucursal:

> Un usuario asignado a una sucursal no puede consultar, crear, modificar ni eliminar información de otra sucursal, salvo que posea permisos globales explícitos.

La sucursal enviada por el frontend nunca debe ser considerada una fuente de autoridad. La autorización se basa en la identidad autenticada, sus permisos efectivos, sus asignaciones vigentes y la sucursal propietaria del recurso. El filtrado de recursos de visitas se implementará junto con sus endpoints de negocio.

## 2. Estado actual por fase

### Fase 1: arquitectura base

Completada parcialmente y funcionando:

- Aplicación FastAPI.
- Punto de entrada `main.py`.
- Configuración centralizada con Pydantic Settings.
- CORS.
- Manejo global de excepciones.
- Endpoint raíz.
- Endpoint de health check.
- Documentación Swagger y ReDoc.
- Configuración inicial de SQLAlchemy.
- Configuración inicial de Alembic.
- Utilidades de hashing y JWT preparadas para fases posteriores.
- Prueba básica de salud.

### Fase 2: diseño del modelo de negocio y base de datos

Completada en [docs/database-design.md](database-design.md).

El documento define:

- Entidades.
- Campos.
- Relaciones.
- Foreign keys.
- Índices.
- Constraints.
- Historial de asignaciones.
- Aislamiento por sucursal.
- Auditoría.
- Notificaciones.
- Fechas UTC.
- Reglas de eliminación.
- Decisiones de seguridad y concurrencia.

### Fase 3: modelos SQLAlchemy

Completada.

Existen 15 modelos ORM registrados en `Base.metadata`, con relaciones, foreign keys, índices y constraints de integridad básica.

### Fase 4: migración SQL Server

Completada para la base local `SeNaSaVisitsDB`.

Las revisiones `df98eb51ee34` y `276b94986df8` fueron aplicadas mediante Alembic. La base contiene las 15 tablas del modelo y la tabla técnica `alembic_version`. La segunda revisión corrige el default UTC de `Notification.created_at`. La conexión local utiliza autenticación integrada de Windows mediante Shared Memory (`lpc:localhost`) porque TCP/1433 no está habilitado en la instancia local.

### Fase 5: autenticación JWT

Completada.

Incluye login, `get_current_user`, Argon2, JWT, `/api/auth/me` y protección de usuarios inactivos.

### Fase 6: roles y permisos

Completada.

Incluye `PermissionService`, precedencia `DENY > ALLOW > RolePermission`, scopes `BRANCH/GLOBAL`, seeds manuales y `require_permission`.

### Fase 7: aislamiento por sucursal

Completada.

Incluye `BranchAccessService`, `get_current_branch`, `require_branch_permission` y consultas de visitas preparadas para filtrar por `Visit.branch_id` directamente en SQL.

### Fase 8: gestión de usuarios y asignaciones

Completada.

Incluye usuarios, roles, asignaciones, activación/desactivación, historial y transferencias con bloqueo `UPDLOCK/HOLDLOCK`.

### Fase 9: gestión de visitantes

Completada.

Incluye DTOs, normalización y máscara de identificación, búsqueda paginada en SQL, CRUD de perfiles de visitantes, VisitorType, activación/desactivación y permisos específicos.

### Fase 10: gestión de visitas

Completada.

Incluye listado paginado, detalle, creación, actualización de campos de negocio, completion, cancelación, validación de Visitor y VisitReason, transiciones de estado y aislamiento SQL por `Visit.BranchId`.

### Fase 11: auditoría

Completada.

Incluye `AuditService`, eventos administrativos y operativos redactados, LOGIN exitoso, consulta paginada con `VIEW_AUDIT_LOGS` y escritura append-only desde la aplicación.

### Fase 12: Dashboard

Completada.

Incluye summary, series diarias, distribuciones por estado y motivo, con acceso de sucursal o global según permisos.

### Fase 13: Reportes

Completada.

Incluye reporte detallado paginado y reporte agrupado por estado, motivo, usuario registrador o sucursal, sin exportaciones.

## 3. Estructura general del proyecto

```text
SeNaSaVisitsBackend/
├── alembic.ini
├── main.py
├── pytest.ini
├── README.md
├── requirements.txt
├── .env
├── .env.example
├── app/
│   ├── api/
│   ├── application/
│   ├── core/
│   ├── domain/
│   └── infrastructure/
├── docs/
│   ├── backend-description.md
│   └── database-design.md
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── README.md
└── tests/
  ├── test_health.py
  ├── test_models.py
  ├── test_auth.py
  ├── test_authorization.py
  ├── test_branch_access.py
  ├── test_users.py
  └── test_visitors.py
```

El entorno `.venv`, los directorios `__pycache__` y `.pytest_cache` son archivos generados localmente y no forman parte de la funcionalidad del backend.

## 4. Arquitectura

La estructura está inspirada en Clean Architecture y separa responsabilidades.

```text
app/
├── domain/
├── application/
├── infrastructure/
├── api/
```

### `domain`

Representa el dominio puro del negocio.

Actualmente contiene únicamente la estructura inicial:

```text
app/domain/
├── __init__.py
├── entities/
├── enums/
└── repositories/
```

No contiene modelos SQLAlchemy ni entidades de dominio implementadas. Esto es intencional: la capa de dominio no debe depender de SQLAlchemy.

No existen actualmente:

- Entidades de dominio Python.
- Enums de dominio funcionales.
- Interfaces de repositorio implementadas.
- Reglas de autorización de dominio.

### `application`

Representa la capa prevista para casos de uso y reglas de aplicación.

```text
app/application/
├── __init__.py
├── dto/
├── interfaces/
├── services/
└── validators/
```

Actualmente solo existe la estructura de carpetas. Todavía no hay:

- Casos de uso.
- DTOs funcionales.
- Servicios de negocio.
- Validadores de visitantes o visitas.
- Servicios de autorización.
- Interfaces de aplicación utilizadas por la API.

### `infrastructure`

Contiene la implementación técnica:

```text
app/infrastructure/
├── authentication/
├── database/
├── persistence/
├── repositories/
└── services/
```

Actualmente contiene funcionalmente:

- `Base` declarativa SQLAlchemy.
- Fábrica de sesiones SQLAlchemy.
- Engine configurado para SQL Server.
- Modelos ORM.
- Registro central de modelos.

Todavía no contiene:

- Repositorios concretos.
- Servicios de negocio.
- Servicios externos.
- Servicio de transferencia de usuarios.
- Servicio de autorización.
- Servicio de auditoría operativo.
- Servicio de notificaciones.

### `api`

Es la capa de entrada HTTP de FastAPI.

```text
app/api/
├── dependencies/
├── middleware/
└── routes/
```

Actualmente solo existe el endpoint de salud. Las carpetas de dependencias y middleware todavía no contienen implementaciones funcionales.

### `core`

Contiene funcionalidades transversales:

```text
app/core/
├── config.py
├── exceptions.py
└── security.py
```

Aquí se encuentran la configuración, los errores globales y las utilidades de seguridad preparadas.

## 5. Punto de entrada FastAPI

El punto de entrada es [main.py](../main.py).

La aplicación:

- Crea una instancia `FastAPI`.
- Usa el nombre de aplicación configurado.
- Declara la descripción de la API.
- Expone la versión `0.1.0`.
- Habilita Swagger en `/docs`.
- Habilita ReDoc en `/redoc`.
- Configura CORS.
- Registra los manejadores globales de excepciones.
- Registra el router principal bajo el prefijo `/api`.
- Expone el endpoint raíz `/`.

### Endpoint raíz

```http
GET /
```

Respuesta actual:

```json
{
  "service": "SeNaSa Visits API",
  "docs": "/docs"
}
```

### Health check

El endpoint está definido en [app/api/routes/health.py](../app/api/routes/health.py).

```http
GET /api/health
```

Respuesta esperada:

```json
{
  "status": "ok",
  "service": "SeNaSa Visits API"
}
```

Este endpoint confirma que la aplicación está funcionando. No verifica todavía la conexión con SQL Server.

## 6. Configuración

La configuración está definida en [app/core/config.py](../app/core/config.py) y utiliza `pydantic-settings`.

La aplicación carga valores desde `.env` y desde las variables de entorno del sistema.

Variables configuradas:

- `APP_NAME`.
- `ENVIRONMENT`.
- `API_V1_PREFIX`.
- `DATABASE_URL`.
- `JWT_SECRET_KEY`.
- `JWT_ALGORITHM`.
- `ACCESS_TOKEN_EXPIRE_MINUTES`.
- `REFRESH_TOKEN_EXPIRE_MINUTES`.
- `CORS_ORIGINS`.

Ambientes soportados:

- `development`.
- `production`.
- `testing`.

`get_settings()` utiliza caché para cargar una única instancia de configuración durante la ejecución del proceso.

### Configuración de base de datos

`DATABASE_URL` se obtiene desde `.env`. No está hardcodeada en el código ni en `alembic.ini`.

La URL configurada actualmente apunta conceptualmente a:

```text
SQL Server local
localhost:1433
base de datos SeNaSaVisitsDB
```

No se muestran aquí usuario, contraseña ni la URL real completa.

Durante la última verificación:

- `ODBC Driver 17 for SQL Server` era el driver solicitado por la configuración.
- En Windows estaba instalado `ODBC Driver 18 for SQL Server`.
- El driver 17 no pudo ser encontrado.
- El driver 18 fue detectado, pero `localhost:1433` no respondió.
- No se confirmó la existencia de la base de datos.

## 7. Conexión SQLAlchemy

La conexión se encuentra en [app/infrastructure/database/session.py](../app/infrastructure/database/session.py).

Incluye:

- `create_engine`.
- `pool_pre_ping=True`.
- `fast_executemany=True`.
- `SessionLocal`.
- Dependencia `get_db()`.
- Cierre de sesión después de cada request.

La conexión está preparada para SQL Server mediante PyODBC, pero no se ha aplicado todavía ninguna migración.

## 8. Modelos ORM implementados

Los modelos se encuentran en:

```text
app/infrastructure/persistence/models/
```

El módulo [app/infrastructure/persistence/models/__init__.py](../app/infrastructure/persistence/models/__init__.py) importa todas las entidades para que Alembic las registre en `Base.metadata`.

### 8.1 BranchType

Catálogo de tipos de ubicación.

Campos:

- `Id`.
- `Code`.
- `Name`.
- `Description`.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.

Permite registrar tipos como `SEDE`, `CENTRO_SERVICIO` y `PUNTO_SERVICIO` sin hardcodearlos en Python.

### 8.2 Branch

Representa una ubicación operativa de SeNaSa.

Campos:

- `Id`.
- `Code`.
- `Name`.
- `BranchTypeId`.
- `Region`.
- `Address`.
- `Phone`.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.

`Code` es único.

No existe `ParentBranchId` y no se ha implementado una jerarquía entre sedes, centros y puntos de servicio.

### 8.3 User

Representa a un usuario institucional.

Campos:

- `Id`.
- `Username`.
- `Email`.
- `FirstName`.
- `LastName`.
- `EmployeeCode`.
- `PasswordHash`.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.
- `DeactivatedAt`.

Restricciones:

- `Username` único.
- `Email` único cuando no sea `NULL`.
- `EmployeeCode` único cuando no sea `NULL`.
- `PasswordHash` obligatorio en el modelo actual.
- No se almacenan contraseñas planas.

El login utiliza este modelo, pero todavía no existe gestión funcional de usuarios mediante CRUD.

### 8.4 Role

Catálogo de roles globales.

Campos:

- `Id`.
- `Code`.
- `Name`.
- `Description`.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.

El modelo no utiliza `Name` como lógica de autorización.

### 8.5 UserRole

Tabla puente entre usuarios y roles.

Campos:

- `Id`.
- `UserId`.
- `RoleId`.
- `AssignedByUserId`.
- `AssignedAt`.
- `RevokedAt`.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.

Características:

- Relación muchos-a-muchos entre `User` y `Role`.
- El rol es global, no pertenece a una sucursal.
- Conserva historial de asignaciones.
- Impide duplicar una relación activa.

### 8.6 Permission

Catálogo de permisos.

Campos:

- `Id`.
- `Code`.
- `Name`.
- `Description`.
- `Resource`.
- `Action`.
- `Scope`.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.

`Scope` solo permite:

- `BRANCH`.
- `GLOBAL`.

Todavía no existe evaluación funcional de permisos.

### 8.7 RolePermission

Tabla puente entre roles y permisos.

Campos:

- `Id`.
- `RoleId`.
- `PermissionId`.
- `AssignedAt`.
- `AssignedByUserId`.
- `IsActive`.

Conserva la relación histórica e impide duplicar relaciones activas.

### 8.8 UserPermission

Representa permisos específicos o excepciones para un usuario.

Campos:

- `Id`.
- `UserId`.
- `PermissionId`.
- `BranchId` nullable.
- `Effect`.
- `ValidFrom`.
- `ValidUntil` nullable.
- `AssignedByUserId`.
- `IsActive`.
- `CreatedAt`.

`Effect` solo permite:

- `ALLOW`.
- `DENY`.

El modelo contiene constraints para el efecto y el intervalo de fechas. La validación entre `BranchId` y `Permission.Scope` deberá realizarse posteriormente en la aplicación, porque requiere consultar otra tabla.

### 8.9 UserBranchAssignment

Conserva la asignación histórica de usuarios a sucursales.

Campos:

- `Id`.
- `UserId`.
- `BranchId`.
- `ValidFrom`.
- `ValidUntil`.
- `AssignedByUserId`.
- `Reason`.
- `Status`.
- `CreatedAt`.
- `UpdatedAt`.

Estados permitidos:

- `ACTIVE`.
- `ENDED`.
- `CANCELLED`.

Características:

- Intervalos `[ValidFrom, ValidUntil)`.
- Índice único filtrado para una única asignación activa por usuario.
- Validación de fechas.
- Validación básica entre estado y fecha de finalización.
- Foreign keys a usuario, sucursal y usuario que realizó la asignación.

Todavía no existe el servicio de traslado ni el control transaccional `SERIALIZABLE`/`UPDLOCK`/`HOLDLOCK`.

### 8.10 Visitor

Representa a un visitante institucional.

Campos:

- `Id`.
- `Identification` nullable.
- `IdentificationNormalized` nullable.
- `FirstName`.
- `LastName`.
- `Phone` nullable.
- `Email` nullable.
- `Company` nullable.
- `VisitorTypeId` nullable.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.

La identificación normalizada tiene índice único filtrado cuando existe. Los visitantes sin identificación no se deduplican automáticamente.

### 8.11 VisitorType

Catálogo de tipos de visitante.

Campos:

- `Id`.
- `Code`.
- `Name`.
- `Description`.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.

### 8.12 Visit

Representa una visita real registrada en una sucursal.

Campos:

- `Id`.
- `VisitorId`.
- `BranchId`.
- `RegisteredByUserId`.
- `EntryAt`.
- `ExitAt` nullable.
- `ReasonId`.
- `Destination` nullable.
- `VisitedPerson` nullable.
- `Status`.
- `Notes` nullable.
- `CreatedAt`.
- `UpdatedAt`.
- `CompletedByUserId` nullable.
- `CancelledByUserId` nullable.
- `CancelledAt` nullable.
- `CancellationReason` nullable.

Estados permitidos:

- `ACTIVE`.
- `COMPLETED`.
- `CANCELLED`.

El modelo valida:

- `ExitAt` no puede ser anterior a `EntryAt`.
- Una visita cancelada debe tener información básica de cancelación.
- `BranchId` es obligatorio.

`BranchId` representa la sucursal histórica donde se registró la visita. No existe lógica ORM que lo cambie cuando el usuario sea trasladado.

### 8.13 VisitReason

Catálogo de motivos de visita.

Campos:

- `Id`.
- `Code`.
- `Name`.
- `Description`.
- `IsActive`.
- `CreatedAt`.
- `UpdatedAt`.

### 8.14 AuditLog

Representa eventos importantes del sistema.

Campos:

- `Id`.
- `ActorUserId` nullable.
- `Action`.
- `EntityType`.
- `EntityId` nullable.
- `BranchId` nullable.
- `OldValues` nullable como `NVARCHAR(MAX)`.
- `NewValues` nullable como `NVARCHAR(MAX)`.
- `IpAddress` nullable como `VARCHAR(45)`.
- `UserAgent` nullable.
- `CorrelationId` nullable.
- `CreatedAt`.

Incluye índices por fecha, actor, entidad y sucursal.

El modelo representa la entidad, pero todavía no existe el mecanismo operativo append-only ni el registro automático de acciones.

### 8.15 Notification

Representa una notificación dirigida a un usuario.

Campos:

- `Id`.
- `UserId`.
- `BranchId` nullable.
- `Title`.
- `Message`.
- `Type`.
- `IsRead`.
- `CreatedAt`.
- `ReadAt` nullable.
- `RelatedEntityType` nullable.
- `RelatedEntityId` nullable.

Existe un constraint para mantener coherencia entre `IsRead` y `ReadAt`.

Todavía no existe un servicio para generar, enviar o marcar notificaciones.

## 9. Tipos y persistencia SQL Server

Los modelos están preparados para SQL Server con:

- `BIGINT IDENTITY` para claves primarias.
- `NVARCHAR` con longitudes explícitas.
- `NVARCHAR(MAX)` para JSON de auditoría.
- `VARCHAR(45)` para IP.
- `BIT` para booleanos.
- `DATETIME2(3)` para timestamps.
- `SYSUTCDATETIME()` para defaults de fechas del servidor.
- Foreign keys con `ON DELETE NO ACTION`.
- Índices filtrados mediante `mssql_where`.

No se utilizan GUID ni UUID.

## 10. Relaciones implementadas

Las relaciones ORM principales son:

```text
BranchType 1 ─── N Branch

User N ─── N Role
       mediante UserRole

Role N ─── N Permission
          mediante RolePermission

User 1 ─── N UserPermission
Permission 1 ─── N UserPermission
Branch 1 ─── N UserPermission

User 1 ─── N UserBranchAssignment
Branch 1 ─── N UserBranchAssignment
User 1 ─── N UserBranchAssignment como AssignedByUser

VisitorType 1 ─── N Visitor
Visitor 1 ─── N Visit
Branch 1 ─── N Visit
VisitReason 1 ─── N Visit

User 1 ─── N Visit como RegisteredByUser
User 1 ─── N Visit como CompletedByUser
User 1 ─── N Visit como CancelledByUser

User 1 ─── N AuditLog
Branch 1 ─── N AuditLog

User 1 ─── N Notification
Branch 1 ─── N Notification
```

Las relaciones con múltiples foreign keys hacia `User` utilizan `foreign_keys` explícitos para evitar ambigüedades de SQLAlchemy.

## 11. Índices implementados

### Identidad y catálogos

- `User.Username` único.
- `User.Email` único filtrado cuando no es `NULL`.
- `User.EmployeeCode` único filtrado cuando no es `NULL`.
- `Branch.Code` único.
- Códigos únicos de roles, permisos y catálogos.

### Autorización y asignaciones

- Relación activa `UserRole(UserId, RoleId)`.
- Relación activa `RolePermission(RoleId, PermissionId)`.
- Búsqueda de `UserPermission`.
- Una sola asignación activa por usuario.
- `UserBranchAssignment(BranchId, ValidFrom, ValidUntil)`.
- `UserBranchAssignment(UserId, ValidFrom, ValidUntil)`.

### Visitantes y visitas

- `Visitor.IdentificationNormalized` único filtrado.
- `Visit(BranchId, Status, EntryAt)`.
- `Visit(BranchId, EntryAt)`.
- `Visit(VisitorId, EntryAt)`.

### Auditoría y notificaciones

- `AuditLog(CreatedAt)`.
- `AuditLog(ActorUserId, CreatedAt)`.
- `AuditLog(EntityType, EntityId, CreatedAt)`.
- `AuditLog(BranchId, CreatedAt)`.
- `Notification(UserId, IsRead, CreatedAt)`.

## 12. Constraints e integridad

Se implementaron constraints básicos para:

- `Permission.Scope` en `BRANCH` o `GLOBAL`.
- `UserPermission.Effect` en `ALLOW` o `DENY`.
- Fechas válidas de `UserPermission`.
- Estados válidos de `UserBranchAssignment`.
- Fechas válidas de `UserBranchAssignment`.
- Coherencia básica entre estado y `ValidUntil`.
- Estados válidos de `Visit`.
- `ExitAt >= EntryAt`.
- Coherencia básica de cancelación.
- Coherencia entre `Notification.IsRead` y `Notification.ReadAt`.

No se implementaron constraints que consulten otras tablas.

## 13. Autenticación implementada

La Fase 5 implementa autenticación local mediante:

- Argon2 con `pwdlib` para contraseñas.
- JWT firmado con `JWT_SECRET_KEY` y `JWT_ALGORITHM`.
- Claims mínimos: `sub`, `type`, `iat` y `exp`.
- Dependencia reutilizable `get_current_user`.
- Endpoint `POST /api/auth/login`.
- Endpoint protegido `GET /api/auth/me`.
- Esquema Bearer visible en Swagger.
- Respuestas sin `PasswordHash`.
- Mensaje genérico `Credenciales inválidas` para evitar enumeración.
- Rechazo de usuarios inactivos.
- Bootstrap manual idempotente mediante `python -m scripts.bootstrap_user`.

La identidad de `/api/auth/me` siempre proviene del JWT validado. No se acepta un `user_id` enviado por query string o body como fuente de identidad.

El JWT no contiene roles, permisos completos, sucursales, contraseñas ni datos personales innecesarios. La evaluación de permisos está implementada; el aislamiento completo de recursos por sucursal queda para fases posteriores.

## 14. Autorización implementada

La Fase 6 implementa `PermissionService`, que evalúa permisos directamente mediante consultas filtradas a SQL Server. La evaluación considera usuario, código de permiso, sucursal e instante UTC.

La precedencia es:

```text
DENY explícito > ALLOW explícito > RolePermission activo > denegar
```

Reglas aplicadas:

- `UserRole` es global y no concede acceso físico por sí solo.
- `BRANCH` requiere `branch_id`, sucursal activa y `UserBranchAssignment` vigente.
- `GLOBAL` requiere que no se envíe `branch_id`.
- `UserPermission` global usa `BranchId = NULL`.
- `UserPermission` de sucursal usa la sucursal concreta.
- Un `ALLOW` no crea asignaciones ni amplía el alcance físico.
- Usuarios o permisos inactivos son rechazados.
- `DENY` gana incluso cuando existe un permiso heredado por rol.
- No existe bypass por código de rol, incluido `SUPER_ADMIN`.

La dependencia `require_permission("PERMISSION_CODE")` está preparada para proteger endpoints futuros. Lee el contexto de sucursal como dato de la solicitud, pero el servicio lo valida contra la base de datos; el cliente no puede conceder permisos enviando un código, rol o sucursal.

Existe un endpoint diagnóstico protegido:

```text
GET /api/auth/permissions/{permission_code}?branch_id=1
```

Devuelve únicamente el permiso solicitado y `allowed`. No otorga autorización y no sustituye los filtros de recursos que deberán implementarse en la siguiente fase.

Seeds manuales:

```powershell
python -m scripts.seed_permissions
python -m scripts.seed_roles
python -m scripts.seed_role_permissions --assigned-by-user-id <id>
```

Los dos primeros comandos ya fueron ejecutados sobre la base y crearon 14 permisos y 4 roles. El tercer comando no se ejecutó porque todavía no existe un usuario activo para `AssignedByUserId`; no se creó ningún usuario automáticamente.

## 15. Aislamiento por sucursal implementado

La Fase 7 añade:

- `BranchAccessService` para resolver la única asignación vigente.
- `BranchContext` con `user_id`, `branch_id` y `assignment_id` autorizados.
- `get_current_branch` para operaciones de sucursal.
- `require_branch_permission("PERMISSION_CODE")` para combinar contexto y permiso.
- `VisitAccessService` para construir consultas de visitas con `Visit.branch_id == contexto.branch_id` dentro de SQL.

La asignación vigente se determina con `Status = 'ACTIVE'`, `ValidFrom <= ahora` y `ValidUntil IS NULL OR ahora < ValidUntil`. El esquema aprobado no contiene `IsActive` en `UserBranchAssignment`; no se agregó una columna y se utiliza `Status` como estado persistido.

Comportamiento:

- Sin `branch_id` del cliente: se utiliza la sucursal autorizada del usuario.
- Con el mismo `branch_id`: se permite continuar.
- Con otro `branch_id`: se devuelve `403`; no se cambia el contexto.
- Sin asignación vigente: `403`.
- Asignación futura o expirada: `403`.
- Sucursal inactiva: `403`.
- Más de una asignación vigente: estado inconsistente y `403`; no se elige una arbitrariamente.
- Permiso global: permanece separado y no concede automáticamente permisos BRANCH.

`Visit.BranchId` es la fuente histórica del contexto del recurso. `RegisteredByUserId` y la sucursal actual del usuario no reemplazan ese valor. El traslado de un usuario no modifica visitas históricas.

`Visitor` no tiene `BranchId` aprobado, por lo que no se modificó el modelo. Los futuros casos de visitantes deberán decidir su alcance a partir de la operación o recurso relacionado.

No se creó un endpoint nuevo de negocio en esta fase. El endpoint diagnóstico de permisos continúa disponible; los endpoints de visitas deberán utilizar estas dependencias y servicios cuando se implementen.

## 16. Gestión de usuarios, roles y sucursales

La Fase 8 añade DTOs, servicios y el router `/api/users` para administrar usuarios sin exponer campos sensibles.

Endpoints:

```text
GET    /api/users
GET    /api/users/{user_id}
POST   /api/users
PATCH  /api/users/{user_id}
POST   /api/users/{user_id}/activate
POST   /api/users/{user_id}/deactivate
GET    /api/users/{user_id}/assignments
POST   /api/users/{user_id}/assignments
GET    /api/users/{user_id}/roles
POST   /api/users/{user_id}/transfer
```

Permisos utilizados:

- `MANAGE_USERS` para listar, consultar, crear, modificar, activar, desactivar y consultar roles/asignaciones.
- `ASSIGN_USER_BRANCH` para crear una asignación.
- `MOVE_USER_BRANCH` para transferir un usuario.

Estos permisos son `GLOBAL` en el catálogo aprobado y deben estar concedidos mediante `RolePermission` o `UserPermission`. No existe lógica especial para `ADMIN` o `SUPER_ADMIN`.

La transferencia valida usuario activo, sucursal activa, intervalos `[ValidFrom, ValidUntil)`, solapamientos e historial. Cierra la asignación anterior con `Status = 'ENDED'` y crea la nueva con `Status = 'ACTIVE'`. La operación utiliza una sola transacción de sesión y el hint SQL Server `WITH (UPDLOCK, HOLDLOCK)` para bloquear el historial del usuario. Una colisión se revierte y se devuelve como conflicto.

La desactivación usa `IsActive = false` y `DeactivatedAt`; no elimina datos históricos ni cierra automáticamente la asignación, porque `PermissionService` ya impide operar a usuarios inactivos y el modelo no aprobó una política adicional de cierre automático.

La creación de usuarios puede recibir un rol existente y una sucursal inicial. El rol se busca por `Code`, debe estar activo y se registra en `UserRole` sin `BranchId`. La sucursal se valida mediante `Branch` y la asignación requiere `ASSIGN_USER_BRANCH`.

`UserResponse` y sus respuestas relacionadas nunca incluyen `PasswordHash`, contraseñas ni tokens. Los cambios administrativos importantes quedan identificados como puntos que deberán alimentar `AuditLog` en la fase de auditoría.

## 17. Seguridad transversal

Está preparado:

- Hashing de contraseñas mediante `pwdlib` y Argon2.
- Creación y decodificación de JWT mediante `PyJWT`.
- Excepciones de autorización como `UnauthorizedError` y `ForbiddenError`.
- Modelo `AuditLog` y servicio operativo de auditoría.
- Campos para IP, agente de usuario y correlación.
- Foreign keys históricas con `NO ACTION`.
- Desactivación lógica mediante `IsActive`.

- Emisión de refresh tokens.
- Permisos SQL Server separados para hacer `AuditLog` append-only a nivel de base de datos.

## 18. Gestión de visitas

La Fase 10 implementa:

```text
GET    /api/visits
GET    /api/visits/{visit_id}
POST   /api/visits
PATCH  /api/visits/{visit_id}
POST   /api/visits/{visit_id}/complete
POST   /api/visits/{visit_id}/cancel
```

Permisos utilizados:

- `VIEW_VISITS` para listado y detalle.
- `CREATE_VISIT` para creación.
- `UPDATE_VISIT` para actualización, completion y cancelación.

La creación deriva `BranchId` del `BranchContext` autorizado y `RegisteredByUserId` del usuario autenticado. Los DTOs no aceptan esos campos. El listado y el detalle aplican `Visit.branch_id == contexto.branch_id` directamente en SQL; nunca se filtran visitas en Python después de cargarlas.

`Visitor` debe existir y estar activo. `VisitReason` debe existir y estar activo. No se crean visitantes ni motivos automáticamente.

Las únicas transiciones permitidas son `ACTIVE -> COMPLETED` y `ACTIVE -> CANCELLED`. Completion registra `ExitAt` y `CompletedByUserId`; cancelación registra `CancelledAt`, `CancelledByUserId` y una razón obligatoria. No existe borrado físico.

`Visit.BranchId` y `RegisteredByUserId` son históricos e inmutables desde estas operaciones. Un traslado posterior del usuario no cambia una visita existente.

## 19. Auditoría operativa

La auditoría utiliza el modelo `AuditLog` existente y no requiere cambios de esquema.

Eventos registrados:

```text
LOGIN
CREATE_USER
UPDATE_USER
DEACTIVATE_USER
ASSIGN_USER_BRANCH
MOVE_USER_BRANCH
CREATE_VISITOR
UPDATE_VISITOR
CREATE_VISIT
CHECKOUT_VISIT
CANCEL_VISIT
```

`AuditService` serializa únicamente campos permitidos y elimina claves sensibles como passwords, hashes, tokens, Authorization, secrets, API keys y credenciales. No serializa objetos ORM completos ni requests completos.

Los cambios de negocio y sus eventos se agregan a la misma sesión antes del commit. Si la operación hace rollback, el evento no queda confirmado.

El único endpoint público es:

```text
GET /api/audit-logs
```

Requiere `VIEW_AUDIT_LOGS`, es paginado, utiliza filtros SQL y ordena por `CreatedAt DESC, Id DESC`. No existen endpoints de creación, edición o eliminación de auditoría.

La respuesta también vuelve a redactar `OldValues` y `NewValues` para proteger registros históricos.

## 20. Dashboard operacional

La Fase 12 implementa métricas agregadas calculadas desde `Visit`, sin tablas ni modelos nuevos:

```text
GET /api/dashboard/summary
GET /api/dashboard/visits-by-day
GET /api/dashboard/visits-by-status
GET /api/dashboard/visits-by-reason
```

El alcance se resuelve desde el usuario autenticado. `VIEW_GLOBAL_REPORTS` produce agregados globales; en caso contrario se exige `VIEW_REPORTS` y `BranchAccessService` limita las consultas a la sucursal actual. No se acepta `branch_id` del cliente como autoridad.

Las agregaciones utilizan `COUNT`, `COUNT(DISTINCT Visit.VisitorId)` y `GROUP BY` directamente en SQL. Los rangos `date_from` y `date_to` son fecha/hora ISO 8601 UTC; `date_to` funciona como límite superior inclusivo a nivel de día mediante un límite SQL exclusivo al inicio del día siguiente.

No se generan eventos de auditoría por consultas de Dashboard.

## 21. Reportes

La Fase 13 implementa dos endpoints:

```text
GET /api/reports/visits
GET /api/reports/visits/summary
```

`VIEW_REPORTS` limita los resultados a la sucursal actual resuelta por `BranchAccessService`. `VIEW_GLOBAL_REPORTS` permite consultar todas las sucursales o filtrar una sucursal concreta. Un `branch_id` recibido por el cliente nunca concede acceso.

El reporte detallado acepta filtros combinables por `date_from`, `date_to`, `status`, `reason_id`, `visitor_id`, `registered_by_user_id`, `branch_id` y búsqueda textual. Sus límites de fecha son `[date_from, date_to)`, en UTC, y ordena por `EntryAt DESC, Id DESC`.

El resumen acepta `group_by=status|reason|registered_by|branch`. La agrupación por sucursal requiere alcance global. Todas las consultas usan `WHERE`, `JOIN`, `COUNT`, `GROUP BY`, `OFFSET` y `LIMIT` en SQL; no se cargan todas las visitas en memoria.

Los visitantes se relacionan mediante `Visit`; no se agregó `BranchId` a `Visitor`. La identificación se devuelve enmascarada y nunca se expone `IdentificationNormalized`.

No se implementan exportaciones, PDF, CSV, Excel, programación ni envío de reportes.

## 22. Alembic y migraciones

La configuración de Alembic está en [alembic.ini](../alembic.ini) y [migrations/env.py](../migrations/env.py).

Actualmente:

- `script_location` apunta a `migrations`.
- `sqlalchemy.url` no está hardcodeada en `alembic.ini`.
- La URL se obtiene desde `Settings`.
- `Base.metadata` se utiliza como `target_metadata`.
- Todos los modelos se importan desde el registro central.
- La carpeta `migrations/versions` contiene la revisión inicial.
- `Base.metadata` contiene las 15 tablas.
- Las revisiones `df98eb51ee34` y `276b94986df8` están aplicadas.
- La tabla `alembic_version` registra la revisión actual.
- El esquema fue validado directamente mediante vistas `sys.*` de SQL Server.

## 23. Tests

Los tests están en:

```text
tests/
├── test_authorization.py
├── test_auth.py
├── test_branch_access.py
├── test_health.py
└── test_models.py
```

### Test de API

`test_health.py` verifica que:

- `GET /api/health` responde `200`.
- `status` es `ok`.
- La respuesta contiene el servicio.

### Tests de modelos

`test_models.py` verifica que:

- Las 15 tablas están en `Base.metadata`.
- Los mappers se configuran sin ambigüedades.
- Las foreign keys usan `NO ACTION`.
- Los índices principales existen.
- Los constraints principales están registrados.
- Los índices filtrados tienen `mssql_where`.
- El DDL del índice filtrado compila con el dialecto MSSQL.

Último resultado conocido:

```text
106 passed
11 warnings
```

Los warnings provienen de dependencias de `Starlette`, `httpx` y `anyio`; no corresponden a errores de los modelos.

## 24. Lo que el backend SÍ contiene

Actualmente contiene:

- Aplicación FastAPI funcional.
- Endpoint raíz.
- Health check.
- Swagger y ReDoc.
- CORS configurable.
- Configuración por variables de entorno.
- Manejo global de errores.
- Utilidades de hashing de contraseñas.
- Utilidades JWT preparadas.
- Base SQLAlchemy.
- Sesiones SQLAlchemy.
- 15 modelos ORM.
- Relaciones ORM.
- Foreign keys.
- Índices.
- Índices filtrados SQL Server.
- Check constraints.
- Registro de modelos para Alembic.
- Diseño técnico de base de datos.
- Tests de API y de metadata.
- Separación inicial entre domain, application, infrastructure, api y core.

## 25. Lo que el backend NO contiene todavía

Todavía no contiene funcionalidades completas de negocio:

### Usuarios y gestión de identidad

- No existe endpoint de logout.
- No existe refresh token persistente.
- No existe autenticación federada.
- No existe recuperación de contraseña.
- La gestión de usuarios, roles y asignaciones ya existe bajo `/api/users`.
- La transferencia de sucursal ya existe y conserva el historial.
- El cambio de roles se realiza mediante `PATCH /api/users/{user_id}` usando roles existentes.

### Autorización

- La evaluación de permisos y el contexto de sucursal ya están implementados.
- Los endpoints de usuarios están protegidos por permisos reales.
- Los endpoints de visitas, Dashboard y Reportes aplican filtros de sucursal mediante SQL.

### Sucursales

- No existen endpoints de sucursales.
- No existen datos oficiales cargados.
- No existen seeds.
- No existe jerarquía `Sede -> Centro -> Punto`.
- No existe catálogo real de ubicaciones en SQL Server.

### Visitantes

- La gestión de visitantes está implementada bajo `/api/visitors`.
- La identificación se normaliza, se enmascara y no expone `IdentificationNormalized`.
- No existe CRUD separado de `VisitorType`.

### Visitas

- La gestión de visitas está implementada bajo `/api/visits`.
- Existen creación, actualización, consulta, paginación, checkout y cancelación.
- Existen transiciones `ACTIVE -> COMPLETED` y `ACTIVE -> CANCELLED`.
- Dashboard y Reportes están implementados en sus routers respectivos.

### Auditoría y notificaciones

- Auditoría operativa y `GET /api/audit-logs` están implementados.
- No existe control append-only mediante permisos SQL Server a nivel de infraestructura.
- Notificaciones no están implementadas y permanecen pendientes.

### Citas y pre-registro

- No están implementados.
- Quedan reservados para una fase posterior.

### Base de datos

- La migración inicial ya existe.
- El esquema fue aplicado en `SeNaSaVisitsDB`.
- La existencia y conexión a `SeNaSaVisitsDB` fueron confirmadas.
- Las 15 tablas del modelo fueron validadas contra metadatos de SQL Server.
- No se han cargado datos iniciales.
- No hay seeds.
- La tabla `alembic_version` registra `276b94986df8`.

### Operación y despliegue

- No existe Dockerfile.
- No existe Docker Compose.
- No existe pipeline CI/CD.
- No existe configuración de producción.
- No existe observabilidad completa.
- No existe monitoreo de salud de SQL Server.
- No existe documentación de despliegue productivo.

## 26. Dependencias principales

Las dependencias están definidas en [requirements.txt](../requirements.txt):

- `fastapi`.
- `uvicorn`.
- `sqlalchemy`.
- `alembic`.
- `pydantic`.
- `pydantic-settings`.
- `pyodbc`.
- `pyjwt`.
- `pwdlib[argon2]`.
- `python-multipart`.
- `python-dotenv`.
- `pytest`.
- `httpx`.

## 27. Cómo ejecutar actualmente

Crear entorno virtual:

```powershell
python -m venv .venv
```

Activar entorno:

```powershell
.venv\Scripts\Activate.ps1
```

Instalar dependencias:

```powershell
pip install -r requirements.txt
```

Configurar variables:

```powershell
Copy-Item .env.example .env
```

Completar `.env` con valores reales sin subirlo al repositorio.

Iniciar API:

```powershell
uvicorn main:app --reload
```

Ejecutar tests:

```powershell
python -m pytest
```

En el entorno actual también se utiliza:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 28. Estado de la base de datos y migración

La migración inicial fue creada, revisada y aplicada correctamente mediante Alembic.

Estado actual:

- Base de datos: `SeNaSaVisitsDB`.
- Instancia local: `MSSQLSERVER` en el equipo local.
- Conexión de desarrollo: autenticación integrada de Windows por `lpc:localhost`.
- Driver ODBC: `ODBC Driver 17 for SQL Server`.
- Revisión actual: `276b94986df8`.
- `down_revision`: `None`.
- Tablas del modelo: 15.
- Tabla técnica adicional: `alembic_version`.
- Foreign keys: 25.
- Foreign keys con cascada: 0.
- Columnas identity: 15.
- Índices filtrados: 6.
- Check constraints: 10.

La base no contiene datos seed. No se ejecutaron operaciones destructivas ni se creó automáticamente la base de datos.

## 29. Discrepancias conocidas

El archivo [README.md](../README.md) todavía describe el estado anterior de Fase 1 y dice que no existen entidades ni modelos de dominio. Esa información está desactualizada con respecto al estado real actual.

El estado real es:

- Existen 15 modelos ORM en `app/infrastructure/persistence/models`.
- Existen tests de modelos.
- Alembic importa los modelos en `migrations/env.py`.
- La migración inicial existe y está aplicada.
- No existen entidades de dominio puras, lo cual sí continúa siendo correcto.

La documentación de diseño [docs/database-design.md](database-design.md) y este archivo representan mejor el estado actual que el README antiguo.

## 30. Próximos pasos naturales

La siguiente fase puede implementar casos de uso, repositorios, aislamiento de recursos por sucursal y endpoints de negocio, manteniendo las restricciones del diseño aprobado. La autenticación y la evaluación de permisos ya están disponibles.

## 31. Resumen final

El backend actual es una base técnica sólida para el sistema SeNaSa Visits:

- La API FastAPI funciona.
- La arquitectura está separada por capas.
- El modelo de datos aprobado está implementado en SQLAlchemy.
- Las 15 entidades están registradas.
- Las relaciones y restricciones básicas están verificadas.
- Los tests locales pasan.
- La configuración de Alembic está preparada.

Pero todavía no es un sistema completo de gestión de visitas en producción porque aún no tiene:

- Migración aplicada.
- Base de datos confirmada.
- Gestión de usuarios mediante CRUD.
- CRUD y endpoints de negocio con aislamiento aplicado a cada recurso.
- Usuarios operativos.
- CRUD.
- Servicios de negocio.
- Endpoints de visitantes y visitas.
- Reportes.
- Dashboard.
- Auditoría automática.
- Notificaciones funcionales.
- Datos iniciales.

En términos prácticos, el proyecto se encuentra en la transición entre la implementación del modelo persistente y la creación real del esquema de base de datos.
