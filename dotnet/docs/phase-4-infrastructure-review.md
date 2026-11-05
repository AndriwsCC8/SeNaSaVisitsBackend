# Auditoría previa de Infrastructure — Fase 4

**Proyecto:** SeNaSaVisits  
**Alcance:** auditoría de contratos, esquema y persistencia antes de implementar Infrastructure  
**Fecha:** 2026-11-05  
**Resultado inicial:** bloqueada por transferencia fuera de transacción.  
**Actualización:** corrección controlada de Application implementada y validada; Infrastructure sigue sin implementarse.

## 1. Resumen ejecutivo

Se inspeccionaron los contratos y servicios C# de Application, las 15 entidades Domain, los modelos SQLAlchemy, los servicios de Python, la migración inicial y la revisión de Fase 2. La tabla de esquema versionada contiene las entidades y columnas ya inventariadas en la auditoría previa. No se conectó a SQL Server, no se ejecutaron scripts, migraciones, seeds ni pruebas de integración.

La primera revisión detectó una discrepancia que requería corregir Application: **`UserManagementService.TransferAsync` leía el historial fuera de `ITransactionRunner`** y lo reutilizaba para conflicto y `old_branch_id`. Esa corrección se realizó de forma controlada y está documentada en §14. La solución ahora pasa un scope transaccional opaco a lectura protegida y escrituras. La implementación real del lock y conexión compartida sigue siendo responsabilidad futura de Infrastructure.

Infrastructure **no se implementó**. No se instaló `Microsoft.Data.SqlClient` ni se modificó ningún proyecto de Infrastructure. Después de la corrección, `dotnet build` pasó y `dotnet test` aprobó 50 pruebas con dobles. Esto no valida locks, transacciones ADO.NET ni comportamiento SQL Server.

## 2. Fuentes revisadas y límites

- Contratos, DTOs y casos de uso en `dotnet/src/SeNaSaVisits.Application/`.
- Entidades, enum y Value Object en `dotnet/src/SeNaSaVisits.Domain/`.
- [Auditoría de Fase 0](../../docs/dotnet-migration-audit.md), [revisión de Domain Fase 2](phase-2-domain-review.md) y [revisión de Application Fase 3](phase-3-application-review.md).
- Modelos de `app/infrastructure/persistence/models/` y servicios de `app/application/services/`.
- Revisión inicial `migrations/versions/df98eb51ee34_initial_schema.py` y cambio del default de notificación `migrations/versions/276b94986df8_fix_notification_utc_default.py`.
- Pruebas Python existentes, sin ejecutarlas durante esta revisión.

Los archivos prueban la forma del esquema del repositorio, no la revisión aplicada ni el estado de una instancia real. No se verificaron collation, deriva de esquema, datos ni locks en SQL Server. La migración de Fase 0 sigue identificando Alembic como autoridad del esquema actual.

## 3. Discrepancia original y resolución controlada

### Transferencia de sucursal: lectura optimista fuera de la transacción

El contrato anterior no garantizaba que la lectura del historial y las escrituras utilizaran la misma conexión/transacción: `ITransactionRunner` solo recibía un delegado con `CancellationToken`, y `TransferAtomicallyAsync` ocultaba las operaciones que debían usar el scope común. La corrección reemplazó esa transferencia opaca por un contexto transaccional de Application y métodos de repositorio que reciben ese mismo contexto.

La implementación actual abre el scope transaccional antes de `GetHistoryForTransferAsync`. La única lista protegida se usa para la detección de duplicidad/misma sucursal, `old_branch_id`, cierre y comprobación de solapamiento. El cierre y la inserción reciben la misma transacción; la auditoría se añade antes de que el runner confirme.

### Otros puntos que requieren precisión antes de afirmar compatibilidad

- Varios DTO mappers requieren navigations cargadas (`UserRoles/Role`, asignaciones/Branch, `VisitorType`, `UserBranchAssignment.Branch`, todas las referencias de Visit), pero varios métodos `GetByIdAsync`, listados y retornos de transferencia no expresan explícitamente ese requisito en su contrato. Un adapter podría satisfacer el comportamiento implícito, pero no se puede certificar desde las firmas.
- El contrato de `IPasswordHasher` solo expone hash; no existe interfaz de verificación para el login Python. No se implementa ni se infiere autenticación durante esta fase.
- `Notification` tiene tabla y entidad, pero no hay flujo Python ni puerto Application funcional; no se debe inventar un repositorio/servicio de notificaciones.

