# SeNaSa Visits API (Backend)

Backend del sistema web institucional de gestión y registro de visitas de SeNaSa.
Proyecto **independiente** del frontend (React + Vite); no comparte archivos ni configuración con él.

> **Estado actual:** API implementada para autenticación JWT, autorización y aislamiento por
> sucursal, usuarios, visitantes, visitas, auditoría, Dashboard y Reportes. Notificaciones y
> citas/pre-registro no forman parte del contrato actual. Ver [docs/backend-description.md](docs/backend-description.md)
> para el contrato de integración y el procedimiento de primera instalación.

## 1. Qué es el proyecto

API REST para el registro y consulta de visitas institucionales de SeNaSa, con soporte
para múltiples sucursales/puntos de servicio. Una regla de negocio central es que
**un usuario asignado a una sucursal no puede consultar,
modificar ni eliminar información de otra sucursal**; esta restricción se aplicará en el
backend, no solo en el frontend.

## 2. Tecnologías utilizadas

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2.x (ORM)
- Alembic (migraciones)
- Pydantic / Pydantic Settings
- SQL Server (motor final) vía PyODBC
- PyJWT (tokens JWT de autenticación)
- pwdlib (hashing seguro de contraseñas)
- Pytest + httpx (pruebas)

## 3. Arquitectura

Arquitectura inspirada en **Clean Architecture**, con responsabilidades separadas en capas:

```
app/
├── domain/          # Entidades, enums y contratos de repositorio (sin dependencias externas)
├── application/     # Casos de uso, DTOs, interfaces y validadores
├── infrastructure/  # SQLAlchemy, repositorios concretos, autenticación, servicios externos
├── api/              # Routers, middlewares y dependencias de FastAPI
└── core/            # Configuración centralizada, excepciones y seguridad transversal

migrations/          # Alembic y revisiones aplicadas
tests/               # Pruebas con pytest
main.py              # Punto de entrada de la aplicación FastAPI
```

La capa `domain` no depende de ninguna otra. `application` depende solo de `domain`.
`infrastructure` implementa los contratos definidos en `domain`/`application`. `api` orquesta
todo mediante inyección de dependencias de FastAPI.

## 4. Requisitos para ejecutarlo

- Python 3.11 o superior
- Driver ODBC de SQL Server instalado (por ejemplo, "ODBC Driver 17/18 for SQL Server")
- Acceso a una instancia de SQL Server con la base de datos `SeNaSaVisitsDB` creada

## 5. Crear el entorno virtual

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 6. Instalar dependencias

```powershell
pip install -r requirements.txt
```

## 7. Configurar `.env`

Copia `.env.example` a `.env` y completa los valores reales (nunca subas `.env` a Git):

```powershell
Copy-Item .env.example .env
```

Variables principales:

- `DATABASE_URL`: cadena `mssql+pyodbc` desde `.env`; en desarrollo local se usa `odbc_connect` con Shared Memory y autenticación Windows
- `JWT_SECRET_KEY`: clave secreta para firmar JWT (cámbiala en producción)
- `CORS_ORIGINS`: lista separada por comas de orígenes exactos permitidos (por defecto localhost y 127.0.0.1 en 8443 y localhost:5173). Para un origen de pruebas o red local, agrégalo explícitamente, p. ej. `CORS_ORIGINS=http://localhost:5173,http://192.168.1.50:8443`; `*` se rechaza. `CORS_ALLOW_CREDENTIALS` es `false` por defecto (se usa Bearer, no cookies)
- `ENVIRONMENT`: `development`, `testing` o `production`. Con `production`, `JWT_SECRET_KEY` de menos de 32 caracteres impide el arranque

## 8. Iniciar FastAPI

