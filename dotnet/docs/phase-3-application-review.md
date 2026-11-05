# Revisión de implementación — Fase 3 Application

**Proyecto:** SeNaSaVisits  
**Alcance:** contratos, DTOs, validaciones y casos de uso en `SeNaSaVisits.Application`  
**Fecha:** 2026-11-05

## 1. Resumen ejecutivo

Se implementó una capa Application independiente de Infrastructure y API. Sus puertos exponen acceso a usuarios/roles/asignaciones, permisos, sucursales, visitantes, visitas, auditoría, catálogos, dashboard y reportes. Los servicios de aplicación orquestan las operaciones y devuelven DTOs, no entidades como respuesta funcional.

Se trasladaron a Application las reglas comprobables de autorización `DENY > ALLOW > RolePermission`, alcance `GLOBAL`/`BRANCH`, verificación de asignación vigente única y sucursal activa, filtros de visitas por la sucursal resuelta, privacidad de contacto, transiciones de visita, redacción/auditoría, filtros de reportes y consultas agregadas mediante puertos. `ITransactionRunner` define límites transaccionales y el contrato de transferencia exige que Infrastructure implemente bloqueo equivalente a `UPDLOCK, HOLDLOCK`.

Validación ejecutada: **`dotnet build` exitoso; `dotnet test` exitoso con 45 pruebas aprobadas, 0 fallidas**. Domain permanece sin paquetes NuGet; Application solo referencia Domain. No hay repositorios concretos ni mapeo EF Core, autenticación/JWT, Argon2, controladores ni integración con SQL Server. Por tanto **no se afirma compatibilidad productiva**.

**Estado:** Application permite continuar con revisión de esta fase, pero la persistencia requiere completar y probar los contratos de Infrastructure, y cerrar la interoperabilidad de identificación/enums/UTC indicada en la revisión de Fase 2. Esta entrega no avanza a Infrastructure ni a una siguiente fase.

## 2. Servicios y casos de uso implementados

Los servicios de módulo son los orquestadores de casos de uso; los puertos (`Interfaces`) definen lo que deberán proporcionar futuras implementaciones de Infrastructure.

| Componente | Operaciones y comportamiento |
| --- | --- |
| `PermissionService` | Resuelve usuario y permiso activos; evalúa alcance; verifica branch propio para permisos BRANCH; filtra grants directos por vigencia y `BranchId`; aplica DENY primero, ALLOW después y consulta roles activos solo si no existe efecto directo aplicable. Expone comprobación y exigencia de permiso. |
| `BranchAccessService` | Obtiene asignaciones `ACTIVE` vigentes, exige exactamente una y que la sucursal esté activa. El branch es derivado del usuario autenticado; puede devolver contexto o denegar. |
| `UserManagementService` | Buscar/listar y obtener usuarios; crear, actualizar, activar/desactivar; devolver roles activos e historial de asignaciones; asignar sucursal; reemplazar el rol activo; transferir sucursal mediante un contrato atómico/transaccional. Incluye unicidad, actividad, fechas, solapamiento y eventos de auditoría. |
| `VisitorManagementService` | Buscar/listar, detalle, crear, actualizar y activar/desactivar visitantes. Exige contexto y permisos branch. Decide búsqueda/serialización de teléfono y email con `VIEW_VISITOR_CONTACT`; calcula máscara de contacto/identificación y aplica identificación normalizada del Domain. |
| `VisitManagementService` | Buscar/listar, detalle, crear, modificar, completar y cancelar visitas. Todas las lecturas/escrituras llevan branch resuelto; crea usando usuario/sucursal del contexto, valida referencias activas y estados, finaliza con hora del reloj cuando falta `exit_at`. |
| `AuditService` | Crea y añade registros append-only; valida longitudes, trunca metadatos y redacta claves sensibles recursivamente antes de serializar JSON determinista. No expone operación de modificar/eliminar. |
| `AuditQueryService` | Exige `VIEW_AUDIT_LOGS` global, valida filtros/paginación/fechas y vuelve a redactar `old_values`/`new_values` al leer. El puerto declara orden `CreatedAt DESC, Id DESC`. |
| `CatalogService` | Listados de solo lectura para sucursales, tipos de sucursal, tipos de visitantes, motivos y roles; reproduce alternativas de permisos globales/branch e inclusión de inactivos. |
| `DashboardService` | Resumen, serie por día UTC y distribuciones por estado/motivo; resuelve alcance global o sucursal y valida rango inclusivo/exclusivo. Los agregados quedan delegados a una consulta de lectura de Infrastructure, no carga entidades completas. |
| `VisitReportService` | Detalle paginado y agrupación por `status`, `reason`, `registered_by`, `branch`; valida referencias/filtros, aplica alcance y no expone contacto. Global puede filtrar sucursal activa; sucursal no puede ampliar su alcance. |