Los puntos de carga de navegaciones y los contratos de hash/login permanecen como riesgos abiertos para implementación futura, pero no bloquean la corrección transaccional seleccionada.

## 4. Inventario de contratos y tablas involucradas

Los métodos listados son contratos existentes en Application. No son implementaciones .NET existentes. “Navegación” significa que el DTO/servicio necesita los datos relacionados; SQLAlchemy/Domain no hacen que una navegación se cargue automáticamente en ADO.NET.

| Contrato / métodos | Tablas y columnas principales | Operación, filtro y regla que debe respetar | Situación |
| --- | --- | --- | --- |
| `IPermissionDataSource.GetUserActiveAsync`, `GetPermissionAsync` | `users(id,is_active)`; `permissions(id,code,scope,is_active)` | Lecturas escalares por ID/código. | Pendiente; no debe inferir permisos desde roles solamente. |
| `GetDirectGrantsAsync`, `HasActiveRoleGrantAsync` | `user_permissions(user_id,permission_id,branch_id,effect,valid_from,valid_until,is_active)`; `user_roles`; `roles`; `role_permissions` | Cargar decisiones directas; Application comprueba vigencia, branch y `DENY > ALLOW > RolePermission`. Grant de rol requiere las filas activas. | Pendiente; enums se almacenan como texto, no enteros. |
| `IBranchAssignmentReader.GetCurrentAssignmentsAsync` | `user_branch_assignments(user_id,branch_id,valid_from,valid_until,status)` y `branches(id,is_active)` | Devolver todas las asignaciones ACTIVE cuyo intervalo contiene el instante; cargar estado de cada sucursal. Application debe decidir exactamente una coincidencia. | Pendiente; no ocultar filas duplicadas al devolver `FirstOrDefault`. |
| `IUserRepository.GetByIdAsync`, `SearchAsync` | `users`; `user_roles`/`roles`; `user_branch_assignments`/`branches` | Lista busca username/nombres/código; filtros estado, asignación vigente por branch, rol activo; count distinto y `id ASC`; DTO requiere roles/asignaciones/navegaciones. | Pendiente; eager loading del detalle debe aclararse/garantizarse. |
| `UsernameExistsAsync`, `EmailExistsAsync`, `EmployeeCodeExistsAsync` | `users(username,email,employee_code,id)` | Existencia exacta y exclusión opcional del usuario actual; respetar unique/filtered indexes y collation institucional (no inspeccionada). | Pendiente. |
| `IUserRepository.AddAsync`, `SaveChangesAsync` | `users(username,email,first_name,last_name,employee_code,password_hash,is_active,deactivated_at,created_at,updated_at)` | INSERT/UPDATE parametrizados. User/role/assignment/audit en una transacción de aplicación. | Pendiente; hashing solo es contrato, no implementación. |
| `IRoleRepository.GetByCodeAsync`, `ListActiveForUserAsync`, `ReplaceActiveRoleAsync` | `roles`; `user_roles(user_id,role_id,assigned_by_user_id,assigned_at,revoked_at,is_active)` | Lectura por código y roles activos; reemplazo revoca roles activos (`is_active=0`, `revoked_at`) y añade el elegido en la misma transacción. | Pendiente. |
| `IUserBranchAssignmentRepository.ListForUserAsync`, `GetByIdAsync` | `user_branch_assignments` + `branches` | Listar por usuario orden `valid_from DESC`; cargar sucursal para `AssignmentDto`. | Pendiente; requisito de navegación no consta en todas las firmas. |
| `ListForOverlapCheckAsync`, `AddAsync`, `SaveChangesAsync` | `user_branch_assignments` y `branches`; `users` para actividad | Alta ordinaria valida usuario/sucursal activos, fechas y solapamientos, y audita dentro de la transacción existente. | Pendiente; estrategia de protección para alta ordinaria, incluido historial vacío, debe probarse con SQL Server autorizado. |
| `GetHistoryForTransferAsync`, `SaveTransferChangeAsync`, `AddTransferAssignmentAsync` | `user_branch_assignments(user_id,branch_id,valid_from,valid_until,status,assigned_by_user_id,reason,created_at,updated_at)` | Leer historia, determinar conflicto/branch anterior, cerrar actual, insertar nueva ACTIVE y auditar bajo un solo scope transaccional. | Pendiente de implementación ADO.NET; bloqueo SQL debe implementarse y probarse en Infrastructure. |
| `IBranchRepository.GetByIdAsync` | `branches` | Leer sucursal y `is_active` para validaciones de asignación/transferencia. | Pendiente. |
| `IVisitorRepository.GetByIdAsync`, `SearchAsync` | `visitors` y `visitor_types` | Listar orden `id ASC`; filtros activo/tipo; búsqueda nombre, apellido, normalizada, empresa y solo si autorizado email/teléfono; cargar tipo opcional. | Pendiente; `Visitor` no tiene `branch_id`. |
| `IdentificationExistsAsync`, `AddAsync`, `SaveChangesAsync` | `visitors(identification,identification_normalized,first_name,last_name,phone,email,company,visitor_type_id,is_active,created_at,updated_at)` | Comparación exacta sobre normalized no nulo; preservar ambas columnas y diferencia `null`/empty/whitespace; validar unique filtered index; visitante y auditoría en transacción. | Pendiente; VO requiere conversión a dos columnas y las reglas de Fase 2 siguen abiertas. |
| `IVisitorTypeRepository.GetByIdAsync` | `visitor_types(id,is_active)` | Leer tipo para validar existencia/actividad. | Pendiente. |
| `IVisitRepository.GetInBranchAsync`, `SearchInBranchAsync` | `visits`; joins `visitors`, `branches`, `visit_reasons`, `users` | Toda consulta debe filtrar `visits.branch_id` en SQL. Filtros opcionales estado/visitor/reason/fechas `[from,to)`/search. Orden `entry_at DESC,id DESC`, count y paginación. DTO requiere referencias completas. | Pendiente; el contrato exige aislamiento, pero mapeo/carga no está implementado. |
| `IVisitRepository.AddAsync`, `SaveChangesAsync` | `visits(visitor_id,branch_id,registered_by_user_id,entry_at,exit_at,reason_id,destination,visited_person,status,notes,completed_by_user_id,cancelled_by_user_id,cancelled_at,cancellation_reason,created_at,updated_at)` | Escribir solo campos definidos; crear estado ACTIVE con branch/actor del servidor; completar/cancelar solo desde ACTIVE; auditoría atómica. | Pendiente. |
| `IVisitReferenceReader.GetVisitorAsync`, `GetReasonAsync`, `GetBranchAsync`, `GetUserAsync` | `visitors`, `visit_reasons`, `branches`, `users` | Consultas por ID que suministran estado activo y navigations para crear/serializar visita. | Pendiente; `Notification` no participa. |
| `IAuditWriter.AppendAsync` | `audit_logs(actor_user_id,action,entity_type,entity_id,branch_id,old_values,new_values,ip_address,user_agent,correlation_id,created_at)` | INSERT únicamente; sin UPDATE/DELETE. Redacción y límites de longitudes se aplican antes del write. Mutación y audit en una transacción. | Pendiente. El esquema no impone append-only. |
| `IAuditReader.SearchAsync` | `audit_logs` | Filtros actor/action/type/entity/branch/fechas `[from,to)`; count/page; orden `created_at DESC,id DESC`. Es global con permiso exigido por Application. | Pendiente. |
| `ICatalogReader.ListBranchesAsync` | `branches` | Filtro de ID branch opcional, activo salvo include; `name,id` ascendente. Alcance ya autorizado por Application. | Pendiente. |
| `ListBranchTypesAsync`, `ListVisitorTypesAsync`, `ListVisitReasonsAsync`, `ListRolesAsync` | `branch_types`, `visitor_types`, `visit_reasons`, `roles` | Activos salvo include y orden `name,id`; API Python solo lee. Roles solicitados actualmente activos. | Pendiente. |
| `IDashboardReader.GetSummaryAsync` | `visits` | SQL aggregate: total, conteos ACTIVE/COMPLETED/CANCELLED, count distinct `visitor_id`; branch opcional y rango `[from,to)`. | Pendiente; mantener agregado en SQL, no materializar visitas. |
| `GetVisitsByDayAsync`, `GetVisitsByStatusAsync`, `GetVisitsByReasonAsync` | `visits`, join `visit_reasons` para motivo | Agrupar por fecha UTC/estado/motivo con orden Python existente. | Pendiente; dashboard diario UTC. |
| `IVisitReportReader.SearchAsync`, `GroupAsync` | `visits` + `visitors`, `branches`, `visit_reasons`, `users` | Detalle SQL-first con filtros branch/global, fechas, estado, motivo, visitante, registrador, búsqueda; orden/paginación; sin datos de contacto. Grupos status/reason/registered_by/branch. | Pendiente. |
| `BranchExistsAndIsActiveAsync`, `ReasonExistsAsync`, `VisitorExistsAsync`, `UserExistsAsync` | `branches`, `visit_reasons`, `visitors`, `users` | Existencia y actividad según operación; consulta por ID. | Pendiente. |
| `ITransactionRunner.ExecuteAsync` | Sin tabla propia | Mismo connection/transaction para comandos del delegado; commit al éxito, rollback ante excepción/cancelación; disponer recursos. | Pendiente; ADO.NET coordinator requerido. |
| `IClock`, `ICurrentUser`, `IPasswordHasher` | `users` solo para hash al alta | Reloj/identidad son adaptadores sin SQL; hash solo para `users.password_hash`. No hay verificación/login, JWT ni notificaciones en estos contratos. | Pendiente; implementaciones de seguridad fuera del alcance indicado. |

