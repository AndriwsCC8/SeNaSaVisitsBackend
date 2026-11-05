using Microsoft.AspNetCore.Mvc;

namespace SeNaSaVisits.API.Controllers;

[ApiController]
public sealed class StatusController : ControllerBase
{
    [HttpGet("/")]
    public IActionResult GetRoot() => Ok(new
    {
        service = "SeNaSaVisits API",
        status = "ok"
    });

    [HttpGet("/api/health")]
    public IActionResult GetHealth() => Ok(new
    {
        service = "SeNaSaVisits API",
        status = "ok"
    });
}
