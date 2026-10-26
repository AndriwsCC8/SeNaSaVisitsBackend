# Análisis de requisitos del registro de visitas (Fase F, solo lectura)

Fecha: 2026-10-26. Este documento **no define requisitos institucionales**: compara tres fuentes y deja explícito qué está comprobado, qué es discrepancia técnica y qué debe decidir la institución. Ninguna inferencia se presenta como requisito confirmado.

## 0. Decisiones de alcance confirmadas por el responsable del proyecto

Estas decisiones aclaran el alcance. **No son evidencia de que algo esté implementado**: salvo lo indicado en el §2 como "comprobado", nada de lo marcado como futuro existe en el código.

| # | Decisión | Clasificación | Efecto en este análisis |
|---|---|---|---|
| 1 | El frontend actual es una **maqueta o demo** que se presentará a los gerentes antes de implementar su funcionalidad real. Los gerentes podrían pedir cambios en pantallas, campos o procesos | Confirmado | Los campos y reglas del frontend son una **propuesta de demo**, no requisitos. Pueden cambiar tras la presentación |
| 2 | El frontend **no se conecta todavía** al backend | Confirmado | No hay integración HTTP en curso |
| 3 | El backend sigue preparándose para una futura integración con contratos y arquitectura coherentes | Confirmado | Se mantienen los contratos actuales; los cambios requieren las decisiones pendientes |
| 4 | El sistema usa **carnets de visitantes existentes** | Confirmado (uso); detalles sin definir | El carnet sigue sin campo en el backend (fila 10). Solo se sabe que los carnets existen |
| 4b | Generación e impresión de etiquetas | **Descartado / fuera de alcance** | No se implementa |
| 5 | Escaneo o captura de imágenes de cédulas o pasaportes | **Descartado / fuera de alcance** | No se implementa |
| 5b | Validación de identidad mediante el **Padrón de la JCE** | **Futuro, pendiente de definición** | No implementada; sin interfaz, contrato ni autorización confirmados |
| 6 | Integración con **Microsoft Entra ID**, Padrón de la JCE, **correo automático** y sistemas institucionales existentes | **Futuro**: después de aprobar el flujo funcional y confirmar interfaces y autorizaciones | Ninguna está implementada ni diseñada en este documento |
| 7 | **Notificaciones** | **Requisito futuro**, sin definir | El modelo `Notification` actual (sin rutas) **no se asume** suficiente para los eventos y destinatarios necesarios |
| 8 | **Citas y pre-registro** | **Reservados para la última fase**, después de investigar el proceso institucional | Fuera de este análisis |

### Etapa previa a congelar requisitos: presentación del demo

Antes de congelar los requisitos del registro de visitas se debe **presentar el demo a los gerentes y recopilar sus observaciones** (pantallas, campos, procesos y permisos). Las respuestas a las preguntas de los grupos A y B (§3) deben contrastarse con esas observaciones. Hasta entonces, ningún campo de la maqueta debe tratarse como requisito ni diseñarse un cambio de esquema a partir de él.

### Resumen de alcance

| Categoría | Elementos |
|---|---|
| Requisitos confirmados | Existen carnets de visitantes; el frontend es un demo y no se conecta todavía; el backend sigue preparándose para la integración |
| Requisitos descartados | Generación e impresión de etiquetas; escaneo o captura de imágenes de documentos |
| Funcionalidades futuras pendientes de definición | Validación con el Padrón de la JCE; Entra ID; correo automático; sistemas institucionales; notificaciones; citas y pre-registro |
| Sin definir (siguen pendientes) | Formulario vigente, campos obligatorios y reglas de la visita (ver matriz y §3) |

## 1. Fuentes y limitaciones