## 5. Correspondencia de 15 entidades y mapeo que deberá realizarse

La siguiente es la forma versionada del esquema conforme a SQLAlchemy y Alembic; no representa inspección de la base viva. Todas las PK son `BIGINT IDENTITY`; FK existentes usan `NO ACTION`. Los timestamps son `DATETIME2(3)` según modelos/migración; `TimestampMixin.updated_at` usa actualización ORM, no trigger.

| Entidad → tabla | Columnas principales; claves, nulabilidad, restricciones y relaciones |
| --- | --- |
| `BranchType` → `branch_types` | `code NVARCHAR(30)` único, `name NVARCHAR(100)`, `description NVARCHAR(500)?`, `is_active BIT` default true, `created_at`/`updated_at`; 1:N Branch. |
| `Branch` → `branches` | `code NVARCHAR(30)` único, `name NVARCHAR(200)`, `branch_type_id` FK required, `region NVARCHAR(100)?`, `address NVARCHAR(300)?`, `phone NVARCHAR(30)?`, `is_active`, timestamps; N:1 BranchType y relaciones a permisos/asignaciones/visitas/auditoría/notificaciones. |
| `User` → `users` | `username NVARCHAR(80)` único, `email NVARCHAR(254)?` unique filtrado, nombres `NVARCHAR(100)`, `employee_code NVARCHAR(50)?` unique filtrado, `password_hash NVARCHAR(255)`, `is_active`, `deactivated_at DATETIME2(3)?`, timestamps; varias relaciones a UserRole/UserPermission/Assignment/Visit/Audit/Notification. |
| `Role` → `roles` | `code NVARCHAR(50)` único, `name NVARCHAR(100)`, `description NVARCHAR(500)?`, `is_active`, timestamps; 1:N UserRole/RolePermission. |
| `UserRole` → `user_roles` | FK user/role/assigned_by required; `assigned_at`, `revoked_at?`, `is_active`, created/updated; índice único filtrado activo por user+role. |
| `Permission` → `permissions` | code(80) unique, name(120), resource/action(80), scope(20), description(500)?, active, timestamps; CHECK scope permite BRANCH o GLOBAL. |
| `RolePermission` → `role_permissions` | FK role/permission/assigned_by required; `assigned_at`, `is_active`; unique filtrado activo role+permission; sin created/updated. |
| `UserPermission` → `user_permissions` | FK user/permission/assigned_by required, branch nullable FK; effect(10), valid_from, valid_until?, active, created_at; CHECK effect permite ALLOW o DENY y valid_until > valid_from; índice lookup. |
| `UserBranchAssignment` → `user_branch_assignments` | FK user/branch/assigned_by required; valid_from, valid_until?, reason(500)?, status; created/updated; CHECK de fechas y estados permitidos ACTIVE, ENDED o CANCELLED; filtered unique de asignación activa abierta por usuario. |
| `Visitor` → `visitors` | `identification NVARCHAR(50)?`, `identification_normalized NVARCHAR(50)?`, nombres(100), phone(30)?, email(254)?, company(200)?, visitor_type_id nullable FK, active y timestamps; índice único filtrado en normalized no nulo; **sin branch_id**. |
| `VisitorType` → `visitor_types` | code(50) unique, name(100), description(500)?, active, timestamps; 1:N Visitor. |
| `Visit` → `visits` | visitor/branch/registered_by/reason FK required; `entry_at`, `exit_at?`, destination/visited_person(200)?, status(30), notes(1000)?, completed_by/cancelled_by/cancelled_at?/cancellation_reason(500)?, timestamps; checks estado/salida/datos cancelación; índices branch/status/time y visitor/time. |
| `VisitReason` → `visit_reasons` | code(50) unique, name(120), description(500)?, active, timestamps; 1:N Visit. |
| `AuditLog` → `audit_logs` | actor_user_id? FK, branch_id? FK, entity_id? sin FK, action(60), entity_type(80), old/new `NVARCHAR(MAX)?`, ip `VARCHAR(45)?`, user_agent(500)?, correlation_id(100)?, created_at; sin updated_at. |
| `Notification` → `notifications` | user_id FK required, branch_id? FK, title(200), message(1000), type(50), is_read default false, read_at?, related_entity_type(80)? y related_entity_id? **sin FK**, created_at; check read state; no updated_at. No flujo funcional Python/Application. |

