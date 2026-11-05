# Auditoría de correspondencia del dominio — Fase 2

**Proyecto:** SeNaSaVisits  
**Alcance:** comparación estática de los modelos Python, migraciones Alembic, auditoría de Fase 0 y clases Domain C#  
**Fecha:** 2026-11-05

## 1. Resumen ejecutivo

La correspondencia estructural es **buena**: se encuentran las 15 entidades esperadas y no se detectó una columna o relación omitida en los modelos C# revisados. Las definiciones de los modelos SQLAlchemy, la migración inicial y el inventario de entidades de [la auditoría de Fase 0](../../docs/dotnet-migration-audit.md#L194-L237) concuerdan en las columnas, tipos SQL, nulabilidad, claves, restricciones e índices descritos aquí. El catálogo C# cubre los campos y las relaciones de navegación, incluidos `Branch.Region`, `Visit.VisitedPerson`, `Visit.Status`, referencias opcionales de `AuditLog` y los campos de entidad relacionada de `Notification`.

La correspondencia aún **no equivale a compatibilidad de persistencia**. Domain no declara mapeo de tablas/columnas, longitudes, índices, claves generadas, defaults SQL, precisión `DATETIME2(3)` ni conversiones de enums a los códigos `NVARCHAR` en mayúsculas. Esos aspectos deben probarse/configurarse en la futura capa Infrastructure; esta revisión no concluye que exista deriva en SQL Server porque no se conectó a ninguna instancia.

Hallazgos principales:

- **Alto, antes de persistencia:** configurar conversión exacta de los cuatro enums C# a los valores `ACTIVE`/`COMPLETED`/`CANCELLED`, `BRANCH`/`GLOBAL`, `ALLOW`/`DENY` y `ACTIVE`/`ENDED`/`CANCELLED`. La conversión enum predeterminada a entero, o `ToString()` sin transformación, no conserva el esquema.
- **Alto, antes de persistencia:** decidir y probar el mapeo del Value Object `VisitorIdentification` a las dos columnas nullable `identification` e `identification_normalized`. El caso de cadena vacía difiere del servicio Python.
- **Alto, en Application:** mantener las reglas Python de autorización, resolución de sucursal única/activa, solapamiento de asignaciones, transacciones y concurrencia. Los métodos de una entidad C# no reemplazan esas reglas.
- **Medio:** los métodos de transición C# requieren tiempos explícitos. Application deberá proporcionar el instante UTC actual cuando Python usa su reloj, y asignar `exit_at` por defecto cuando la petición de finalización lo omite.
- **Medio:** las fechas `DateTime` C# no normalizan ni indican por sí solas UTC. La comparación y persistencia deben respetar el uso actual de UTC y `DATETIME2(3)`.

**Conclusión:** **GO condicional** para comenzar trabajo de Application sin persistencia ni afirmar paridad completa; **NO-GO** para conectar Infrastructure a SQL Server o declarar compatibilidad hasta cerrar las conversiones, el mapeo de identificación, UTC y las reglas de concurrencia. No se avanzó a Fase 3.

## 2. Fuentes, método y límites

