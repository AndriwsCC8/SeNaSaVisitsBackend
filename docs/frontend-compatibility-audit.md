# Auditoría de compatibilidad backend ↔ frontend (Fase D2)

Fecha: 2026-10-26. Alcance: solo el backend de este repositorio, contrastado con el inventario D1 del frontend (maqueta local sin HTTP). No se editó código funcional, no se crearon migraciones, no se ejecutaron bootstrap, seeds ni cargas, y no se conectó el frontend. **Ninguna integración ha sido probada**: el frontend no tiene cliente HTTP y el backend nunca ha sido invocado por él.

Convención: **[C]** comprobado en código o por comando; **[D1]** afirmado por el informe del frontend (no verificado por mí); **[?]** desconocido.

## 1. Resumen ejecutivo

- El backend es coherente y está verificado: **258 pruebas pasan** y Alembic está en `276b94986df8` sin cambios pendientes (§9).
- El frontend solo usa realmente un módulo con lógica (Registro de Visitas) y su modelo de visita es **mucho más amplio** que el de la API. Faltan en el backend: carnet, gerencia, piso, tipo de visitante por visita, tiempo estimado, fecha fin, equipos, detalle de motivo y estado "Pendiente".
- Hay tres hallazgos que impiden integrar el flujo principal tal como está dibujado: (1) `RECEPTIONIST` no tiene `UPDATE_VISIT`, así que un recepcionista no puede registrar la salida; (2) la visita no devuelve teléfono ni correo, que la tabla del frontend muestra; (3) no existe un endpoint de permisos efectivos para decidir qué módulos mostrar.
- Hay un hallazgo de privacidad en el backend: la búsqueda de `GET /api/visitors` coincide con teléfono y correo aunque el usuario no tenga `VIEW_VISITOR_CONTACT` (§6).
- Fechas: el backend interpreta como UTC un instante sin zona. El frontend envía hora local sin zona (`entryAt`): si se integra sin cambios, las horas se desplazan 4 h.
- CORS está bien para los orígenes de Vite identificados (8443 y 5173, `localhost` y `127.0.0.1`); `0.0.0.0` y las IP de red no están permitidas (§8).
- No se puede declarar listo el sistema: el modelo de datos de visita requiere decisiones institucionales y probablemente un cambio de esquema (§7).

## 2. Evidencias inspeccionadas

Código del backend (leído o ejecutado): `main.py`, `app/core/config.py`, `app/core/security.py`, `app/core/exceptions.py`; `app/api/routes/*` (auth, users, visitors, visits, catalogs, dashboard, reports, audit, health); `app/api/dependencies/*` (auth, branch_access, permissions, catalogs, dashboard, reports); `app/application/dto/*`; `app/application/services/*` (visits, visitors, users, audit, authorization, branch_access, dashboard, reports, catalogs); `app/application/validators/visitors.py`; modelos `visit.py`, `visitor.py`, `branch.py`, `visit_reason.py`, `visitor_type.py`, `notification.py`; `scripts/*`; `docs/api-contract.md`, `docs/backend-description.md`, `README.md`; las suites de pruebas.

Comandos ejecutados en esta fase (solo lectura): `pytest`, `alembic heads/current/check`, preflight CORS con `TestClient`, generación de OpenAPI, prueba de `normalize_identification`.

Del frontend solo dispongo del informe D1; no he leído su código.

## 3. Verificación de `docs/api-contract.md`

- **[C]** Las 40 operaciones de OpenAPI están cubiertas. Ocho aparecen con forma abreviada (`.../activate`, `.../complete`, `/summary`…) y no son omisiones.
- **[C]** Los permisos, campos, paginación, defectos, ordenamientos, política de fechas, política de contacto y reglas de inactivos coinciden con el código revisado.
- Correcciones que el documento aún necesita (no se editó por la restricción de esta fase):
  1. Añadir que la búsqueda de visitantes (`search`) coincide con `phone` y `email` aunque estén enmascarados (§6, H-05).
  2. Aclarar que la búsqueda por `identification_normalized` solo funciona si el cliente normaliza antes (§5.3).
  3. La sección "Pendiente de validar contra el frontend" queda parcialmente respondida por este informe.

## 4. Compatibilidad por módulo y operación