La conversión de enums debe persistir exactamente texto mayúsculo: `VisitStatus` → `ACTIVE/COMPLETED/CANCELLED`; `PermissionScope` → `BRANCH/GLOBAL`; `PermissionEffect` → `ALLOW/DENY`; `UserBranchAssignmentStatus` → `ACTIVE/ENDED/CANCELLED`. No debe usarse `SqlDbType.Int` ni `Enum.ToString()` sin conversión explícita.

`VisitorIdentification` requiere guardar y leer simultáneamente las columnas `identification` y `identification_normalized`. Application conserva las diferencias de `null`, cadena exactamente vacía y espacios; el Domain VO no es una columna SQL y el mapeo relacional aún no existe.

## 6. Conexiones, transacciones y concurrencia: Infrastructure pendiente

### Conexiones

Se evaluó `Microsoft.Data.SqlClient` como proveedor ADO.NET compatible con el proyecto net10.0. No se añadió porque Infrastructure no se implementa en esta corrección. Cuando se autorice, la propuesta es centralizar:

- Una factoría/administrador de conexiones que recibe configuración externa y crea `SqlConnection` sin almacenar secretos versionados.
- Un contexto/runner de transacción que abre **una** conexión por operación, inicia `SqlTransaction`, comparte ambos con todos los repositorios del delegado y asegura commit/rollback/dispose.
- Adaptadores que reciben la conexión/transaction contextual; no crear conexiones arbitrariamente por cada comando si la operación requiere atomicidad.
- Un método de composición DI de Infrastructure. No hay activación ni conexión automática mientras no se registre/configure el proveedor en una fase aprobada.