No se trasladó `login`, `me` ni emisión/verificación de tokens. `IPasswordHasher` es solamente un puerto para alta de usuarios y no implementa hash alguno. No se crearon casos de uso de refresh/logout, notificaciones, permisos administrativos inexistentes por API, exportaciones, citas ni pre-registro.

## 3. Interfaces y contratos

### Tiempo e identidad

- `IClock` entrega el instante UTC actual como `DateTime`; `ApplicationTime.ToUtc` convierte valores locales y considera naive/unspecified como UTC, siguiendo la convención Python.
- `ICurrentUser` entrega el ID confiable del actor. Las operaciones no reciben identidad como dato autorizado desde el DTO.
- `IPasswordHasher` es únicamente una abstracción sin dependencia de Argon2 ni implementación.
- `ITransactionRunner` ofrece el límite para ejecutar operaciones de aplicación en una transacción; no proporciona locks por sí mismo.

### Persistencia/lectura requerida

- `IPermissionDataSource`, `IBranchAssignmentReader`, `IUserRepository`, `IRoleRepository`, `IUserBranchAssignmentRepository`, `IBranchRepository`.
- `IVisitorRepository`, `IVisitorTypeRepository`, `IVisitRepository`, `IVisitReferenceReader`.
- `IAuditWriter` (solo `AppendAsync`) y `IAuditReader`.
- `ICatalogReader`, `IDashboardReader`, `IVisitReportReader`.

Las interfaces describen filtros, órdenes y requisitos de carga; el cumplimiento efectivo depende de Infrastructure. En particular, `IVisitRepository.GetInBranchAsync` y `SearchInBranchAsync` exigen que el proveedor filtre por sucursal en la consulta de datos, no después de cargar resultados.

`IUserBranchAssignmentRepository.TransferAtomicallyAsync` declara operación atómica para cerrar/crear intervalos. `ListForOverlapCheckAsync` debe llamarse dentro de `ITransactionRunner` y bloquear historial en alta; transferencia debe reproducir el nivel de protección del Python `UPDLOCK, HOLDLOCK`. Estos contratos **no prueban ni implementan concurrencia**.

## 4. DTOs y validaciones

Los DTOs están separados en archivos por responsabilidad:

- Usuarios: búsquedas/paginación, alta/actualización, asignación/transferencia y respuestas con roles y asignación vigente; no se expone `PasswordHash`.
- Visitantes: create/update, filtros/paginación, tipo y respuesta; `identification_normalized` no se expone.
- Visitas: creación/edición/completar/cancelar, filtros y respuesta con referencias; las entradas no contienen `BranchId`, actor o status asignados por cliente.
- Auditoría: filtros/paginación y campos de lectura.
- Catálogos, dashboard y reportes: item/agregados/proyección de detalle sin teléfono/correo.
- `FieldUpdate<T>` diferencia campo omitido de null explícito para PATCH.