| Fuente | Qué se usó | Limitación |
|---|---|---|
| **Backend** | Código real: modelos `Visit`, `Visitor`, DTOs, servicios, rutas, `scripts/permission_catalog.py`, pruebas, `docs/api-contract.md` | Comprobado por lectura y por una sonda de solo lectura (§6). Pruebas con sesiones simuladas o SQLite en memoria; no hay prueba contra SQL Server real |
| **Frontend** | Únicamente el informe D1, tal como se pegó en la conversación (Fase D2). Se citan sus afirmaciones como **[D1]** | **No se leyó el código del frontend en esta fase.** Es una maqueta/demo (§0): sus campos y reglas no son requisitos confirmados. El informe D1 completo no está en el repositorio; `docs/frontend-compatibility-audit.md` solo recoge una parte. Todo lo del frontend es afirmación del informe, no verificada por mí |
| **Excel** `Formulario_Registro_Visitantes.xlsx` (y `-1`) | Leído en solo lectura. Las cuatro copias encontradas tienen idéntico SHA-256. Hoja única "Registro de Visitantes". Control documental: código `GTI-FORM-000`, versión `01`, vigencia "3 años", **fecha de aprobación `XX/XX/XXXX`** (celda B12, marcador). Tabla en fila 14 con 11 columnas; filas 15-31 vacías. Sin validaciones de datos, listas, fórmulas ni formato condicional | **No se asume vigente.** Es un formulario en papel de captura; no define obligatoriedad, formatos ni catálogos |

Las 11 columnas del Excel (fila 14): Fecha · Nombre del Visitante · Telefono · Documento de Identidad · Motivo de la Visita · Persona a quien Visita · Hora de Entrada · Hora de Salida · Área Visitada · Observaciones · Nombre del Responsable.

Estados usados en la matriz: **CT** confirmado técnicamente · **DT** discrepancia técnica · **PD** pendiente de decisión institucional · **ND** no documentado · **DESC** descartado (fuera de alcance) · **FUT** funcionalidad futura pendiente de definición.

## 2. Matriz de discrepancias