Este diseño es una recomendación; ningún componente se creó ni se abrió conexión durante esta revisión.

### Transferencia y alta de asignación

Python `transfer_user` selecciona historial de `user_branch_assignments` con hint `WITH (UPDLOCK, HOLDLOCK)`, modifica el intervalo anterior, inserta el nuevo y registra auditoría en la misma transacción; hace rollback ante excepciones. En SQL Server `HOLDLOCK` implica semántica serializable para la referencia, mientras el alcance de los rangos protegidos depende de predicado, índice y plan de acceso.

La transferencia ADO.NET futura deberá mantener una transacción explícita en la misma conexión, hacer el `SELECT` del historial con los hints exactos y ejecutar lectura, validación, cierre, inserción y auditoría antes de commit. Application pasa el scope opaco a la lectura, el cierre, el alta y al `IAuditWriter.AppendAsync`; Infrastructure debe vincular cada uno a ese mismo scope y no realizar una lectura por conexión independiente.

La creación Python usa `.with_for_update()` en el historial dentro de la transacción; eso no demuestra por sí solo qué SQL/hint o bloqueo de rango se obtuvo en el motor SQL Server. El índice filtrado único solo impide más de una asignación abierta ACTIVE por usuario; no prohíbe todos los solapamientos históricos. Infrastructure debe validar el comportamiento con SQL Server en una fase autorizada, especialmente con historial vacío. Application ofrece `ExecuteWithTransactionAsync` para transferencia; no se afirma garantía real de concurrencia hasta implementar y probar Infrastructure.