Validaciones incorporadas incluyen longitud de búsqueda/paginación, longitudes de campos, email de visitante, nombres requeridos normalizados, motivo de cancelación, estado, intervalo temporal, referencias activas, unicidad de identificación consultada, fechas UTC y límite superior exclusivo. `ApplicationNotFoundException`, `ApplicationConflictException`, `ApplicationValidationException` y `ApplicationForbiddenException` evitan introducir códigos HTTP en Application; el mapeo HTTP queda para la API en otra fase.

## 5. Reglas de autorización y sucursal

### Permisos

1. Usuario o permiso inactivo/missing deniega.
2. `GLOBAL` solo se evalúa con `branchId == null`.
3. `BRANCH` requiere un branch solicitado, asignación vigente única y sucursal activa; la sucursal debe coincidir con el contexto resuelto del usuario.
4. Solo aplican `UserPermission` activo, dentro de `[ValidFrom, ValidUntil)`, y cuyo `BranchId` coincide con el scope: null para GLOBAL, sucursal exacta para BRANCH.
5. Si existe algún `DENY` directo aplicable, deniega; si no existe DENY y hay `ALLOW`, permite; solo sin efecto directo consulta grant efectivo de roles activos (`UserRole`, `Role`, `RolePermission`).

La fuente de datos debe devolver los grants directos del usuario/permiso y el servicio revalida vigencia/scope. El puerto de role grant declara explícitamente que solo considera asociaciones activas.

### Aislamiento

- `ICurrentUser.UserId` es la fuente de identidad. Los casos de visita y visitante resuelven sucursal en servidor.
- No se acepta branch del cliente para crear visita ni para leer/modificar visitas.
- Cada método del repositorio de visita recibe `branchId` como parte obligatoria del alcance; recurso de otra sucursal debe aparecer como ausente.
- Los perfiles Visitor siguen siendo globales según la tabla existente, aunque acceder a la funcionalidad requiera permiso/contexto branch.
- Dashboard/reportes seleccionan global o branch según permisos efectivos. Solo el filtro global puede indicar una sucursal activa.

## 6. Auditoría y privacidad

Nombres de eventos portados desde flujos actuales de mutación: `CREATE_USER`, `UPDATE_USER`, `DEACTIVATE_USER`, `ASSIGN_USER_BRANCH`, `MOVE_USER_BRANCH`, `CREATE_VISITOR`, `UPDATE_VISITOR`, `CREATE_VISIT`, `UPDATE_VISIT`, `CHECKOUT_VISIT`, `CANCEL_VISIT`. `LOGIN` no se genera en Application porque el caso de login está excluido en esta fase.

La redacción reconoce las claves `password`, `password_hash`, `token`, `access_token`, `refresh_token`, `authorization`, `secret`, `api_key`, `credentials`, normalizando mayúsculas/guion/underscore, y procesa mappings/listas anidados. Los DTOs de visita/reporte no incluyen teléfono/email; identificación se enmascara para visitantes, visitas y reportes. Se omiten del evento de actualización del visitante teléfono, email y tipo, igual que el código Python revisado.

`IAuditWriter` solo permite append. Esto es un límite del contrato, no una garantía de almacenamiento: Infrastructure debe insertar sin endpoints/operaciones update/delete y la seguridad del esquema/credenciales debe revisarse por separado.

## 7. Pruebas y resultados

Se añadieron pruebas xUnit en `dotnet/tests/SeNaSaVisits.UnitTests/Application/` para:

- Precedencia DENY/ALLOW/RolePermission, scopes GLOBAL/BRANCH, actividad y límites de vigencia.
- Resolución de sucursal sin asignación, vencida, inactiva, duplicada, inicio inclusivo y fin exclusivo.
- Búsqueda de visitantes que suprime los filtros de contacto sin permiso y los permite con el permiso; máscaras de respuesta.
- Normalización de identificación, guiones, espacios y entrada exactamente vacía conforme a la lógica de create del servicio Python.
- Alta/asignación con intervalos adyacentes, conflicto por solapamiento y delegación de transferencia al puerto atómico.
- Crear/leer/finalizar/cancelar visitas, branch scope, usuario/sucursal derivados, fallback del reloj y razón normalizada.
- Redacción recursiva de auditoría, re-redacción histórica y metadatos.
- Scope de dashboard/reporte, límite de fecha exclusivo, branch filter y grouping global.