Todas las rutas llevan prefijo `/api`. Errores comunes: 401 (sin/expirado/inválido), 403 (sin permiso o sucursal), 422 (validación). Detalle de campos y esquemas en `docs/api-contract.md`.

### 4.1 Autenticación

| Necesidad del frontend | Operación backend | Estado |
|---|---|---|
| Login real (hoy simulado, sin validar contraseña) | `POST /auth/login` · cuerpo `{username, password}` (ambos obligatorios) · 200 `{access_token, token_type:"bearer", user{id, username, first_name, last_name, role\|null, branch\|null}}` · 401 · 503 | Compatible. El cliente debe mostrar errores (hoy no hay) |
| `AppUser {name, role, branch, permissions[]}` | `GET /auth/me` devuelve `{id, username, first_name, last_name, role, branch}` | **Diferente**: `name` = first_name + last_name; `role` es un **código** (`ADMIN`, `RECEPTIONIST`…) no el texto "Administrador"; `branch` es objeto `{id, code, name}` o `null`; **no hay lista de permisos** |
| Permisos por pantalla | `GET /auth/permissions/{code}?branch_id=` → `{permission, allowed}` | Solo consulta uno a uno. **Falta endpoint de permisos efectivos** |
| Expiración, refresh, logout | JWT 30 min (`ACCESS_TOKEN_EXPIRE_MINUTES`); sin refresh ni logout | El cliente debe tratar 401 como cierre de sesión |

### 4.2 Visitas (`/visits`, permisos BRANCH, siempre en la sucursal del token)

| Operación | Ruta y permiso | Entrada | Salida | Errores relevantes |
|---|---|---|---|---|
| Listar | `GET /visits` · `VIEW_VISITS` | `page`, `page_size` ≤100, `status`, `visitor_id`, `reason_id`, `date_from`, `date_to`, `search` | `{items[VisitResponse], total, page, page_size}`; orden `entry_at` desc | 403, 422 (rango vacío) |
| Detalle | `GET /visits/{id}` · `VIEW_VISITS` | — | `VisitResponse` | 404 (también si es de otra sucursal) |
| Crear | `POST /visits` · `CREATE_VISIT` | **Obligatorios** `visitor_id`, `reason_id`. Opcionales `entry_at`, `destination`≤200, `visited_person`≤200, `notes`≤1000. **Campos desconocidos → 422** (`extra=forbid`) | 201 `VisitResponse`, `status="ACTIVE"` | 404 visitante/motivo; 422 inactivo |
| Actualizar | `PATCH /visits/{id}` · `UPDATE_VISIT` | `reason_id`, `destination`, `visited_person`, `notes` | `VisitResponse` | 409 si no está `ACTIVE`; 422 |
| Salida | `POST /visits/{id}/complete` · `UPDATE_VISIT` | `exit_at` opcional (por defecto ahora) | `VisitResponse`, `COMPLETED` | 409; 422 si `exit_at < entry_at` |
| Cancelar | `POST /visits/{id}/cancel` · `UPDATE_VISIT` | `cancellation_reason` obligatorio (1-500) | `VisitResponse`, `CANCELLED` | 409 |

`VisitResponse` anula en `null`: `exit_at`, `destination`, `visited_person`, `notes`, `completed_by`, `cancelled_by`, `cancelled_at`, `cancellation_reason`. El visitante embebido trae `id`, `identification` enmascarada, `first_name`, `last_name`, `company`: **sin teléfono ni correo**.

### 4.3 Visitantes (perfil global; operaciones con permisos BRANCH)

| Operación | Ruta y permiso | Notas |
|---|---|---|
| Listar / buscar | `GET /visitors` · `VIEW_VISITORS` | Filtros `search`, `is_active`, `visitor_type_id`, paginación; orden por `id`. `search` coincide con nombre, apellido, identificación normalizada, empresa, **correo y teléfono** |
| Detalle | `GET /visitors/{id}` · `VIEW_VISITORS` | 404 |
| Crear | `POST /visitors` · `CREATE_VISITOR` | **Obligatorios** `first_name`, `last_name`; opcionales `identification`≤50, `phone`≤30, `email` (validado), `company`≤200, `visitor_type_id`. 409 si la identificación normalizada ya existe (sin devolver el id existente) |
| Editar | `PATCH /visitors/{id}` · `UPDATE_VISITOR` | Mismos campos opcionales |
| Activar / desactivar | `POST /visitors/{id}/activate` · `/deactivate` · `UPDATE_VISITOR` | Es `is_active`, no una lista negra |