| # | Campo o regla | Frontend [D1] | Backend [código] | Excel | Estado | Impacto en la integración | Pregunta concreta |
|---|---|---|---|---|---|---|---|
| 1 | Nombre y apellido | `name`, un solo texto obligatorio | `Visitor.first_name` y `last_name`, ambos obligatorios (≤100) | "Nombre del Visitante", una columna | DT + PD | El cliente debe dividir el nombre o el backend aceptar uno solo | ¿El nombre se captura en uno o dos campos? ¿El apellido es obligatorio? |
| 2 | Identificación y normalización | `cedula` y `passport` separados y excluyentes; placeholder `000-0000000-0`; sin validación de formato | Un solo `identification` (≤50) sin tipo; se normaliza (valor numérico sin guiones/espacios; con letras conserva el guion); índice único sobre el normalizado → 409; la respuesta enmascara | "Documento de Identidad", una columna | DT + PD | Se pierde la distinción cédula/pasaporte; búsqueda con guiones falla (§6) | ¿Se necesita el tipo de documento? ¿Cuál es el formato válido de cédula y pasaporte? |
| 3 | Teléfono y correo | `phone` y `email` opcionales sin validar; la tabla de visitas muestra el teléfono | `phone` ≤30 sin validar formato; `email` validado; **la visita no los devuelve**; en visitantes salen enmascarados sin `VIEW_VISITOR_CONTACT`; la búsqueda por contacto está limitada (Fase E) | Solo "Telefono"; no hay correo | DT + PD | La tabla de visitas no puede mostrar el teléfono sin una llamada adicional, y el recepcionista no lo vería completo | ¿El teléfono es obligatorio? ¿Quién puede verlo completo? ¿El correo se necesita? |
| 4 | Motivo de visita | `purpose`, 8 valores fijos; "Otro" exige `purposeDetail` (los valores no están en el informe D1) | `reason_id` obligatorio, catálogo `visit-reasons` (vacío hasta cargar datos oficiales); sin campo de detalle | "Motivo de la Visita", texto | PD | Sin lista oficial no hay catálogo que cargar; "Otro" no tiene dónde guardarse | ¿Catálogo cerrado o texto libre? ¿Cuál es la lista oficial? ¿"Otro" lleva detalle y dónde se guarda? |
| 5 | Persona visitada | `host`, texto libre obligatorio | `visited_person` ≤200, opcional | "Persona a quien Visita" | CT (correspondencia directa) / PD (obligatoriedad) | Ajuste de nombres; el backend no lo exige | ¿Es obligatorio? ¿Texto libre o empleado de un directorio? |
| 6 | Área o destino | `dept` (etiqueta obligatoria, **no validada**), catálogo fijo de 7; además `gerencia` y `piso` | `destination` ≤200 texto libre, opcional; sin catálogo | "Área Visitada" | PD | No se sabe si `dept`, `gerencia`, `piso` y "área" son uno, dos o tres datos | ¿"Área Visitada" equivale a departamento, gerencia o piso? ¿Texto libre o catálogo por sucursal? |
| 7 | Responsable del registro | No hay campo; el usuario autenticado viene de la maqueta (la barra lateral muestra un nombre fijo) | `registered_by` se deriva del token y no se puede enviar | "Nombre del Responsable" (solo encabezado) | ND | La correspondencia es una suposición | ¿Quién es el "responsable": quien registra, el anfitrión, un supervisor o quien firma? ¿Se captura aparte? |
| 8 | Fecha y hora de entrada y salida | `entryAt` ISO local **sin zona**; `entry`/`exit` como texto "HH:mm"; salida `"--"` sin valor; formatos de hora inconsistentes; no existe `exitAt` | `entry_at` opcional (por defecto ahora UTC); `exit_at` solo vía `complete` (por defecto ahora); `exit_at >= entry_at`; sin validación contra fechas pasadas o futuras | Fecha, Hora de Entrada, Hora de Salida en columnas separadas | DT | Riesgo de desplazamiento de 4 h; el cliente debe mapear `"--"` a `null` | ¿Quién fija la hora (reloj del servidor o del cliente)? ¿Se permiten registros retroactivos? |
| 9 | Zona horaria de Santo Domingo | Hora local del navegador, sin zona; rango "Esta semana" empieza el lunes | Se almacena y responde en UTC con `Z`; un valor sin zona se interpreta como UTC; el dashboard por día agrupa por **día UTC**; documentada la guía UTC-4 | No indica zona | PD | Si el día de negocio es local, hay filtros y agregados desplazados | ¿La zona operativa es `America/Santo_Domingo`? ¿El "día" de reportes y dashboard es local? |
| 10 | Carnet | Obligatorio; único entre visitas Activas/Pendientes (solo validación local); `"--"` en un mock | **No existe** campo ni catálogo | No aparece | ND (backend y Excel) / PD. **Confirmado:** se usan carnets de visitantes existentes; etiquetas e impresión descartadas | Sin campo no hay forma de guardarlo ni de validar la unicidad | ¿Cómo se identifica y se registra el carnet existente (número, código)? ¿Es único por sucursal o global? ¿Cómo se registra una visita sin carnet? |
| 11 | Piso | Obligatorio; catálogo de 6 solo para "Sede Central"; **en otras sucursales no hay selector y el alta falla** (defecto del frontend [D1]) | No existe | No aparece | ND / PD | Bloquea el alta en sucursales sin catálogo | ¿Se registra el piso? ¿Qué pisos tiene cada sucursal? |
| 12 | Gerencia | Solo para "Sede Central" y "Naco"; catálogo de 7 | No existe | No aparece | ND / PD | Mismo que piso; además depende de la sucursal | ¿Gerencia es un dato requerido y por qué sucursales? |
| 13 | Tipo de visitante | `visitorType`, 9 valores **por visita**; en el módulo de visitantes hay otros 3 tipos distintos | `Visitor.visitor_type_id` por **persona**; catálogo `visitor-types`; no es un dato de la visita | No aparece | DT + PD | Una persona no puede tener distinto tipo por visita; hay dos listas incompatibles | ¿El tipo pertenece a la persona o a la visita? ¿Cuál es la lista oficial? |
| 14 | Tiempo estimado | `estimatedMinutes` según el tipo (solo "Técnico" editable; `null` para contratista permanente) | No existe; `VisitorType` no guarda minutos | No aparece | ND / PD | No hay dónde almacenarlo ni calcular excesos | ¿Existe un tiempo máximo? ¿Depende del tipo? ¿Quién lo define? |
| 15 | Fecha fin de contratistas | `endDate` solo para "Contratista permanente" | No existe | No aparece | ND / PD | Idem | ¿Se registra y qué efecto tiene? |
| 16 | Equipos y sus datos | Tipos de equipo, y marca, modelo y serie para 5 de ellos; resumen de texto; no se guardan `hasEquipment` ni `equipmentTypes` en la visita | No existe ningún campo | No aparece | ND / PD | Requeriría tabla propia o campos nuevos | ¿Se registra equipo? ¿Con qué datos y para qué visitas? |
| 17 | Observaciones | `notes` | `notes` ≤1000 | "Observaciones" | CT | Mapeo directo | Ninguna (salvo si debe ser obligatorio) |
| 18 | Estados de visita | `Activa`, `Completada`, `Cancelada`, `Pendiente`, más 4 estados calculados en el cliente; "Pendiente" y "Cancelada" sin acción en la UI | `ACTIVE`, `COMPLETED`, `CANCELLED` (restricción en la tabla); transiciones `ACTIVE → COMPLETED/CANCELLED`; cancelar exige motivo | No define estados | DT + PD | "Pendiente" y los estados calculados no tienen soporte; el cliente debe traducir etiquetas | ¿Existe "Pendiente de salida" y quién lo genera? ¿"Excedió tiempo" se guarda o se calcula, y dónde? ¿Se puede cancelar? |
| 19 | Permisos de recepción | Un recepcionista crea visitas y marca salida | `RECEPTIONIST` tiene `VIEW_VISITS`, `CREATE_VISIT`, `VIEW_VISITORS`, `CREATE_VISITOR`, `UPDATE_VISITOR`. **No** tiene `UPDATE_VISIT` (necesario para `complete`/`cancel`), `VIEW_REPORTS` ni `VIEW_VISITOR_CONTACT` | No aplica | DT + PD | El recepcionista no puede registrar la salida | ¿El recepcionista completa y cancela visitas? ¿Ve el contacto completo? ¿Ve el dashboard? |
| 20 | Visibilidad del dashboard | Visible a todos; datos fijos; ningún dato se filtra por sucursal | `VIEW_REPORTS` (sucursal) o `VIEW_GLOBAL_REPORTS` (global); sin ellos, 403; sin serie por hora, por departamento, tiempo promedio ni ocupación | No aplica | DT + PD | Pantalla inicial devolvería 403 a recepción | ¿Quién ve el dashboard y con qué alcance? ¿Qué métricas son oficiales? |
| 21 | Alcance por sucursal | Visibilidad filtrada en el cliente; "Administrador" ve todas las sucursales; la sucursal es un texto libre | Las visitas siempre se limitan a la sucursal del contexto del usuario, **incluso para `ADMIN`**; el acceso global a visitas solo existe vía reportes; los visitantes son perfiles globales sin `branch_id` | No aplica | DT + PD | El administrador del frontend no vería las visitas de otras sucursales por `/visits` | ¿Quién puede ver visitas de otras sucursales? ¿Los visitantes deben ser globales? |
| 22 | Visitantes duplicados | Cada visita lleva sus datos y no hay `visitorId`; solo se valida el carnet en uso | Identificación normalizada única (409 sin devolver el id existente); sin identificación no se deduplica por otros campos | No aplica (una línea por visita) | DT + PD | El flujo del cliente debe buscar o crear el visitante antes de la visita | ¿Es válido un visitante sin documento? ¿Cómo se fusionan duplicados? |
| 23 | Catálogos y validaciones | Listas fijas en el cliente (tipos, gerencias, pisos, equipos, departamentos, motivos); sin validar formato de cédula, teléfono ni correo | Catálogos de solo lectura: sucursales, tipos de sucursal, tipos de visitante, motivos y roles; **no hay** gerencias, pisos, departamentos ni equipos; validación de correo, longitudes y existencia/actividad de referencias | Sin listas ni validaciones | DT + PD | Sin datos oficiales los catálogos están vacíos | ¿Qué catálogos son oficiales y quién los mantiene? |
| 24 | Vigencia del formulario | No aplica | No aplica | `GTI-FORM-000` v01, vigencia 3 años, aprobación `XX/XX/XXXX` | PD | No se puede usar como especificación | ¿El formulario está aprobado y vigente? ¿Es la fuente de campos obligatorios? |
| 25 | Sucursal y regional | Tres nombres de sucursal en el login y 12 regionales con otros nombres | Entidad `Branch` con tipo; DTO de catálogo sin dirección, teléfono ni región (aunque el modelo tiene esos campos) | No aplica | PD | Determina qué se carga como dato de referencia | ¿Sucursal y regional son la misma entidad? ¿Cuál es la lista oficial? |
| 26 | Generación e impresión de etiquetas | No se describe en D1 | No existe y no se implementa | No aparece | **DESC** (confirmado fuera de alcance) | Ninguno | Ninguna |
| 27 | Escaneo o captura de imágenes de cédula o pasaporte | No se describe en D1 (solo un interruptor de foto en Configuración, sin implementación [D1]) | No existe y no se implementa | No aparece | **DESC** (confirmado fuera de alcance) | Ninguno | Ninguna. La foto del visitante es un tema distinto y no está decidida |
| 28 | Validación de identidad con el Padrón de la JCE | No se describe en D1 | **No implementada**; el backend solo normaliza y enmascara el texto de `identification` | No aparece | **FUT** | Condiciona identificación, nombre y duplicados (filas 1, 2, 22); sin interfaz ni autorización confirmadas | ¿Cuándo, con qué interfaz y autorización se integra? ¿Qué datos devuelve y cuáles se persisten? |
| 29 | Autenticación con Microsoft Entra ID | Login simulado [D1] | Login propio con usuario y contraseña (Argon2) y JWT; **sin** Entra ID | No aplica | **FUT** | Afecta a autenticación, usuarios y roles | ¿Cuándo se integra, y cómo se asignan roles y sucursales? |
| 30 | Correo automático | Interruptores de alertas en Configuración, sin efecto [D1] | **No existe** envío de correo | No aplica | **FUT** | Depende de eventos y destinatarios sin definir | ¿Qué eventos y destinatarios? ¿Desde qué cuenta o servicio? |
| 31 | Notificaciones | Lista local con categorías [D1]; sugiere aprobación, pre-registro, lista negra y copias de seguridad, que no existen en el frontend | Existe un modelo `Notification` **sin rutas ni servicios**; no se asume que cubra los eventos ni los destinatarios necesarios | No aplica | **FUT** | Requiere definición propia | ¿Qué eventos generan notificaciones, para quién y por qué canal? |
| 32 | Sistemas institucionales existentes | No se describen | No existe ninguna integración | No aplica | **FUT** | Desconocido | ¿Cuáles sistemas, con qué interfaces y autorizaciones? |
| 33 | Citas y pre-registro | Un interruptor y textos de notificación, sin funcionalidad [D1] | No existe | No aplica | **FUT** (reservado para la última fase, tras investigar el proceso) | Ninguno por ahora | Se difiere |