```powershell
uvicorn main:app --reload
```

 La API quedará disponible en [http://localhost:8000](http://localhost:8000).

## 9. Acceder a Swagger / ReDoc

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Verificación de API: `GET http://localhost:8000/api/health`
- Verificación de API y base de datos: `GET http://localhost:8000/api/health/db`
- Login: `POST http://localhost:8000/api/auth/login`
- Usuario autenticado: `GET http://localhost:8000/api/auth/me`

## 10. Ejecutar las pruebas

```powershell
pytest
```

## 11. Ejecutar Alembic

```powershell
# Crear una migración a partir de los modelos ORM
alembic revision --autogenerate -m "descripcion del cambio"

# Aplicar migraciones pendientes
alembic upgrade head

# Revertir la última migración
alembic downgrade -1
```

Alembic toma la cadena de conexión desde `DATABASE_URL` (a través de `Settings`), nunca
desde `alembic.ini` directamente.

La migración inicial es `migrations/versions/df98eb51ee34_initial_schema.py` y la corrección del default UTC de notificaciones es `migrations/versions/276b94986df8_fix_notification_utc_default.py`. Para consultar el estado:

```powershell
alembic current
alembic history
```

## 12. Contrato de autenticación y primera instalación

El login recibe JSON (`username`, `password`) en `POST /api/auth/login`. La API devuelve un
JWT de acceso y datos básicos del usuario; las demás rutas protegidas usan
`Authorization: Bearer <token>`. No hay endpoints de refresh/logout. La respuesta `user.branch`
solo se informa cuando hay exactamente una asignación vigente a una sucursal activa.

Para una instalación nueva, el orden es: `alembic upgrade head`, `python -m scripts.seed_authorization`,
`python -m scripts.load_reference_data --file <oficial.json> --validate-only | --dry-run | --apply` y
`python -m scripts.bootstrap_first_admin --confirm-initialization --username ... --first-name ... --last-name ... --branch-code ...`.
El detalle (qué valida cada comando, conflictos, idempotencia y por qué el orden es obligatorio) está en
[docs/backend-description.md](docs/backend-description.md#inicialización-segura-de-primera-instalación).
No hay credenciales por defecto: la contraseña del primer administrador se solicita sin eco y nunca
se pasa como argumento. La plantilla de datos es [docs/examples/reference-data.example.json](docs/examples/reference-data.example.json)
(solo ejemplo; los datos oficiales los entrega la institución). **No ejecutes estos comandos contra una base real sin autorización.**
No se crean usuarios, roles ni catálogos al iniciar FastAPI.

Permisos de sucursal se evalúan con la asignación vigente resuelta por backend; un `branch_id`
en la petición solo puede comprobar el contexto, no concederlo. Los permisos globales no usan
sucursal. Para validar un permiso de forma diagnóstica:

```http
GET /api/auth/permissions/VIEW_VISITORS?branch_id=1
Authorization: Bearer <token>
```

Para permisos `GLOBAL`, omite `branch_id`. Este endpoint no reemplaza la autorización de las
rutas de negocio. Los catálogos de solo lectura (`/api/branches`, `/api/branch-types`, `/api/visitor-types`,
`/api/visit-reasons`, `/api/roles`) están descritos en [docs/backend-description.md](docs/backend-description.md#api-de-catálogos).

### Probar el login y Bearer en Swagger

1. Abre `/docs`, ejecuta `POST /api/auth/login` con `{"username": "...", "password": "..."}`.
2. Copia `access_token`, pulsa **Authorize** y pega solo el token (el esquema es HTTP Bearer).
3. El token dura `ACCESS_TOKEN_EXPIRE_MINUTES` (30 por defecto); al expirar las rutas responden `401` y hay que repetir el login (no hay refresh ni logout).

### Códigos de error

- `401`: token ausente, inválido, expirado o usuario inactivo.
- `403`: identidad válida sin permiso, sin sucursal vigente o con un `branch_id` ajeno.
- `409`: conflicto de estado o duplicado. `422`: validación de datos o rango de fechas.
- Fallos internos devuelven `500` genérico sin detalles; el login devuelve `503` si la base no responde.

### Fechas

Los timestamps se almacenan y devuelven en UTC con sufijo `Z`. `date_from` es inclusivo y `date_to` exclusivo en visitas, dashboard, reportes y auditoría (en auditoría `date_to` antes era inclusivo). Detalle y guía para `America/Santo_Domingo` en [docs/backend-description.md](docs/backend-description.md#fechas-y-timestamps).

## 16. Gestión de visitantes

Los visitantes son perfiles globales y no tienen `BranchId`. La gestión utiliza:

```text
GET    /api/visitors
GET    /api/visitors/{visitor_id}
POST   /api/visitors
PATCH  /api/visitors/{visitor_id}
POST   /api/visitors/{visitor_id}/activate
POST   /api/visitors/{visitor_id}/deactivate
```

Permisos:

```text
VIEW_VISITORS
CREATE_VISITOR
UPDATE_VISITOR
```

La identificación se normaliza de forma conservadora para búsquedas y duplicados, pero `IdentificationNormalized` nunca se acepta desde el cliente ni aparece en respuestas. La identificación original se conserva y se devuelve enmascarada. Teléfono y correo se devuelven completos solo con el permiso `VIEW_VISITOR_CONTACT`; sin él salen enmascarados (ver [docs/backend-description.md](docs/backend-description.md#privacidad-de-visitantes)). El contrato completo de la API está en [docs/api-contract.md](docs/api-contract.md). Los visitantes sin identificación no se deduplican por nombre, teléfono, email o empresa.

Los listados aplican búsqueda, filtros, `COUNT`, `OFFSET` y `LIMIT` directamente en SQLAlchemy. La activación y desactivación son cambios lógicos mediante `IsActive`; no existe borrado físico.

## 18. Auditoría

La auditoría operativa utiliza `AuditService` y registra únicamente eventos definidos para usuarios, visitantes, visitas y login. Los valores se serializan como JSON mínimo y se redactan claves sensibles como passwords, hashes, tokens, Authorization, secrets y credenciales.

Eventos implementados:

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

La escritura de auditoría es append-only desde la aplicación: no existen endpoints de POST, PATCH, PUT ni DELETE para `AuditLog`. El único endpoint público es:

```text
GET /api/audit-logs
```

Requiere `VIEW_AUDIT_LOGS`, soporta paginación y filtros SQL. La respuesta vuelve a redactar `OldValues` y `NewValues` para proteger registros históricos potencialmente contaminados.

## 19. Dashboard operacional

La Fase 12 expone métricas agregadas sin crear tablas nuevas:

```text
GET /api/dashboard/summary
GET /api/dashboard/visits-by-day
GET /api/dashboard/visits-by-status
GET /api/dashboard/visits-by-reason
```

Los endpoints requieren `VIEW_REPORTS` para el Dashboard de la sucursal actual o `VIEW_GLOBAL_REPORTS` para un Dashboard global. No aceptan `branch_id` como fuente de autoridad.

Los rangos opcionales `date_from` y `date_to` reciben fecha/hora ISO 8601 UTC. Las métricas se calculan en SQL Server mediante `COUNT`, `COUNT DISTINCT` y `GROUP BY`; no se cargan todas las visitas en memoria.

## 20. Reportes

La Fase 13 expone consultas históricas y agrupadas:

```text
GET /api/reports/visits
GET /api/reports/visits/summary
```

Los reportes aceptan filtros combinables por rango UTC, estado, motivo, visitante, usuario registrador, sucursal y búsqueda textual. El reporte detallado utiliza paginación estable por `EntryAt DESC, Id DESC`.

`VIEW_REPORTS` limita la consulta a la sucursal actual. `VIEW_GLOBAL_REPORTS` permite consultar globalmente o filtrar una sucursal concreta. `branch_id` nunca amplía el alcance del usuario.

El resumen acepta `group_by=status|reason|registered_by|branch`; la agrupación por sucursal requiere alcance global. No se implementan exportaciones CSV, Excel o PDF en esta fase.

## 17. Gestión de visitas

Los endpoints disponibles son:

```text
GET    /api/visits
GET    /api/visits/{visit_id}
POST   /api/visits
PATCH  /api/visits/{visit_id}
POST   /api/visits/{visit_id}/complete
POST   /api/visits/{visit_id}/cancel
```

Permisos:

```text
VIEW_VISITS
CREATE_VISIT
UPDATE_VISIT
```

La creación deriva `BranchId` de la asignación vigente del usuario y `RegisteredByUserId` de su identidad JWT. El cliente no puede establecer esos valores. Todas las consultas filtran por `Visit.branch_id` en SQLAlchemy.

Las transiciones permitidas son:

```text
ACTIVE -> COMPLETED
ACTIVE -> CANCELLED
```

Una visita completada o cancelada no se elimina ni vuelve a estado activo. `Visit.BranchId` y `RegisteredByUserId` permanecen históricos incluso si el usuario cambia de sucursal.

## 15. Gestión de usuarios y sucursales

La gestión administrativa está disponible bajo `/api/users` y exige permisos materializados:

```text
MANAGE_USERS          usuarios y roles
ASSIGN_USER_BRANCH    asignaciones iniciales
MOVE_USER_BRANCH      transferencias
```

Endpoints principales:

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

Las respuestas nunca incluyen `PasswordHash`. Las contraseñas nuevas se convierten a Argon2 antes de persistirse.

Las transferencias cierran la asignación vigente y crean una nueva dentro de una única transacción. SQL Server utiliza `UPDLOCK, HOLDLOCK` al leer el historial del usuario para impedir dos transferencias concurrentes. La visita histórica no se modifica: `Visit.BranchId` continúa representando la sucursal donde se registró.

Las asignaciones usan intervalos `[ValidFrom, ValidUntil)`, conservan el historial y rechazan solapamientos. Desactivar un usuario solo cambia `IsActive` y `DeactivatedAt`; no borra usuarios, visitas, auditoría ni asignaciones.

## 14. Aislamiento por sucursal

La infraestructura de Fase 7 resuelve el contexto mediante `BranchAccessService` y `get_current_branch`. La consulta de la asignación vigente filtra por `Status = 'ACTIVE'`, `ValidFrom <= ahora` y `ValidUntil IS NULL OR ahora < ValidUntil`. Si no existe exactamente una asignación vigente, el acceso se deniega; no se escoge una fila arbitrariamente.

`require_branch_permission("VIEW_VISITS")` combina usuario autenticado, contexto vigente y `PermissionService`. Un `branch_id` enviado por query o path solo se compara con el contexto autorizado. Si difiere, se devuelve `403`; nunca cambia la sucursal del usuario.

Las consultas futuras de visitas deben usar `VisitAccessService.list_query(context)`, que genera el predicado SQL `Visit.branch_id == context.branch_id`. No se permite traer todas las visitas y filtrar después en Python. `Visit.BranchId` es la pertenencia histórica del recurso; el cambio posterior de sucursal del usuario no modifica ese valor.

`Visitor` no tiene `BranchId` en el esquema aprobado. Por eso no se inventa una columna: su alcance futuro deberá derivarse del recurso u operación relacionada y no de una relación inexistente.

## Notas de seguridad

- Las contraseñas nunca se almacenan en texto plano (se usará `pwdlib`).
- Los secretos (JWT, credenciales de base de datos) viven únicamente en `.env`, fuera de Git.
- El manejo de errores está centralizado (`app/core/exceptions.py`) y no expone detalles internos.
- El aislamiento de datos por sucursal se diseñará en la capa de dominio/aplicación e infraestructura
  antes de implementar los endpoints de negocio, para no tener que rediseñar el proyecto después.