`VisitorResponse` anula: `identification`, `phone`, `email`, `company`, `visitor_type`. Sin `VIEW_VISITOR_CONTACT`: `phone` y `email` vienen enmascarados y `contact_masked=true`. No hay contadores `visits`/`lastVisit` ni historial embebido (el historial sería `GET /visits?visitor_id=`, limitado a la sucursal del usuario).

### 4.4 Catálogos (lectura)

| Ruta | Permisos de acceso | Inactivos |
|---|---|---|
| `GET /branches` | Globales (`MANAGE_BRANCHES`, `MANAGE_USERS`, `ASSIGN_USER_BRANCH`, `MOVE_USER_BRANCH`, `VIEW_GLOBAL_REPORTS`, `VIEW_AUDIT_LOGS`) ven todas; de sucursal (`VIEW_VISITS`, `CREATE_VISIT`, `UPDATE_VISIT`, `VIEW_VISITORS`, `VIEW_REPORTS`) ven solo la suya | `MANAGE_BRANCHES` |
| `GET /branch-types` | `MANAGE_BRANCHES` | `MANAGE_BRANCHES` |
| `GET /visitor-types` | BRANCH: `VIEW_VISITORS`, `CREATE_VISITOR`, `UPDATE_VISITOR`, `VIEW_VISITS`, `CREATE_VISIT`; GLOBAL: `MANAGE_VISITOR_TYPES` | `MANAGE_VISITOR_TYPES` |
| `GET /visit-reasons` | BRANCH: `VIEW_VISITS`, `CREATE_VISIT`, `UPDATE_VISIT`, `VIEW_REPORTS`; GLOBAL: `VIEW_GLOBAL_REPORTS`, `MANAGE_VISIT_REASONS` | `MANAGE_VISIT_REASONS` |
| `GET /roles` | `MANAGE_USERS` | no aplica |

Campos: `id`, `code`, `name`, `is_active` (`branches` añade `branch_type_id`; `roles` solo `id`, `code`, `name`). **No existen** catálogos de gerencias, pisos, departamentos, equipos ni tiempos por tipo. El DTO de sucursal **no expone** `region`, `address` ni `phone`, aunque el modelo `Branch` los tiene.

### 4.5 Usuarios (permisos GLOBAL)

| Operación | Ruta · permiso | Notas |
|---|---|---|
| Listar | `GET /users` · `MANAGE_USERS` | `search`, `is_active`, `branch_id` (filtro), `role_code`; orden por `id` |
| Detalle / roles / asignaciones | `GET /users/{id}`, `/roles`, `/assignments` · `MANAGE_USERS` | |
| Crear | `POST /users` · `MANAGE_USERS` (+ `ASSIGN_USER_BRANCH` si envía `branch_id`) | Obligatorios `username`, `first_name`, `last_name`, `password` (8-256). Opcionales `email`, `employee_code`, `role_code`, `branch_id`, `assignment_valid_from`. 409 duplicados |
| Editar | `PATCH /users/{id}` · `MANAGE_USERS` | `email`, `first_name`, `last_name`, `employee_code`, `role_code`. Sin cambio de contraseña ni de username |
| Activar / desactivar | `POST /users/{id}/activate` · `/deactivate` | No hay eliminar |
| Asignar / trasladar | `POST /users/{id}/assignments` (`ASSIGN_USER_BRANCH`), `POST /users/{id}/transfer` (`MOVE_USER_BRANCH`) | |

`UserResponse` no contiene departamento, último acceso, estado "Suspendido" ni avatar.

### 4.6 Dashboard, reportes, auditoría