## 3. Preguntas institucionales por prioridad

### A. Bloqueantes para integrar el registro de visitas
1. ¿Cuál es el formulario vigente: la maqueta, `GTI-FORM-000` v01 (sin fecha de aprobación) u otro? ¿Quién lo aprueba? Debe responderse **después de presentar el demo a los gerentes** y recoger sus observaciones. *Afecta al modelo de datos, DTOs y frontend; sin esto las demás respuestas no tienen referencia.*
2. ¿Cuáles son los campos obligatorios de una visita? *Validaciones del backend y del formulario.*
3. Piso, gerencia, tiempo estimado, fecha fin y equipos: ¿se registran? Para cada uno: dónde, con qué formato y si son únicos. Del carnet ya se sabe que se usan carnets existentes; falta definir cómo se registra y su unicidad. *Modelo `Visit`, esquema, DTOs; probablemente migración.*
4. ¿El tipo de visitante pertenece a la persona o a cada visita? ¿Cuál es la lista oficial? *`Visitor`, `Visit`, catálogo.*
5. ¿"Área Visitada" es texto libre o un catálogo? ¿Es departamento, gerencia o piso? *`destination` o nuevos catálogos.*
6. ¿Quién es el "Responsable" del Excel? *`registered_by` o un campo nuevo.*
7. ¿Cédula y pasaporte se distinguen? ¿Hay formato y dígito verificador? ¿El nombre es uno o dos campos? *`Visitor`, normalización y búsqueda.*
8. ¿Quién fija la hora de entrada y de salida, y se permiten registros retroactivos? ¿Cuál es la zona operativa? *`entry_at`, `exit_at`, validación y cliente.*
9. ¿Qué estados existen realmente ("Pendiente", "Excedió tiempo", "Cancelada")? ¿Se persisten o se calculan? *CHECK de `Visit`, servicios, UI.*
10. ¿Cuál es la lista oficial de motivos y se admite "Otro" con detalle? *Catálogo `visit-reasons`, carga de datos.*