## 7. UTC y mapeo temporal pendiente

SQL `DATETIME2(3)` no conserva `DateTime.Kind` ni offset. Python convierte valores aware a UTC naive antes de escribir/comparar; valores naive se interpretan como UTC en las rutas/servicios auditados. `SYSUTCDATETIME()` proporciona defaults server-side y `updated_at` tiene `onupdate` de ORM.

Futura infraestructura deberá:

1. Leer `DateTime` SQL como instante UTC por convención y devolverlo al Domain como `DateTimeKind.Utc` (o convención equivalente documentada).
2. Antes de persistir, normalizar a UTC y tratar la precisión de milisegundos de `DATETIME2(3)` de manera consistente.
3. Usar defaults server-side ya existentes, no crear defaults/esquema nuevo; coordinar cuándo Application establece timestamps explícitos.
4. Evitar asumir que una fecha recuperada de SQL Server tiene `Kind=Utc` automáticamente.

No se ejecutaron lecturas para probar este comportamiento.

## 8. Paquetes, pruebas y arquitectura actual

- El `.csproj` actual de Infrastructure solo referencia Application y Domain. `Microsoft.Data.SqlClient` no está añadido ni instalado por esta fase detenida.
- No se usó EF Core ni se añadió mecanismo de migraciones .NET.
- No se añadieron tests de Infrastructure porque los adaptadores aún no están implementados.
- Tras la corrección de Application se ejecutó `dotnet build` correctamente y `dotnet test` aprobó 50/50; las cinco pruebas nuevas son unitarias con dobles y no son pruebas de Infrastructure/SQL Server.
- Los dobles xUnit existentes son unitarios y no prueban SQL Server, `UPDLOCK/HOLDLOCK`, DDL, índices filtrados, collation, transacciones ADO.NET o rollback del servidor.

## 9. Contratos implementados y pendientes

| Grupo | Contratos de Application | Estado en Infrastructure | Motivo / próximo requisito |
| --- | --- | --- | --- |
| Conexión/ADO.NET | No existe todavía interfaz de fábrica SqlClient en Application (correctamente, pues no debe conocer el proveedor). | **No implementado** | Definir factoría y runner que implementen scope transaccional compartido; configuración externa sin secretos. |
| Usuarios/roles | `IUserRepository`, `IRoleRepository`, `IBranchRepository` | **No implementado** | Mapear columnas/navegaciones, uniqueness/collation y reemplazo de rol transaccional. |
| Permisos | `IPermissionDataSource`, `IBranchAssignmentReader` | **No implementado** | Cargar cuatro tablas y mapear enum textualmente; devolver todos los matches de asignación. |
| Asignaciones | `IUserBranchAssignmentRepository` | **No implementado** | Implementar lectura protegida y escrituras enlazadas al scope común; transfer Application ya no hace pre-read. |
| Visitantes | `IVisitorRepository`, `IVisitorTypeRepository` | **No implementado** | Mapear VO a dos columnas; filtros contacto; eager load de tipo; índice filtered. |
| Visitas | `IVisitRepository`, `IVisitReferenceReader` | **No implementado** | Scope branch en SQL; navs y campos FK exactos; UTC/state text. |
| Auditoría | `IAuditWriter`, `IAuditReader` | **No implementado** | Insert-only en adapter, orden/filtros; transacción conjunta. Schema no impone inmutabilidad. |
| Catálogos | `ICatalogReader` | **No implementado** | Queries read-only ordenadas por `name,id`, estado activo. |
| Dashboard | `IDashboardReader` | **No implementado** | Agregaciones SQL; scope y día UTC. |
| Reportes | `IVisitReportReader` | **No implementado** | Projection SQL-first sin contacto, filtros/existencia, paginación/agregación. |
| Notificaciones | Ninguno | **Fuera de alcance** | Tabla/entidad sin flujo funcional confirmado en Python ni contrato Application. |
| Login/JWT/Argon2 verify | No hay contrato de verificación/login en Application; solo `IPasswordHasher.Hash`. | **Fuera de alcance** | No implementar según restricciones de Fase 4. |