| Módulo | Backend | Frente al frontend |
|---|---|---|
| Dashboard | `GET /dashboard/summary` (totales de estado y `unique_visitors`), `/visits-by-day` (día **UTC**), `/visits-by-status`, `/visits-by-reason`. Permiso: `VIEW_GLOBAL_REPORTS` (global) o `VIEW_REPORTS` (sucursal); no admite `branch_id` | Cubre KPIs, serie diaria y motivos. **No existen**: serie por hora, por departamento, tiempo promedio, ocupación por área, alertas, visitas recientes (se pueden obtener con `GET /visits?page_size=5`) |
| Reportes | `GET /reports/visits` (paginado, filtros ampliados, `total_pages`) y `/visits/summary` (`group_by` = `status`, `reason`, `registered_by`, `branch`). `VIEW_REPORTS` o `VIEW_GLOBAL_REPORTS` | Sin exportación PDF/Excel, sin lista de "reportes generados" ni compartir |
| Auditoría | `GET /audit-logs` · `VIEW_AUDIT_LOGS` (GLOBAL). Filtros `actor_user_id`, `action`, `entity_type`, `entity_id`, `branch_id`, `date_from/to`; `old_values`/`new_values` son cadenas JSON | El frontend **no tiene** módulo de auditoría |

### 4.7 Sin soporte en backend

Notificaciones (hay un modelo `Notification` pero **ninguna ruta**), Configuración (preferencias, no persistidas), exportaciones, pre-registro, citas, foto, lista negra, aprobación de visitas. Están fuera de alcance de las fases anteriores.

## 5. Diferencias concretas entre contratos

### 5.1 Campos de la visita del frontend

| Campo frontend | Equivalente en backend | Clasificación |
|---|---|---|
| `id` (`V-00235`) | `id` entero generado por el servidor | Ajuste del cliente (formatear/ignorar el id local) |
| `name` (un solo texto) | `visitor.first_name` + `last_name`, ambos obligatorios | Ajuste del cliente + decisión (cómo dividir el nombre) |
| `cedula` / `passport` | Un único `visitor.identification` (≤50), sin tipo | **Decisión institucional / posible cambio de esquema** (distinguir tipo de documento) |
| `email`, `phone` | Perfil de visitante; en visita **no aparecen**; enmascarados sin `VIEW_VISITOR_CONTACT` | Ajuste del cliente + decisión de permisos |
| `host` | `visited_person` | Ajuste del cliente |
| `dept` | `destination` (texto libre, 200). No hay catálogo | Decisión institucional (¿es "destino" o "departamento"?) |
| `purpose` | `reason_id` (catálogo `visit-reasons`) | Ajuste del cliente + datos de referencia |
| `purposeDetail` ("Otro") | Sin campo | Decisión (¿en `notes`?) / posible esquema |
| `notes` | `notes` | Compatible |
| `entryAt`, `entry` | `entry_at` UTC con `Z`; opcional | Ajuste del cliente (§8) |
| `exit`, `exitConfirmed` | `exit_at` nullable; `status` | Ajuste del cliente (`"--"` → `null`; "Sí" → `COMPLETED`) |
| `status` Activa/Completada/Cancelada | `ACTIVE`/`COMPLETED`/`CANCELLED` | Ajuste del cliente (mapeo) |
| `status` **Pendiente** | No existe; el CHECK de la tabla solo admite los tres | **Decisión institucional / cambio de esquema** |
| `automaticStatus` (4 valores calculados) | No existe | Decisión (¿calcular en cliente o en servidor?) |
| `carnet` (único entre activas/pendientes) | **Sin campo** | **Cambio de esquema** previa decisión (inventario y unicidad por sucursal o global) |
| `visitorType` (9 valores) | `visitor.visitor_type_id` por **visitante**, no por visita | Decisión; por visita implicaría **cambio de esquema** |
| `estimatedMinutes`, `endDate` | Sin campo; `VisitorType` no guarda minutos | Decisión / posible esquema |
| `gerencia` | Sin campo ni catálogo | Decisión / cambio de esquema |
| `piso` | Sin campo ni catálogo | Decisión / cambio de esquema |
| Equipos (`equipmentTypes`, `equipmentDetails`, `equipment`) | Sin campos | Decisión / cambio de esquema |
| `branch` | Derivado del token; no se envía | Ajuste del cliente |
| Registrado por | `registered_by` derivado del token | Compatible |
| Sin equivalente en la UI | `completed_by`, `cancelled_*`, `created_at`, `updated_at` | Opcional para el cliente |