### B. Permisos y aislamiento por sucursal
11. ¿`RECEPTIONIST` debe completar y cancelar visitas (`UPDATE_VISIT`)? *Catálogo de permisos y asignaciones de rol.*
12. ¿Quién ve teléfono y correo completos (`VIEW_VISITOR_CONTACT`)? El Excel pide teléfono. *Política de privacidad, DTOs.*
13. ¿Qué otros roles existen (Supervisor, Seguridad, Auditor, Solo Lectura) y con qué permisos? *Catálogo de roles y permisos.*
14. ¿Quién puede ver visitas de otras sucursales, incluido el administrador? *`/visits` hoy es solo de la sucursal propia.*
15. ¿Los visitantes son globales entre sucursales? ¿El historial cruza sucursales? *Modelo `Visitor`, `VIEW_VISITORS`.*
16. ¿Sucursal y regional son la misma entidad? ¿Cuál es la lista oficial? *Datos de referencia y catálogo de sucursales.*
17. ¿Cómo debe el cliente conocer sus permisos efectivos? *Hoy no hay endpoint para listarlos.*

### C. Reportes y dashboard
18. ¿Quién ve el dashboard y con qué alcance? *Permisos `VIEW_REPORTS`/`VIEW_GLOBAL_REPORTS`.*
19. ¿Qué métricas son oficiales (por hora, por departamento, tiempo promedio, ocupación, alertas)? *Nuevos endpoints o agregaciones.*
20. ¿El día de reportes es el día local o UTC? *`visits-by-day`, filtros.*
21. ¿Se requiere exportación (PDF/Excel)? *Fuera de alcance actual.*