Se contrastaron los modelos de `app/infrastructure/persistence/models/`, `migrations/versions/df98eb51ee34_initial_schema.py`, `migrations/versions/276b94986df8_fix_notification_utc_default.py`, [§6 de la auditoría](../../docs/dotnet-migration-audit.md#L194-L237) y las clases en `dotnet/src/SeNaSaVisits.Domain/`.

La migración inicial crea las 15 tablas. La segunda revisión corrige el default de `notifications.created_at` en `upgrade()`. Esto acredita el contenido versionado en el repositorio, no la revisión aplicada ni el esquema vivo. No se ejecutaron consultas, pruebas, migraciones, seeds ni operaciones de base de datos durante esta revisión.

En las tablas siguientes, `id` representa `BIGINT IDENTITY NOT NULL PRIMARY KEY`; las FK SQL declaradas usan `ON DELETE NO ACTION`. `required`/`NOT NULL` y `?`/`NULL` describen el esquema. Las propiedades C# con `string` o `long` no configuran por sí solas tamaños, nulabilidad SQL, identidad ni restricciones.

## 3. Tabla de las 15 entidades y correspondencia

| Entidad y tabla | Definición SQL/Python verificada | Correspondencia C# y relaciones | Evaluación |
| --- | --- | --- | --- |
| `BranchType` / `branch_types` | `id`; `code NVARCHAR(30)` requerido y único; `name NVARCHAR(100)` requerido; `description NVARCHAR(500)` nullable; `is_active BIT` requerido default Python `True`/SQL `1`; `created_at`, `updated_at DATETIME2(3)` requeridos con default UTC. | [BranchType.cs](../src/SeNaSaVisits.Domain/Entities/BranchType.cs) contiene `Code`, `Name`, `Description`, `IsActive`; navegación 1:N `Branches`. | Coincide. Tabla/longitudes/unique/default deben configurarse en Infrastructure. |
| `Branch` / `branches` | `id`; `code NVARCHAR(30)` requerido único; `name NVARCHAR(200)` requerido; `branch_type_id BIGINT` requerido FK; `region NVARCHAR(100)`, `address NVARCHAR(300)`, `phone NVARCHAR(30)` nullable; `is_active BIT` default true/1; timestamps requeridos UTC. Índice en `branch_type_id`. | [Branch.cs](../src/SeNaSaVisits.Domain/Entities/Branch.cs) conserva todos los campos, incluyendo `Region`; navegación N:1 a `BranchType` y 1:N a permisos, asignaciones, visitas, auditoría y notificaciones. | Coincide. `BranchType` puede ser null en el objeto C# cuando la navegación no se cargó; `BranchTypeId` sí es requerido. |
| `User` / `users` | `username NVARCHAR(80)` requerido único; `email NVARCHAR(254)` nullable y unique filtrado; nombres `NVARCHAR(100)` requeridos; `employee_code NVARCHAR(50)` nullable y unique filtrado; `password_hash NVARCHAR(255)` requerido; `is_active BIT` default true/1; `deactivated_at DATETIME2(3)` nullable; timestamps UTC. | [User.cs](../src/SeNaSaVisits.Domain/Entities/User.cs) contiene todos los campos y colecciones de roles, permisos, asignaciones, visitas (registrador/completador/cancelador), auditoría y notificaciones. | Coincide estructuralmente. Unique filtrados, límites y almacenamiento de hash son de persistencia/aplicación. |
| `Role` / `roles` | `code NVARCHAR(50)` requerido único; `name NVARCHAR(100)` requerido; `description NVARCHAR(500)` nullable; `is_active BIT` default true/1; timestamps UTC. | [Role.cs](../src/SeNaSaVisits.Domain/Entities/Role.cs) representa esos campos y relaciones 1:N a `UserRole` y `RolePermission`. | Coincide. El esquema permite varios roles activos por usuario; el servicio Python reemplaza el conjunto activo al asignar un rol (ver §4). |
| `UserRole` / `user_roles` | FK requeridas `user_id`, `role_id`, `assigned_by_user_id`; `assigned_at DATETIME2(3)` requerido default UTC; `revoked_at` nullable; `is_active BIT` default true/1; `created_at`, `updated_at` requeridos default UTC. Índice único filtrado `(user_id, role_id)` cuando activo. | [UserRole.cs](../src/SeNaSaVisits.Domain/Entities/UserRole.cs) contiene todos los campos y navegaciones N:1 a usuario, rol y asignador; hereda ambos timestamps. | Coincide. No existe check SQL que relacione `IsActive` con `RevokedAt`; no añadirlo por suposición. |
| `Permission` / `permissions` | `code NVARCHAR(80)` requerido único; `name NVARCHAR(120)`, `resource NVARCHAR(80)`, `action NVARCHAR(80)`, `scope NVARCHAR(20)` requeridos; `description NVARCHAR(500)` nullable; `is_active BIT` default true/1; timestamps UTC. CHECK `scope IN ('BRANCH','GLOBAL')`. | [Permission.cs](../src/SeNaSaVisits.Domain/Entities/Permission.cs) incluye propiedades y navegación 1:N a `RolePermission`/`UserPermission`; `Scope` es enum. | Campos y cardinalidad coinciden. El enum requiere conversión SQL string exacta. |
| `RolePermission` / `role_permissions` | FK requeridas `role_id`, `permission_id`, `assigned_by_user_id`; `assigned_at DATETIME2(3)` requerido default UTC; `is_active BIT` default true/1. Unique filtrado activo por `(role_id, permission_id)`. **No** hay `created_at` ni `updated_at`. | [RolePermission.cs](../src/SeNaSaVisits.Domain/Entities/RolePermission.cs) contiene todos los campos y navegaciones N:1 a rol, permiso y asignador; hereda solo `Id`. | Coincide; ausencia de timestamps compartidos es correcta. |
| `UserPermission` / `user_permissions` | FK requeridas `user_id`, `permission_id`, `assigned_by_user_id`; `branch_id BIGINT` nullable FK; `effect NVARCHAR(10)` requerido; `valid_from DATETIME2(3)` requerido; `valid_until` nullable; `is_active BIT` default true/1; `created_at DATETIME2(3)` requerido default UTC. CHECK efecto ALLOW/DENY y fin posterior al inicio; índice de búsqueda no único. | [UserPermission.cs](../src/SeNaSaVisits.Domain/Entities/UserPermission.cs) contiene esos campos, `CreatedAt`, navegación opcional a sucursal y las demás relaciones; enum `Effect`; validación de fin y vigencia temporal. | Coincide en forma. `IsEffectiveAt` no evalúa usuario/permisos activos, scope/branch, existencia de asignación ni precedencia; esas reglas están en Application en Python. |
| `UserBranchAssignment` / `user_branch_assignments` | FK requeridas `user_id`, `branch_id`, `assigned_by_user_id`; `valid_from DATETIME2(3)` requerido; `valid_until` nullable; `reason NVARCHAR(500)` nullable; `status NVARCHAR(30)` requerido; timestamps requeridos default UTC. Checks de fin > inicio y estado-fecha; estados ACTIVE, ENDED y CANCELLED; unique filtrado de asignación abierta activa por usuario; índices de usuario/sucursal y fechas. | [UserBranchAssignment.cs](../src/SeNaSaVisits.Domain/Entities/UserBranchAssignment.cs) representa todos los campos/navegaciones y ambos timestamps. Su enum, `Validate()` e `IsEffectiveAt()` reflejan estado/intervalo de una fila. | Coincide a nivel de fila. No representa solapamientos, exclusividad temporal entre filas, usuario activo, sucursal activa, contexto exactamente único ni bloqueos concurrentes. |
| `Visitor` / `visitors` | `identification`, `identification_normalized NVARCHAR(50)` nullable; `first_name`, `last_name NVARCHAR(100)` requeridos; `phone NVARCHAR(30)`, `email NVARCHAR(254)`, `company NVARCHAR(200)` nullable; `visitor_type_id BIGINT` nullable FK; `is_active BIT` default true/1; timestamps UTC. Unique filtrado sobre normalized no nulo; no tiene `branch_id`. | [Visitor.cs](../src/SeNaSaVisits.Domain/Entities/Visitor.cs) contiene nombres/contacto/tipo/estado/fechas y `Identification` VO; `IdentificationNormalized` es proyección calculada. Navegación N:1 opcional a tipo, 1:N visitas. | Correspondencia semántica, no mapeo de dos columnas demostrado. La entrada exactamente vacía difiere; ver §4. |
| `VisitorType` / `visitor_types` | `code NVARCHAR(50)` requerido único; `name NVARCHAR(100)` requerido; descripción nullable; `is_active BIT` default true/1; timestamps UTC. | [VisitorType.cs](../src/SeNaSaVisits.Domain/Entities/VisitorType.cs) conserva campos y relación 1:N a visitantes. | Coincide. |
| `Visit` / `visits` | FKs requeridas a visitor, branch, registered user y reason; `entry_at DATETIME2(3)` requerido; `exit_at` nullable; `destination`, `visited_person NVARCHAR(200)` nullable; `status NVARCHAR(30)` requerido; `notes NVARCHAR(1000)` nullable; completed/cancelled user IDs nullable FK; `cancelled_at` y `cancellation_reason NVARCHAR(500)` nullable; timestamps UTC. Checks de estado, salida ≥ entrada y datos de cancelación; índices por sucursal/estado/fecha y visitante/fecha. | [Visit.cs](../src/SeNaSaVisits.Domain/Entities/Visit.cs) contiene campos y todas las navegaciones, incluidos `VisitedPerson` y enum `Status`; aplica transiciones y validación de fila. | Coincide en estructura. Estado necesita conversión string; salida/UTC y valores por defecto deben coordinarse en Application/Infrastructure. |
| `VisitReason` / `visit_reasons` | `code NVARCHAR(50)` requerido único; `name NVARCHAR(120)` requerido; descripción nullable; `is_active BIT` default true/1; timestamps UTC. | [VisitReason.cs](../src/SeNaSaVisits.Domain/Entities/VisitReason.cs) contiene campos y relación 1:N a visitas. | Coincide. |
| `AuditLog` / `audit_logs` | `actor_user_id BIGINT` nullable FK y `branch_id BIGINT` nullable FK; `entity_id BIGINT` nullable **sin FK**; acción/tipo requeridos; `old_values`, `new_values NVARCHAR(MAX)` nullable; `ip_address VARCHAR(45)`, `user_agent NVARCHAR(500)`, `correlation_id NVARCHAR(100)` nullable; `created_at DATETIME2(3)` requerido UTC. Sin `updated_at`. | [AuditLog.cs](../src/SeNaSaVisits.Domain/Entities/AuditLog.cs) conserva campos, referencias opcionales Actor/Branch y EntityId escalar sin navegación FK; propiedades son init-only. | Coincide. Init-only no impone append-only en base/servicio; la aplicación Python es quien lo opera append-only. |
| `Notification` / `notifications` | FK requerida a User, `branch_id` nullable FK; `title NVARCHAR(200)`, `message NVARCHAR(1000)`, `type NVARCHAR(50)` requeridos; `is_read BIT` default false/0; `read_at` nullable; `related_entity_type NVARCHAR(80)` y `related_entity_id BIGINT` nullable y **sin FK**; `created_at DATETIME2(3)` requerido UTC. Check leído ↔ `read_at` no nulo y un índice por usuario/lectura/fecha. Sin `updated_at`. | [Notification.cs](../src/SeNaSaVisits.Domain/Entities/Notification.cs) contiene todos los campos, navegaciones User/Branch, `CreatedAt` y `Validate()` de read state. | Coincide. La entidad relacionada es referencia lógica, no FK; no se encontró flujo de notificaciones Python. |

### 3.1 Referencias de esquema por entidad

Los rangos Alembic apuntan a la creación de tablas, claves, checks e índices en la revisión inicial. La revisión de notificación se detalla en §8.

- `BranchType`: [modelo Python](../../app/infrastructure/persistence/models/branch_type.py#L11-L19) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L21-L31).
- `Branch`: [modelo Python](../../app/infrastructure/persistence/models/branch.py#L11-L30) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L97-L112).
- `User`: [modelo Python](../../app/infrastructure/persistence/models/user.py#L16-L54) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L58-L74).
- `Role`: [modelo Python](../../app/infrastructure/persistence/models/role.py#L11-L21) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L47-L57).
- `UserRole`: [modelo Python](../../app/infrastructure/persistence/models/user_role.py#L14-L31) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L126-L141).
- `Permission`: [modelo Python](../../app/infrastructure/persistence/models/permission.py#L11-L27) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L32-L46).
- `RolePermission`: [modelo Python](../../app/infrastructure/persistence/models/role_permission.py#L14-L28) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L113-L125).
- `UserPermission`: [modelo Python](../../app/infrastructure/persistence/models/user_permission.py#L14-L35) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L220-L239).
- `UserBranchAssignment`: [modelo Python](../../app/infrastructure/persistence/models/user_branch_assignment.py#L14-L37) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L198-L219).
- `Visitor`: [modelo Python](../../app/infrastructure/persistence/models/visitor.py#L11-L28) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L142-L158).
- `VisitorType`: [modelo Python](../../app/infrastructure/persistence/models/visitor_type.py#L11-L20) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L86-L96).
- `Visit`: [modelo Python](../../app/infrastructure/persistence/models/visit.py#L14-L45) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L240-L271).
- `VisitReason`: [modelo Python](../../app/infrastructure/persistence/models/visit_reason.py#L11-L20) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L75-L85).
- `AuditLog`: [modelo Python](../../app/infrastructure/persistence/models/audit_log.py#L14-L36) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L159-L179).
- `Notification`: [modelo Python](../../app/infrastructure/persistence/models/notification.py#L14-L37) · [DDL](../../migrations/versions/df98eb51ee34_initial_schema.py#L180-L197).

### 3.2 Relaciones: evaluación global

Las navegaciones C# corresponden a las relaciones ORM declaradas: `BranchType`–`Branch`; `VisitorType`–`Visitor`; `VisitReason`–`Visit`; y tablas de asociación con sus referencias a usuario, rol, permiso o sucursal. Las relaciones de Visit distinguen correctamente usuario registrador, completador y cancelador. Las colecciones inversas modelan 1:N donde SQLAlchemy declara esas relaciones.

Las propiedades de navegación C# son referencias de objeto y no sustituyen las FK SQL. En particular, una navegación nullable en C# también puede significar “no cargada” aunque su FK sea requerida; la obligatoriedad efectiva la debe definir el mapeo Infrastructure. `Notification.RelatedEntityId` y `AuditLog.EntityId` no deben convertirse en FK: el esquema los define como identificadores lógicos.

## 4. Propiedades con diferencias o dudas

### `Branch.Region` y `Visit.VisitedPerson`

No se detectó discrepancia: `Branch.Region` es nullable y corresponde a `NVARCHAR(100)`; `Visit.VisitedPerson` es nullable y corresponde a `NVARCHAR(200)`. Ambas propiedades están presentes en C# y deben recibir las longitudes correctas en el futuro mapeo SQL.

### `Visit.Status`

Python lo almacena como `NVARCHAR(30)` y la base acepta solo `ACTIVE`, `COMPLETED`, `CANCELLED`. C# lo representa como `VisitStatus` (`Active`, `Completed`, `Cancelled`) y lo inicializa en `Active`. El default en memoria coincide con el servicio Python al crear una visita, que asigna explícitamente `ACTIVE`; la columna SQL no tiene default server-side. No convertir enum a entero ni a los nombres PascalCase.

### `Notification` y entidad relacionada

La entidad Python existe en el modelo/migración, pero no se identificó un servicio/ruta funcional que cree o gestione notificaciones. El campo relacionado es un par polimórfico (`related_entity_type`, `related_entity_id`) sin FK. La navegación a User/Branch sí corresponde a las FK reales. La validación C# de lectura coincide con el CHECK SQL.

### `AuditLog` y referencias opcionales

`ActorUserId` y `BranchId` son nullable FK; `EntityId` también es nullable pero **no** es FK. Las navegaciones opcionales de actor y sucursal y el ID escalar de entidad en C# son correctos. El append-only se aplica desde la aplicación Python: no hay restricción SQL ni comportamiento de repositorio en Domain que lo garantice. Las propiedades init-only reducen mutaciones del objeto tras inicializar, pero no constituyen una política de almacenamiento.

### `VisitorIdentification`

Python mantiene dos columnas independientes: original (`identification`) y normalizada (`identification_normalized`). La normalización implementada quita espacios y convierte a mayúscula; conserva guiones y otra puntuación. El VO C# conserva esos comportamientos en entradas ordinarias y el campo normalizado se proyecta desde el objeto, pero aún no hay mapeo que demuestre que `RawValue` y `NormalizedValue` se escriben en las columnas adecuadas.

Diferencia concreta: el servicio Python usa `payload.identification.strip() if payload.identification else None`. Una entrada exactamente `""` se guarda como `NULL`; `VisitorIdentification.From("")` devuelve un VO no nulo con `RawValue` vacío y `NormalizedValue` null. Una entrada formada por espacios es truthy en Python y termina como raw vacío, de modo que no es el mismo caso. Se debe decidir si Application conserva exactamente el tratamiento o si el contrato permite una diferencia; esta auditoría no lo decide.

### Defaults y timestamps

- `IsActive = true` en C# coincide con defaults Python/SQL documentados en las entidades correspondientes; `Notification.IsRead` inicia en false, equivalente al default SQL.
- `Visit.Status = Active` corresponde al flujo de alta Python, pero no es default de la columna SQL.
- `Entity.Id` es `long`, compatible con `BIGINT`, pero no indica `IDENTITY`/generación en DB.
- `TimestampedEntity` agrega los dos campos correctos a BranchType, Branch, User, Role, UserRole, Permission, UserBranchAssignment, VisitorType, Visitor, Visit y VisitReason. `CreatedEntity` solo se usa para UserPermission y Notification. AuditLog declara su `CreatedAt`; RolePermission tiene `AssignedAt` y no `CreatedAt`/`UpdatedAt`.
- Las clases base no codifican `DATETIME2(3)`, `SYSUTCDATETIME()`, precisión, generación de columnas ni refresco de `UpdatedAt`. En Python, `updated_at` usa SQLAlchemy `onupdate`, no trigger SQL. Infrastructure deberá reproducirlo.
- SQL Server `DATETIME2` no persiste `DateTime.Kind`; el código debe mantener convención UTC. Los métodos de vigencia/visita comparan `DateTime` recibidos sin normalizarlos. Python convierte los timestamps timezone-aware a UTC naive en servicios.

## 5. Reglas de dominio verificadas

| Regla | Backend Python y esquema | C# | Evaluación |
| --- | --- | --- | --- |
| Ventana temporal de asignación | `valid_from <= instant` y `valid_until is null or valid_until > instant`; status debe ser ACTIVE; checks exigen `valid_until > valid_from` y coherencia status/fin. | `IsEffectiveAt()` e `Validate()` aplican estas condiciones a una fila. | Coincide a nivel de una asignación. Python además requiere exactamente una asignación vigente y sucursal activa al resolver contexto; C# no implementa esa consulta global. |
| Vigencia de permiso directo | Python filtra `is_active`, `valid_from <= now`, `valid_until is null or > now`, además de scope/branch/permission/user. DB check de fechas. | `IsEffectiveAt()` verifica activo y fechas; `Validate()` verifica orden del intervalo. | Coincidencia parcial intencional; no equivale a autorización efectiva. |
| Precedencia DENY/ALLOW/rol | `PermissionService` aplica DENY > ALLOW > RolePermission en Application. | No está implementada en Domain. | No es discrepancia de esquema: debe implementarse/probarse en futura Application, no inferirse de `PermissionEffect`. |
| Transiciones de visita | Solo visitas ACTIVE se actualizan/completan/cancelan; checkout fija COMPLETED, salida y actor; cancel fija CANCELLED, actor, timestamp actual y razón normalizada no vacía. | `Complete()`/`Cancel()` rechazan estado no activo y fijan estado/datos; `Validate()` comprueba enum, salida no anterior y datos de cancelación. | Regla principal coincide. Python normaliza razón y timestamp en servicio; C# recibe la fecha de cancelación como parámetro y no normaliza zona horaria. El caller deberá suministrar tiempo UTC. |
| Finalización de visita | Python acepta `exit_at` opcional y, si falta, usa ahora UTC; valida `exit_at >= entry_at`. | `Complete()` exige `exitAt` explícito, valida orden y registra el actor. | Debe Application resolver ausencia a reloj UTC antes de invocar el dominio. No hay incompatibilidad si se conserva ese comportamiento. |
| Restricciones DB de Visit | Estados permitidos; salida ≥ entrada; CANCELLED requiere actor, fecha y razón no nulos. DB no exige ACTIVE sin salida ni COMPLETED con salida. | `Validate()` representa estado permitido, fecha y cancelación. Transiciones C# producen datos de finalización completos. | Correcto respecto al CHECK; no atribuir a la base restricciones de ciclo de vida más fuertes. |
| Consistencia de Notification | CHECK requiere `is_read=1` ↔ `read_at` no nulo. | `Validate()` compara el booleano con presencia de timestamp. | Coincide. No implementa un flujo de notificación, que no existe en Python. |
| Identificación | Python quita whitespace y upper, conserva guiones; normalizada vacía queda null. | VO trim en extremos, elimina whitespace, upper invariant, conserva puntuación; exact empty difiere en el valor raw. | Coincide para normalización usual; requiere prueba de paridad con whitespace/casing Unicode y resolver la entrada exactamente vacía. |
| Auditoría append-only | AuditService añade eventos; no hay mutación vía API ni constraint SQL append-only. | AuditLog init-only tras creación, pero no hay garantía en persistencia. | Solo inmutabilidad de instancia parcial; append-only debe preservarse en capa de escritura de Application/Infrastructure. |

La representación de estados, scopes y efectos en enums es compatible a nivel conceptual, no a nivel de almacenamiento hasta agregar conversiones explícitas. El repositorio Python usa strings/checks SQL, no enums de dominio propios.

## 6. Reglas que requieren confirmación institucional o definición de diseño

1. Confirmar política de codificación de enums en SQL Server: conservar exactamente strings mayúsculos; la opción propuesta para Infrastructure debe tener tests de conversión ida/vuelta.
2. Determinar el tratamiento de identificación exactamente vacía, manteniendo el comportamiento Python o autorizando explícitamente una normalización distinta. No cambiar la regla de guiones: el código actual los conserva aunque documentos antiguos digan que los elimina.
3. Confirmar convención UTC end-to-end y representación de `DateTime` para la migración, incluyendo precisión de 3 milisegundos y reloj utilizado por Application.
4. Resolver si el diseño conceptual de visitas pretende checks adicionales (p. ej. completed requiere exit) o si el comportamiento actual del código y migración es la fuente contractual. No añadir checks/tablas en esta fase.
5. Definir los permisos de cardinalidad de roles: el esquema permite múltiples asignaciones activas distintas; el flujo Python de asignación reemplaza roles activos. Un cambio a múltiples roles efectivos alteraría autorización.
6. Definir quién mantiene la política append-only y protección de audit logs en la arquitectura .NET, ya que el esquema no lo impone.
7. Las decisiones de normalización Unicode y collation para unicidad dependen de reglas de datos/SQL Server que no fueron inspeccionadas ni deben suponerse.

## 7. Relaciones incorrectas o no verificables

No se detectaron relaciones C# contradictorias con las relaciones ORM inspeccionadas. Sin embargo, son **no verificables en SQL Server real** hasta existir mapeo y pruebas de integración. Además:

- Las referencias requeridas tienen navegaciones nullable para permitir entidades no cargadas; Infrastructure debe configurar FK required y delete behavior `NO ACTION` explícitamente.
- Las colecciones C# reflejan cardinalidades ORM, pero no definen FK ni restricciones por sí mismas.
- `AuditLog.EntityId` y `Notification.RelatedEntityId` son IDs escalares, sin relaciones FK, de forma correcta.
- `UserPermission.BranchId` puede ser null según esquema. No existe constraint cruzado que fuerce coherencia entre nullability y `Permission.Scope`; Python la aplica al evaluar autorización.
- `Visitor` es global y no tiene sucursal, aunque sus rutas requieren contexto branch; el modelo C# conserva correctamente la ausencia de `BranchId`.
- La asignación filtrada única solo impide más de una asignación abierta ACTIVA por user_id; no impide solapamientos temporales entre filas ya cerradas. Esa regla depende de servicios y transacciones.

## 8. Riesgos para la futura persistencia SQL Server

1. **Enums:** valores C# PascalCase deben convertirse a strings SQL exactos; SQL checks rechazarán otros formatos.
2. **Identificación:** mapear el VO a dos columnas y preservar nullable/empty semantics; el índice único filtrado aplica a `identification_normalized IS NOT NULL`.
3. **Tipos y longitudes:** cada propiedad debe mapear a tipos exactos (`BIGINT`, `BIT`, `NVARCHAR(n)`, `VARCHAR(45)`, `NVARCHAR(MAX)`, `DATETIME2(3)`). `required string` no define longitud o constraint SQL.
4. **Generación/defaults:** configurar `BIGINT IDENTITY`, defaults server-side y `UpdatedAt` equivalente a SQLAlchemy `onupdate`; no depender exclusivamente de inicializadores C#.
5. **DateTime/UTC:** convertir a UTC consistentemente, gestionar valores sin zona y persistir `DATETIME2(3)`; la comparación de vigencia con diferentes `DateTime.Kind` puede variar.
6. **Índices filtrados y checks:** comprobar DDL efectivo de EF Core contra la migración Alembic; SQLite no certifica el dialecto SQL Server.
7. **Concurrencia:** transferencias y asignaciones solapadas deben usar transacciones/aislamiento o locks equivalentes a los utilizados en Python (`UPDLOCK, HOLDLOCK` en transferencia). El método C# de una entidad no protege concurrencia.
8. **Collation/únicos:** la base no fija collation; unicidad de username, email, employee_code, códigos e identificación debe verificarse con el collation institucional real.
9. **Alembic downgrade:** la revisión `276b94986df8` corrige el default de `notifications.created_at` en upgrade, pero su downgrade vuelve a poner el texto literal `'SYSUTCDATETIME()'`. Es riesgo documentado en el historial; esta auditoría no modificó Alembic ni recomienda ejecutar downgrade.
10. **Estado real:** no se verificó revisión aplicada ni drift de SQL Server. La autoridad de migraciones sigue siendo Alembic conforme al estado actual, y no deben generarse migraciones/cambios desde C# en esta fase.

## 9. Correcciones y acciones recomendadas priorizadas

### Críticas

- No se detectaron omisiones críticas de entidades/campos en el modelo C# respecto a la fuente versionada.

### Altas

1. Antes de EF Core, preparar un mapeo explícito de cada enum a los códigos SQL mayúsculos exactos y pruebas de ida/vuelta.
2. Definir y probar el mapeo de `VisitorIdentification.RawValue` y `NormalizedValue` a dos columnas separadas, incluyendo `null`, cadena vacía y whitespace-only.
3. En Application, preservar autorización completa: actividad de user/permission/branch, precedencia DENY > ALLOW > role, alcance branch/global, única asignación vigente y scope/branch consistency.
4. En Application/Infrastructure, reproducir prevención de solapamiento y la garantía transaccional/concurrente de transferencia; no confiar en `Validate()` por fila.

### Medias

1. Acordar un reloj UTC para invocar `Cancel()` y default de `exitAt` para `Complete()` cuando el request no lo envíe; testear entradas UTC-aware y timestamps de frontera.
2. Añadir contract/integration tests de valores SQL, defaults, longitudes, índices filtrados, checks, FK `NO ACTION` y precisión `DATETIME2(3)` al empezar persistencia; esto no requiere cambios en el Domain auditado.
3. Mantener el comportamiento de roles de la aplicación Python o registrar decisión institucional antes de admitir múltiples grants activos.
4. Preservar append-only/redacción de AuditLog en los componentes de escritura; init-only no reemplaza protección de almacenamiento.

### Bajas

1. Comparar normalización para whitespace y mayúsculas Unicode entre Python y .NET con ejemplos controlados; definir tratamiento sin cambiar silenciosamente datos preexistentes.
2. Mantener `docs/database-design.md` identificado como conceptual y no usar sus checks de estados de visita como si existieran en Alembic.
3. Documentar tablas/longitudes/índices en la futura configuración EF Core manteniendo Alembic como autoridad durante la transición.

## 10. Conclusión: preparación para Application

El Domain C# representa correctamente las 15 formas de entidad y relaciones comprobables desde los archivos versionados. Las reglas locales de fecha, transiciones de visita, cancelación, estado leído de Notification y normalización están en gran parte respaldadas por Python/esquema.

**Recomendación: avanzar de forma condicional a Application** para diseñar casos de uso y políticas, sin aún afirmar paridad productiva. Application debe cubrir las reglas hoy ubicadas en servicios Python y resolver tiempos/defaults descritos en este informe. Antes de Infrastructure/SQL Server deben quedar cerrados los hallazgos de prioridad alta, particularmente conversiones enum, Value Object de identificación, aislamiento/autorización y concurrencia.

### Declaración de alcance

Se realizó solo inspección de código, documentación y revisiones Alembic. No se modificó código C# o Python, frontend, Alembic o esquema; no se instalaron paquetes; no se ejecutaron pruebas, scripts, seeds ni migraciones; no se conectó ni se escribieron datos en SQL Server. El único archivo creado para esta entrega es este informe.