### 5.2 Otras diferencias

- **Roles:** el frontend define 6 (Administrador, Supervisor, Recepcionista, Seguridad, Auditor, Solo Lectura). El backend tiene 4 (`SUPER_ADMIN`, `ADMIN`, `RECEPTIONIST`, `USER`). Supervisor, Seguridad, Auditor y Solo Lectura **no existen** y no hay API para crear roles ni permisos (solo scripts y el catálogo en código).
- **Permisos textuales** del frontend vs. permisos reales: Ver Dashboard → `VIEW_REPORTS`/`VIEW_GLOBAL_REPORTS`; Registrar Visitas → `CREATE_VISIT`; Gestionar Visitantes → `CREATE_VISITOR`/`UPDATE_VISITOR`; Ver Reportes → `VIEW_REPORTS`; Gestionar Usuarios → `MANAGE_USERS`; Ver Logs → `VIEW_AUDIT_LOGS`; **Exportar Reportes y Configurar Sistema no tienen equivalente**. El literal `"recepciones"` no es un permiso del backend.
- **Sucursal/Regional:** el backend tiene una entidad `Branch` con tipo. Si Sede Central, Naco, Sucursal Norte y las 12 regionales son sucursales, hay que cargarlas como datos de referencia (sin fuente oficial hoy). Provincia, dirección y teléfono no se devuelven por la API.
- **Paginación:** el frontend pinta listas completas. El backend limita `page_size` a 100, así que toda lista necesita paginación o varias peticiones.
- **Filtros:** el frontend filtra en cliente por "Hoy/Ayer/Semana/Mes" con fecha local; el backend filtra por rango UTC.
- **Estados de usuario:** "Suspendido" no existe; solo `is_active`.
- **Errores:** el frontend no maneja errores de red ni 401/403. El `detail` puede ser texto o lista (422 de FastAPI).

### 5.3 Búsqueda por documento

`normalize_identification` quita guiones y espacios de valores numéricos (`001-1223344-5` → `00112233445`) pero **conserva** los de valores con letras (`ab-12` → `AB-12`) **[C]**. La búsqueda compara el texto recibido con el valor normalizado **sin normalizarlo antes**: buscar `001-1223344-5` no encuentra `00112233445` **[C, por lectura del código]**. El cliente debe enviar la búsqueda ya sin guiones, o el backend debería normalizar (cambio no hecho).

## 6. Hallazgos

### BLOQUEANTES (impiden el flujo principal tal como está dibujado)

| ID | Hallazgo | Evidencia | Acción |
|---|---|---|---|
| B-01 | `RECEPTIONIST` no tiene `UPDATE_VISIT`, necesario para `complete` y `cancel`. Un recepcionista puede crear visitas pero no registrar la salida | `scripts/permission_catalog.py`; rutas de `visits.py` | Decisión institucional + cambio del catálogo (código) y `seed_role_permissions` |
| B-02 | El modelo de visita carece de carnet, piso, gerencia, tipo por visita, tiempo estimado, fecha fin, equipos y "Pendiente"; el formulario los exige | Modelo `Visit`, `VisitCreate` con `extra=forbid` | Decisiones del §7; probable cambio de esquema aprobado por separado |
| B-03 | No hay forma de que el frontend conozca los permisos efectivos del usuario ni su lista de módulos; `AppUser.permissions` hoy es un literal | `GET /auth/me` sin permisos; solo `GET /auth/permissions/{code}` | Decisión: añadir endpoint de permisos efectivos o aceptar consultas por permiso |

### IMPORTANTES