**Resultado:** `dotnet build .\dotnet\SeNaSaVisits.sln` correcto; `dotnet test .\dotnet\SeNaSaVisits.sln` correcto: **45 total, 45 aprobadas, 0 fallidas, 0 omitidas**. Son tests unitarios con dobles; no prueban SQL Server, locks, transacciones reales, índices filtrados o traducción de consultas.

## 8. Funcionalidades pendientes

- Login, `GET /auth/me`, autenticación Bearer/JWT, verificación de credenciales, emisión/renovación/logout y hash real Argon2. No se implementaron por el alcance explícito de Fase 3.
- Implementaciones concretas de puertos, `DbContext`, repositorios, SQL Server, transacciones, locks/aislamiento y traducciones de enums/VO a columnas.
- Adaptador `ICurrentUser` y origen seguro de `AuditContext` desde request; mapeo de excepciones Application a contratos HTTP.
- Escritura administrativa de permisos/RolePermission y roles fuera del flujo de reemplazo de rol existente.
- Notificaciones, citas, pre-registro, exportaciones u operaciones no presentes en el contrato actual.
- Pruebas de paridad con los 278 casos Python, contratos HTTP y pruebas de integración SQL Server.

## 9. Discrepancias detectadas y decisiones de portación

1. **Guiones de identificación:** documentación antigua dice que se eliminan; el código Python y sus pruebas los conservan. Se conserva el comportamiento del código. El Domain usa `char.IsWhiteSpace`/`ToUpperInvariant`; diferencias Unicode frente a regex/upper Python requieren tests de paridad.
2. **Identificación vacía:** create Python convierte string exactamente vacío a `None`; una cadena de espacios es truthy y termina con identificación original vacía y normalizada `None`. Application reproduce esa diferencia en `FromPythonInput`; el mapeo a dos columnas permanece para Infrastructure.
3. **PATCH de visitante con null en phone/company:** el DTO Python acepta null pero el servicio usa `.strip()` y puede provocar un 500. Application rechaza explícitamente ese null con error de validación en vez de conservar el fallo accidental. Es una desviación deliberada para no trasladar una excepción no controlada; requiere decisión de contrato antes de API.
4. **PATCH de usuario con null:** el servicio Python ignora null para campos opcionales, no los usa para limpiar. Application mantiene ese no-op.
5. **`branch-types?include_inactive=true`:** el endpoint Python no ejecuta comprobación adicional para `include_inactive`, pero la dependencia ya requiere `MANAGE_BRANCHES` global. Application preserva ese requisito existente sin una segunda evaluación.
6. **Asignación/transferencia:** la regla de solapamiento en Python es de servicio y usa locks. Application valida intervalos y crea contrato transaccional; no afirma prevenir carreras hasta que Infrastructure implemente bloqueo y pruebas de SQL Server.
7. **Finalización:** Python acepta exit_at opcional y utiliza ahora UTC si falta; el Domain C# requiere instante. Application proporciona su `IClock` UTC.
8. **Auditoría de login:** el único evento no implementado en esta fase es `LOGIN`, porque no se portó autenticación.
9. **Lista de eventos en Fase 0:** el resumen de Fase 0 omite `UPDATE_VISIT` de su lista, pero el servicio Python de visitas registra ese evento. Application lo incluye conforme al código fuente.
10. **Redacción de tuplas:** Python `_redact` recorre mappings y listas; Application recorre mappings y cualquier secuencia enumerable no-string (incluidas tuplas/arreglos). La versión C# puede redactar algunas estructuras adicionales; no debilita la protección.
11. **README Python/Clean Architecture:** Python services consultan SQLAlchemy directamente pese al diseño de interfaces descrito por README. Application .NET define puertos nuevos sin copiar ese acoplamiento.
12. **Fase 2:** no se cambiaron entidades. Siguen pendientes las advertencias de mapeo enum string, doble columna de identificación, UTC/precisión y nav required de [la revisión Fase 2](phase-2-domain-review.md).

