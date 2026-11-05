using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.Application.DTOs;

public sealed record VisitVisitorDto(long Id, string? Identification, string FirstName, string LastName, string? Company);
public sealed record VisitUserDto(long Id, string Username, string FirstName, string LastName);
public sealed record VisitReasonDto(long Id, string Code, string Name);
public sealed record VisitBranchDto(long Id, string Code, string Name);
public sealed record VisitDto(long Id, VisitVisitorDto Visitor, VisitBranchDto Branch, VisitUserDto RegisteredBy,
    DateTime EntryAt, DateTime? ExitAt, VisitReasonDto Reason, string? Destination, string? VisitedPerson,
    string Status, string? Notes, DateTime CreatedAt, DateTime UpdatedAt, VisitUserDto? CompletedBy,
    VisitUserDto? CancelledBy, DateTime? CancelledAt, string? CancellationReason);
public sealed record VisitSearchRequest(PageRequest Page, string? Status = null, long? VisitorId = null,
    long? ReasonId = null, DateTime? DateFrom = null, DateTime? DateTo = null, string? Search = null);
public sealed record VisitCreateRequest(long VisitorId, long ReasonId, DateTime? EntryAt = null,
    string? Destination = null, string? VisitedPerson = null, string? Notes = null);
public sealed record VisitUpdateRequest(FieldUpdate<long?> ReasonId, FieldUpdate<string?> Destination,
    FieldUpdate<string?> VisitedPerson, FieldUpdate<string?> Notes);
public sealed record VisitCompleteRequest(DateTime? ExitAt = null);
public sealed record VisitCancelRequest(string CancellationReason);

internal static class VisitDtoMapper
{
    public static VisitDto ToDto(Visit visit)
    {
        if (visit.Visitor is null || visit.Branch is null || visit.RegisteredBy is null || visit.Reason is null)
        {
            throw new InvalidOperationException("Visit reference navigations must be loaded to create the application DTO.");
        }

        var visitor = visit.Visitor;
        var registeredBy = visit.RegisteredBy;
        var branch = visit.Branch;
        var reason = visit.Reason;
        return new VisitDto(visit.Id,
            new VisitVisitorDto(visitor.Id, MaskIdentification(visitor.Identification?.RawValue), visitor.FirstName, visitor.LastName, visitor.Company),
            new VisitBranchDto(branch.Id, branch.Code, branch.Name),
            new VisitUserDto(registeredBy.Id, registeredBy.Username, registeredBy.FirstName, registeredBy.LastName),
            visit.EntryAt, visit.ExitAt, new VisitReasonDto(reason.Id, reason.Code, reason.Name),
            visit.Destination, visit.VisitedPerson, visit.Status.ToString().ToUpperInvariant(), visit.Notes,
            visit.CreatedAt, visit.UpdatedAt,
            visit.CompletedBy is null ? null : ToDto(visit.CompletedBy),
            visit.CancelledBy is null ? null : ToDto(visit.CancelledBy), visit.CancelledAt, visit.CancellationReason);
    }

    private static VisitUserDto ToDto(User user) => new(user.Id, user.Username, user.FirstName, user.LastName);

    private static string? MaskIdentification(string? value)
    {
        if (value is null) return null;
        var compact = value.Trim();
        if (compact.Length <= 4) return new string('*', compact.Length);
        return compact[..3] + new string('*', Math.Max(3, compact.Length - 7)) + compact[^4..];
    }
}