| ID | Hallazgo | Evidencia |
|---|---|---|
| I-01 | La tabla de visitas muestra teléfono; `VisitResponse` no lo incluye. Requiere pedir el visitante aparte (y sale enmascarado para quien no tenga `VIEW_VISITOR_CONTACT`) | `VisitVisitorResponse` |
| I-02 | El frontend envía fechas locales sin zona; el backend interpreta un valor sin zona como UTC: desplazamiento de 4 h respecto a Santo Domingo | `_utc_naive` en servicios |
| I-03 | Ningún receptor tiene `VIEW_REPORTS` por defecto, así que `/dashboard/*` y `/reports/*` devuelven 403 a recepcionistas aunque el Dashboard sea la pantalla inicial del frontend | Catálogo de permisos |
| I-04 | **Privacidad:** `GET /visitors?search=` coincide con `phone` y `email` aunque el usuario no tenga `VIEW_VISITOR_CONTACT`. Permite descubrir por tanteo contactos que luego se ven enmascarados | `visitors.py` servicio, líneas de `like`; contrato de privacidad de Fase C |
| I-05 | El alta de visitante falla con 409 si la identificación existe y no devuelve el id existente; el flujo del cliente debe buscar primero. La búsqueda con guiones no encuentra (§5.3) | Servicio de visitantes |
| I-06 | Un visitante es global: cualquier usuario con `VIEW_VISITORS` lista visitantes de toda la institución (nombre, empresa, id enmascarado), pero el historial solo se ve en su sucursal. ¿Es el comportamiento deseado? | Modelo `Visitor` sin `branch_id` |
| I-07 | Roles del frontend sin equivalente (Supervisor, Seguridad, Auditor, Solo Lectura) y sin API para crearlos | Catálogo de roles |
| I-08 | Hay dos catálogos de tipo de visitante en el frontend y ninguna fuente oficial. El backend no guarda minutos por defecto | D1 §4.2-4.3 |
| I-09 | `visits-by-day` agrupa por día UTC: visitas después de las 20:00 hora local caen al día siguiente | `DashboardService.visits_by_day` |
| I-10 | `JWT_SECRET_KEY` local de 25 caracteres (menor que el mínimo recomendado de 32); en producción impediría arrancar | Advertencia en cada ejecución |

### MENORES

- M-01 `GET /auth/me` devuelve solo el primer rol activo si el usuario tiene varios.
- M-02 Los mensajes de error funcionales son texto en español, no códigos; no son estables para lógica de cliente.
- M-03 El 422 de FastAPI incluye `input`, que repite el cuerpo enviado (en login incluiría la contraseña, solo hacia el mismo cliente).
- M-04 No hay límite de intentos de login.
- M-05 El backend no valida el formato de la cédula ni el teléfono.
- M-06 `entry_at` puede ser cualquier instante: no se valida contra el futuro ni el pasado **[C, no hay validación]**.
- M-07 Valor de `role` como código y estado en inglés obliga a una capa de traducción.
- M-08 El CORS solo admite las cabeceras `Authorization` y `Content-Type`.

## 7. Datos de visita faltantes y decisiones necesarias

Decisiones previas a cualquier cambio de esquema: 
1. ¿Carnet es un recurso físico? ¿Único por sucursal o global? ¿Cómo se representa "sin carnet"?
2. ¿Tipo de visitante pertenece al visitante o a cada visita? ¿Cuántos tipos oficiales y con qué tiempo máximo?
3. ¿Se necesita "Pendiente de salida" y quién lo genera? ¿Se persiste "Excedió tiempo permitido" o se calcula?
4. ¿Gerencia y piso son catálogos administrados por sucursal? ¿Qué pisos tienen las demás sucursales (el frontend hoy no puede registrar ahí)?
5. ¿Equipos se guardan estructurados (marca, modelo, serie)? ¿En qué visitas?
6. ¿Cédula y pasaporte se distinguen en el dato?
7. ¿`dept` equivale a `destination`? ¿`purposeDetail` va en `notes`?
8. Hasta que se decida: lo que sí puede enviarse hoy es `visitor_id`, `reason_id`, `entry_at` (opcional), `destination`, `visited_person`, `notes`.

## 8. Riesgos de seguridad, fechas, permisos y sucursales