## 10. Archivos creados y modificados

### Creados en `dotnet/src/SeNaSaVisits.Application`

- `Common/ApplicationExceptions.cs`, `Common/Paging.cs`, `Common/ApplicationTime.cs`.
- `Interfaces/TimeAndIdentity.cs`, `Authorization.cs`, `Users.cs`, `Visitors.cs`, `Visits.cs`, `Audit.cs`, `ReadModels.cs`, `Transactions.cs`.
- `DTOs/Users.cs`, `Visitors.cs`, `Visits.cs`, `Audit.cs`, `ReadModels.cs`.
- `Validators/InputValidators.cs`.
- `Services/BranchAccessService.cs`, `PermissionService.cs`, `UserManagementService.cs`, `VisitorManagementService.cs`, `VisitManagementService.cs`, `AuditService.cs`, `AuditQueryService.cs`, `CatalogService.cs`, `DashboardService.cs`, `VisitReportService.cs`.

### Creados en pruebas

- `Application/AuthorizationAndBranchAccessTests.cs`
- `Application/VisitorApplicationRulesTests.cs`
- `Application/VisitApplicationTests.cs`
- `Application/UserAssignmentUseCaseTests.cs`
- `Application/AuditRedactionTests.cs`
- `Application/DashboardAndReportUseCaseTests.cs`

### Modificados

- `Interfaces/Users.cs`, `Interfaces/Authorization.cs`, `Interfaces/Visits.cs`, `Interfaces/ReadModels.cs`, `Interfaces/Audit.cs`.
- `DTOs/Audit.cs`.
- `Services/UserManagementService.cs`, `VisitorManagementService.cs`, `VisitManagementService.cs`, `AuditService.cs`, `VisitReportService.cs`, `CatalogService.cs`, `DashboardService.cs`.
- `Validators/InputValidators.cs`.

No se modificaron `SeNaSaVisits.Application.csproj`, `Domain`, Infrastructure, API, `.sln` o dependencias.

## 11. Dependencias y revisión de arquitectura

- `SeNaSaVisits.Application.csproj` conserva solo referencia a `SeNaSaVisits.Domain`.
- No se añadieron paquetes NuGet.
- Application no referencia Infrastructure ni API; no hay referencias circulares en el grafo existente.
- Los casos de uso no dependen de FastAPI, SQLAlchemy, EF Core, `DbContext`, SQL Server, JWT ni Argon2.
- El puerto `IPasswordHasher` permite desacoplar alta de usuarios, pero no se proporciona algoritmo.

## 12. Conclusión

La capa Application ya contiene contratos y coordinación para las operaciones principales de usuarios/asignaciones, visitantes, visitas, autorización, sucursales, auditoría, catálogos, dashboard y reportes. Se puede revisar esta fase como capa de casos de uso **sin implementación productiva de persistencia**.

La garantía de operación real queda condicionada a Infrastructure: mapeo exacto de IDs/timestamps/enums/identificación, carga de navegaciones para DTO, semántica SQL, transacciones compartidas y bloqueo de asignaciones. Los 45 tests no constituyen certificación de SQL Server. No avanzar hasta que la revisión de esta fase sea aceptada.

### Declaración de alcance

Solo se editaron archivos .NET bajo `dotnet/src/SeNaSaVisits.Application`, tests xUnit y este informe. No se modificó ningún archivo Python, frontend, modelo de Domain, Alembic o esquema; no se instalaron paquetes; no se ejecutaron scripts/seeds/migraciones; no se conectó ni escribió en SQL Server. No se implementaron repositorios, API controllers, JWT, Argon2 ni notificaciones. No se avanzó a Infrastructure ni a la fase siguiente.