## 10. Riesgos y diferencias que deben conservarse

1. **Lock real pendiente:** la corrección Application define el orden/scope, pero no implementa ni certifica los hints/aislamiento de SQL Server.
2. **Carga de navegación no formalizada:** los DTO mappers fallan o representan incompletamente datos si adapter no carga Role/Branch/VisitorType/Visit references. Aclarar contrato antes de afirmar cobertura completa.
3. **Mapeo de enums:** las restricciones SQL solo aceptan los códigos uppercase exactos.
4. **Identificación:** original y normalized son dos columnas; no normalizar input otra vez en Infrastructure ni perder null/empty distinction.
5. **Locks de asignación nueva:** SQLAlchemy `with_for_update()` no demuestra paridad con SQL Server y debe validarse en ambiente controlado futuro.
6. **Auditoría append-only:** contrato no expone update/delete pero SQL no previene modificaciones por otra credencial/consulta. Infra debe restringir lo que implemente; no puede certificar inmutabilidad total del servidor.
7. **Collation/únicos:** la collation real no fue consultada; igualdad/capitalización puede depender del ambiente.
8. **Downgrade ya existente:** la segunda revisión de Alembic revierte a default literal incorrecto en downgrade; no se cambia ni ejecuta aquí.
9. **Hashes/login:** `IPasswordHasher` no verifica hashes heredados. No existe contrato que permita login equivalente y no se debe inferir.
10. **Notificaciones:** no crear tabla ni flujo; la tabla ya existe, pero no hay operaciones funcionales Python ni contrato .NET.

## 11. Recomendaciones priorizadas

### Bloqueante

- No quedan cambios bloqueantes adicionales identificados en el código Application para esta corrección. El bloqueo previo se resolvió según §14; Infrastructure sigue sin implementar.

### Alta, antes de terminar adapters

- Formalizar eager-load requirements de las operaciones que mapean DTOs.
- Resolver cómo Application consumirá el resultado del transfer (branch anterior/nuevo y conflicto) desde la operación atómica.
- Definir conversiones enum y mapping de `VisitorIdentification` con tests aislados de serialización/mapeo.

### Media, durante implementación posterior autorizada

- Diseñar el ámbito de conexión/`SqlTransaction` compartido y rollback.
- Añadir tests de comandos parametrizados y fake ADO abstractions; no confundirlos con integración real.
- Planificar pruebas SQL Server autorizadas para rango vacío, locks, índice filtered y concurrencia antes de afirmar paridad.

### Baja / documentación

- Documentar el contrato temporal UTC/`DATETIME2(3)` y defaults de servidor.
- Mantener la lista de eventos de auditoría alineada con el código actual (incluye `UPDATE_VISIT`).

## 12. Próximo paso recomendado

Revisar y autorizar esta corrección controlada. En una fase posterior implementar Infrastructure con ADO.NET y `Microsoft.Data.SqlClient`, garantizando que el scope opaco use una única conexión/transacción y que el read transfer utilice `UPDLOCK, HOLDLOCK`. No conectar a producción ni tocar Alembic/esquema sin autorización separada.

## 13. Declaración de alcance