- **Bearer y expiración [C]:** `Authorization: Bearer`; 30 min; 401 con `WWW-Authenticate: Bearer`; revalida usuario activo en cada petición. Sin refresh ni logout. El frontend no tiene almacenamiento ni manejo de 401 **[D1]**; dónde guardar el token (memoria vs. almacenamiento del navegador) es una decisión pendiente: guardarlo en memoria reduce exposición, pero la recarga cierra la sesión.
- **Aislamiento por sucursal [C]:** el contexto sale de la asignación vigente; un `branch_id` del cliente nunca concede acceso (cubierto en tests). Una visita ajena responde 404, y un `branch_id` ajeno, 403. El frontend ya filtra por `branch` en cliente, pero esa no es una barrera de seguridad.
- **Privacidad [C]:** identificación enmascarada y `identification_normalized` ausente. Contacto enmascarado sin `VIEW_VISITOR_CONTACT`, salvo el hallazgo I-04.
- **Fechas [C]:** `date_from` inclusivo y `date_to` exclusivo; respuestas con `Z`; sin zona se asume UTC. El frontend: `entryAt` local sin zona **[D1]**, `endDate` con `toISOString()` (UTC) **[D1]**, rangos "Hoy/Semana/Mes" locales **[D1]**. Para filtrar el día local D el cliente debe enviar `date_from` = 04:00Z de D y `date_to` = 04:00Z de D+1. El cliente debería omitir `entry_at` y dejar que el servidor use la hora actual.
- **Permisos [C]:** global y de sucursal no se mezclan. Ver B-01, B-03, I-03.
- **Frontend [D1]:** el login actual acepta cualquier contraseña; todos los módulos son visibles a cualquier usuario; esto es solo de maqueta y no reemplaza la autorización del servidor.
- Dependencias de HTTPS: [?] el informe no indica si el frontend se servirá por HTTPS ni la URL del backend.

### CORS: verificación con los orígenes del frontend (Vite, puerto 8443)

Resultado real de preflight `OPTIONS /api/auth/login` con `Authorization, Content-Type` **[C]**:

| Origen | Resultado |
|---|---|
| `http://localhost:8443`, `https://localhost:8443`, `http://127.0.0.1:8443`, `https://127.0.0.1:8443`, `http://localhost:5173` | 200 con `Access-Control-Allow-Origin` igual al origen |
| `http://0.0.0.0:8443`, `http://192.168.1.5:8443` (ejemplo de IP de red), `https://evil.example` | 400, sin cabecera de origen |
| Preflight `PATCH` desde `localhost:8443` | 200 |
| Preflight con cabecera `X-Requested-With` | 400 (no permitida) |

`.env` contiene la misma lista que el valor por defecto; no hay `*`; credenciales de navegador desactivadas (`CORS_ALLOW_CREDENTIALS=false`). El frontend **no tiene proxy** **[D1]**, por lo que llamará al backend directamente entre orígenes. Si se accede por IP de red o dominio, hay que añadir ese origen exacto a `CORS_ORIGINS`. No se probó un servidor HTTPS real **[?]**.

## 9. Resultados reales

```text
pytest -q -p no:warnings          -> 258 passed
alembic heads                     -> 276b94986df8 (head)
alembic current                   -> 276b94986df8 (head)
alembic check                     -> No new upgrade operations detected.
```

`alembic current` y `check` consultan la base configurada en modo lectura; no se aplicaron migraciones. No hay cambios en `migrations/`. Las pruebas usan sesiones simuladas y SQLite en memoria, no SQL Server: **el comportamiento real en SQL Server no está probado de extremo a extremo**.

Comandos de inicialización vigentes (verificados en código y documentación, **no ejecutados**): `alembic upgrade head` → `python -m scripts.seed_authorization` → `python -m scripts.load_reference_data --file <oficial.json> --validate-only | --dry-run | --apply` → `python -m scripts.bootstrap_first_admin --confirm-initialization --username … --first-name … --last-name … --branch-code …`. Obsoletos (solo avisan): `seed_roles`, `seed_permissions`, `bootstrap_user`. Vigente solo para resincronizar: `seed_role_permissions --assigned-by-user-id`.

## 10. Requisitos de datos de referencia

El cargador admite únicamente: tipos de sucursal, sucursales, tipos de visitante y motivos de visita. Necesidades detectadas:

| Dato | Fuente según D1 | Estado |
|---|---|---|
| Sucursales | "Sede Central", "Sucursal Norte", "Naco" y 12 regionales con nombres distintos | **Sin fuente oficial**; ¿sucursal = regional? |
| Tipos de sucursal | No aparecen en el frontend | Por definir |
| Tipos de visitante | 9 en `VisitRegistry`, 3 distintos en `Visitors` | Sin definición oficial; faltan minutos por defecto |
| Motivos de visita | 8 en `purposes` (el informe no lista los valores) | [?] |
| Gerencias (7), pisos (6), departamentos (7), equipos (7) | Listas fijas en el cliente | **No hay catálogo en el backend** |
| Usuarios y roles | 7 usuarios y 6 roles de maqueta | Los usuarios demo no existen en el backend; solo existen 4 roles |
| Excel `Formulario_Registro_Visitantes*.xlsx` | No inspeccionado | Revisar manualmente: puede definir los campos oficiales |

