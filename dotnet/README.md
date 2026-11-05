# SeNaSaVisits (.NET)

Estructura inicial de la futura migración del backend SeNaSaVisits. Esta solución convive en el mismo repositorio con la implementación Python/FastAPI, que permanece como referencia temporal.

## Requisitos

- .NET SDK 10.0.x. En el entorno de creación se detectó SDK 10.0.400.
- .NET 10 es el target provisional y está sujeto a confirmación del estándar institucional.
- No se requiere SQL Server para compilar, ejecutar la API básica ni correr la prueba inicial.

## Estructura

```text
dotnet/
  SeNaSaVisits.sln
  Directory.Build.props
  src/
    SeNaSaVisits.Domain/
    SeNaSaVisits.Application/
    SeNaSaVisits.Infrastructure/
    SeNaSaVisits.API/
  tests/
    SeNaSaVisits.UnitTests/
```

- **SeNaSaVisits.Domain**: entidades, reglas de dominio, value objects, enums y excepciones puras. Todavía no contiene lógica de negocio.
- **SeNaSaVisits.Application**: casos de uso, DTOs, interfaces y validación. Depende de Domain.
- **SeNaSaVisits.Infrastructure**: futuras implementaciones de persistencia, repositorios, autenticación e integraciones. Depende de Application y Domain.
- **SeNaSaVisits.API**: host ASP.NET Core, controladores, middleware, configuración y OpenAPI/Swagger. Depende de Application e Infrastructure.
- **SeNaSaVisits.UnitTests**: pruebas xUnit iniciales; referencia Domain y Application.

`Directory.Build.props` centraliza `net10.0`, nullable reference types e implicit usings. El grafo de referencias sigue Clean Architecture y no contiene dependencias circulares.

## Compilar

Desde la raíz del repositorio:

```powershell
dotnet build .\dotnet\SeNaSaVisits.sln
```

## Ejecutar pruebas

```powershell
dotnet test .\dotnet\SeNaSaVisits.sln
```

## Iniciar la API

```powershell
dotnet run --project .\dotnet\src\SeNaSaVisits.API\SeNaSaVisits.API.csproj
```

El perfil HTTP local utiliza `http://localhost:5045`. Swagger UI estará disponible en:

- `http://localhost:5045/swagger`
- Documento OpenAPI: `http://localhost:5045/swagger/v1/swagger.json`

La API expone `GET /` y `GET /api/health`; el health check no se conecta a SQL Server.

## Alcance actual

Esta fase solo establece la solución, sus referencias, el host API mínimo y una prueba de humo xUnit. Aún no están implementados modelos, casos de uso, repositorios, acceso a SQL Server, migraciones .NET, JWT, Argon2, permisos, autorización, ni los endpoints funcionales del backend Python. No se agregaron dependencias de EF Core, JWT Bearer, Argon2 ni FluentValidation.