### D. Mejoras que pueden esperar
22. Validación de formato de cédula y teléfono. 23. Normalizar el texto buscado para documentos con guiones. 24. Fusión de visitantes duplicados. 25. Lista negra o bloqueo de visitantes. 26. Foto, notificaciones y configuración por sucursal.

### E. Citas y pre-registro (reservados para la última fase)
27. No se plantean preguntas ni se analizan requisitos de citas ni de pre-registro en esta fase; se investigará el proceso institucional antes.

### F. Integraciones futuras (no implementadas; sin interfaces ni autorizaciones confirmadas)
28. **Padrón de la JCE:** ¿qué interfaz y autorización existen, qué datos se consultan y cuáles se guardan? *Afecta a identificación, nombre y duplicados.*
29. **Entra ID:** ¿cómo se mapearían usuarios, roles y sucursales? ¿Se mantiene el login propio? *Afecta a autenticación y administración de usuarios.*
30. **Correo automático y notificaciones:** ¿qué eventos, destinatarios y canales? *Afecta al modelo de notificaciones y a un futuro servicio de envío.*
31. **Sistemas institucionales existentes:** ¿cuáles y con qué interfaces? *Afecta a la arquitectura de integración.*

## 4. Revisión técnica adicional

| Asunto | Estado | Evidencia |
|---|---|---|
| Recepción debe completar o cancelar visitas, pero `RECEPTIONIST` no tiene `UPDATE_VISIT` | **Comprobado en código.** `complete` y `cancel` exigen `UPDATE_VISIT`; `ROLE_PERMISSION_CODES["RECEPTIONIST"]` no lo incluye. La necesidad de negocio es solo del frontend [D1] y está **sin decidir**. Documentado en `docs/api-contract.md` y en el informe de compatibilidad (B-01). **Ninguna prueba afirma esta ausencia** (solo hay una para `VIEW_VISITOR_CONTACT`) | `scripts/permission_catalog.py`; rutas de visitas |
| El frontend muestra el teléfono en las visitas; la respuesta de visitas no lo incluye | **Backend comprobado:** los campos de `VisitVisitorResponse` son `id`, `identification`, `first_name`, `last_name`, `company`; hay una prueba que impide `phone` y `email` en visitas y reportes. La tabla del frontend es solo **[D1]** | `app/application/dto/visits.py`; `tests/test_phase_c.py` |
| Fechas locales sin zona interpretadas como UTC | **Backend comprobado:** `_utc_naive` deja un valor sin zona sin conversión (sonda: `09:00` → `09:00`); hay pruebas de conversión en `tests/test_phase_a.py`. Que el frontend envíe fechas sin zona es solo **[D1]** | `app/application/services/visits.py` |
| Búsqueda por identificación con guiones | **Comprobado ahora** con una sonda en SQLite en memoria: buscar `001-1223344-5` da 0 resultados; `00112233445` y `0011223` dan 1. Documentado en el contrato y el informe de compatibilidad. **No hay ninguna prueba** de este caso | `app/application/services/visitors.py` |
| Alcance global de `VIEW_VISITORS` | **Comprobado:** `Visitor` no tiene `branch_id` (hay una prueba). Documentado como hallazgo. La decisión institucional sigue sin resolverse | `tests/test_visitors.py` |
| Excel sin fecha de aprobación visible | **Comprobado** en B12 (`XX/XX/XXXX`). **Desactualizado en la documentación existente:** el informe de compatibilidad dice que el Excel "no se inspeccionó" (no se modificó por restricción) | Excel; `docs/frontend-compatibility-audit.md` |
| "Nombre del Responsable" sin correspondencia confirmada | **Comprobado:** solo existe el encabezado `K14`; no hay valores, instrucciones ni campo equivalente confirmado | Excel |
| Campos adicionales de la maqueta ausentes del Excel | **Comprobado** contra el Excel (carnet, piso, gerencia, tipo, tiempo estimado, fecha fin, equipos, correo, empresa, pasaporte no aparecen). Que existan en la maqueta es solo **[D1]** | Excel; informe D1 |