## 11. Plan de integración (orden por dependencias)

1. **Decisiones institucionales** del §7 y §12; definir roles y asignaciones de `RECEPTIONIST` (B-01, I-03, I-07).
2. **Datos oficiales:** preparar el JSON de referencia y validarlo con `--validate-only`/`--dry-run` en un entorno autorizado.
3. **Backend previo a integrar** (cambios aún no hechos): corregir I-04; decidir sobre permisos efectivos (B-03); si se aprueba, diseñar y revisar por separado la migración de campos de visita (B-02); catálogos de gerencia/piso si procede.
4. **Inicialización controlada** de un entorno de pruebas: migraciones, `seed_authorization`, carga de referencias, primer administrador.
5. **Frontend, infraestructura:** variable de URL base del API, cliente HTTP, `Authorization: Bearer`, tipos compartidos, manejo de 401/403/422/503, y política de almacenamiento del token.
6. **Autenticación:** reemplazar el login simulado; `AppUser` desde `/auth/me`; cierre de sesión al expirar.
7. **Catálogos:** cargar motivos, tipos y sucursales por API, sustituyendo las listas fijas.
8. **Visitantes:** búsqueda (con normalización), alta con manejo de 409, perfil.
9. **Visitas:** crear (sin `entry_at`), listar con paginación y filtros UTC, salida, cancelación; mapeo de estados.
10. **Usuarios y permisos**, **Dashboard**, **Reportes**, **Auditoría** (si la institución la requiere en la UI).
11. Notificaciones, configuración y exportaciones: fuera de alcance hasta decidir.

## 12. Pruebas necesarias para validar la integración

- Contrato: cada llamada del cliente contra `/openapi.json` (esquemas, nulos, límites de longitud).
- Autenticación: login correcto/incorrecto, token expirado, 403 por permiso, usuario sin sucursal.
- CORS desde el origen real del frontend, con y sin HTTPS y con IP de red si aplica.
- Aislamiento: usuarios de dos sucursales; `branch_id` manipulado; visita ajena.
- Privacidad: usuario con y sin `VIEW_VISITOR_CONTACT`, incluida la búsqueda por correo/teléfono.
- Fechas: 23:30 y 00:30 hora local, límites de día, desplazamiento de 4 h.
- Flujo completo recepcionista: buscar/crear visitante → crear visita → salida → cancelar.
- Paginación con más de 100 registros.
- Pruebas contra SQL Server real de pruebas (no solo SQLite).

## 13. Decisiones institucionales pendientes

1. Qué roles ve el sistema (Supervisor, Seguridad, Auditor, Solo Lectura) y sus permisos.
2. Si `RECEPTIONIST` debe tener `UPDATE_VISIT`, `VIEW_REPORTS` y `VIEW_VISITOR_CONTACT`.
3. Modelo de visita (carnet, tipo por visita, gerencia, piso, equipos, tiempos, "Pendiente").
4. Si sucursal y regional son la misma entidad, y la lista oficial.
5. Visibilidad de visitantes entre sucursales.
6. Zona horaria operativa y si el Dashboard agrupa por día local.
7. Política de sesión y almacenamiento del token.
8. Qué módulos son reales (notificaciones, configuración, exportación, pre-registro, lista negra, auditoría en UI).
9. Contenido y autoridad del Excel `Formulario_Registro_Visitantes*.xlsx`.

## 14. Lo que no puede afirmarse

- Que el frontend es compatible: es una maqueta sin código de red y sus formularios no coinciden con el modelo del backend.
- Que el backend funciona con SQL Server real de extremo a extremo.
- Que los orígenes de despliegue (más allá de los de desarrollo de Vite) estén cubiertos por CORS.
- Los valores de motivos, sucursales y tipos oficiales: no hay fuente en el repositorio ni en el informe.