La auditoría inicial de este informe fue de solo lectura. En la corrección controlada posterior se modificaron `dotnet/src/SeNaSaVisits.Application/Interfaces/Transactions.cs`, `Users.cs` y `Audit.cs`; `Services/UserManagementService.cs` y `AuditService.cs`; dobles/pruebas de transferencia en `dotnet/tests/SeNaSaVisits.UnitTests/`; y este informe. **No se modificó Infrastructure, Domain, Python, frontend o Alembic. No se instaló ningún paquete; no se ejecutaron migraciones, seeds ni scripts; no se modificó el esquema y no se conectó ni ejecutó operaciones de lectura/escritura contra SQL Server.**

## 14. Corrección controlada del flujo de transferencia (Application)

### Problema original y causa

La primera versión de `TransferAsync` obtenía `ListForOverlapCheckAsync` antes de abrir `ITransactionRunner`. Usaba esa lista para detectar asignaciones múltiples o la misma sucursal y reutilizaba el valor leído para `old_branch_id`. El repositorio atómico volvía a consultar bajo su operación protegida, pero esa lectura no era la fuente de las decisiones ni del evento auditado. La ventana entre ambas lecturas permitía decisiones o auditoría obsoletas.

### Corrección y cambios mínimos de contrato

Application ahora ejecuta la transferencia con `ITransactionRunner.ExecuteWithTransactionAsync`, que entrega un `IApplicationTransaction` opaco. La interfaz no expone conexión ni tipos del proveedor; declara que Infrastructure debe enlazar el scope a la misma conexión y transacción durante todo el delegado.

En `IUserBranchAssignmentRepository`, la operación compuesta `TransferAtomicallyAsync` se reemplazó por tres pasos que reciben ese mismo scope:

1. `GetHistoryForTransferAsync`: leer el historial protegido dentro del scope, sin abrir otra conexión, con bloqueo equivalente a `UPDLOCK`/`HOLDLOCK` implementado por Infrastructure.
2. `SaveTransferChangeAsync`: persistir el cierre de la asignación vigente dentro del mismo scope.
3. `AddTransferAssignmentAsync`: insertar la nueva asignación dentro del mismo scope.

El evento `MOVE_USER_BRANCH` pasa también el scope a `IAuditWriter.AppendAsync`, por lo que la interfaz permite que Infrastructure lo inserte en la misma transacción; no basta con que el servicio de auditoría se invoque antes del commit.

El historial devuelto es ahora la única fuente para decidir conflicto y capturar `old_branch_id`. Validación, cierre, alta y append del evento de auditoría se ejecutan dentro del callback transaccional. `ITransactionRunner` debe confirmar solo al éxito y hacer rollback ante excepción o cancelación. No se incluyó SQL en Application.

### Nuevo orden

`begin transaction → locked history read → conflict checks and old_branch_id capture → close current assignment (if any) → overlap check → insert new assignment → append audit using same transaction scope → commit`. Cada operación recibe el scope opaco de la transacción; no hay lectura de historial previa.

### Pruebas añadidas/adaptadas

`TransferTransactionOrderingTests` registra el orden de eventos y comprueba que las llamadas de historial, cierre y alta reciben exactamente el mismo scope activo. Incluye fallo inyectado en lectura, cierre y alta para verificar rollback y ausencia de commit. También prueba conflicto de misma sucursal, y verifica que el valor anterior auditado proviene del historial protegido. La prueba previa `UserAssignmentUseCaseTests` se adaptó al nuevo contrato.

### Resultado y responsabilidades pendientes

La compilación de la solución y la suite completa se ejecutaron después de esta corrección; el resultado final se consigna en la respuesta de esta entrega. Las pruebas usan dobles y demuestran el orden contractual, no la existencia real de locks, una conexión ADO.NET compartida, ni rollback de SQL Server.

Infrastructure deberá implementar el scope sobre una sola conexión/`SqlTransaction`, `UPDLOCK, HOLDLOCK` en la lectura completa de historial (incluido el caso sin filas), comandos de cierre/alta/auditoría enlazados a esa transacción y commit/rollback/dispose. Hasta probarlo en un SQL Server de pruebas autorizado, **no se afirma garantía real de concurrencia SQL Server**. No se implementó Infrastructure, no se instaló `Microsoft.Data.SqlClient` y no se alteraron esquema o migraciones.