Además, solo con lectura de código: las visitas de `ADMIN` también se limitan a su sucursal (fila 21) y el cliente no puede conocer los permisos efectivos (fila 19/17).

## 5. Resultado

### Hallazgos bloqueantes
1. No hay un formulario vigente confirmado: el Excel no tiene fecha de aprobación y la maqueta (un demo sujeto a cambios) es más amplia.
2. El modelo de visita no soporta carnet, piso, gerencia, tipo por visita, tiempo estimado, fecha fin, equipos ni "Pendiente".
3. `RECEPTIONIST` no puede completar ni cancelar visitas (decisión pendiente).
4. Nombre, documento y "Responsable" no tienen correspondencia confirmada.
5. No hay datos oficiales para motivos, tipos de visitante ni sucursales.

### Recomendación de fase siguiente
0. **Etapa previa (sin código): presentar el demo a los gerentes y recopilar observaciones** sobre pantallas, campos, procesos y permisos. Solo después se congelan los requisitos.

Una vez presentado el demo y respondidas las preguntas de los grupos A y B:
1. **Fase G1 (diseño, sin código):** decisión del modelo de visita; propuesta de esquema y migración presentada por separado para aprobación.
2. **Fase G2 (backend sin cambio de esquema):** ajustes de permisos de rol según la decisión, normalización del texto buscado, endpoint de permisos efectivos si se aprueba, y pruebas.
3. **Fase G3 (esquema):** migración aprobada y los campos nuevos de visita.
4. **Después:** integración del frontend (que hoy no se conecta), empezando por login, catálogos y visitas.
5. **Más adelante, por separado:** JCE, Entra ID, correo, notificaciones y sistemas institucionales, cuando haya flujo aprobado, interfaces y autorizaciones confirmadas; y al final, citas y pre-registro.

## 6. Verificación realizada

- `pytest -q -p no:warnings`: **278 pruebas pasaron**.
- Sonda de solo lectura con SQLite en memoria (búsqueda con y sin guiones, normalización, catálogo de permisos y campos de DTOs). No se usó SQL Server.
- **No** se ejecutó Alembic en esta fase.
- **No se realizó ninguna escritura en la base de datos**, ni seeds, bootstrap o cargas.
- Los Excel se leyeron sin modificarlos.
- Archivo creado: `docs/visit-requirements-analysis.md`. No se modificó ningún otro archivo.
- **Actualización de alcance (solo documentación):** se añadieron el §0 y las filas 26-33 y se ajustaron las filas 10 y la recomendación. No se ejecutaron pruebas en esta actualización y los resultados anteriores no se repiten aquí.
