using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Domain.Entities;

namespace SeNaSaVisits.Application.DTOs;

public sealed record VisitorTypeDto(long Id, string Code, string Name);
public sealed record VisitorDto(long Id, string? Identification, string FirstName, string LastName,
    string? Phone, string? Email, bool ContactMasked, string? Company, VisitorTypeDto? VisitorType,
    bool IsActive, DateTime CreatedAt, DateTime UpdatedAt);
public sealed record VisitorSearchRequest(PageRequest Page, string? Search = null, bool? IsActive = null, long? VisitorTypeId = null);
public sealed record VisitorCreateRequest(string FirstName, string LastName, string? Identification = null,
    string? Phone = null, string? Email = null, string? Company = null, long? VisitorTypeId = null);
public sealed record VisitorUpdateRequest(FieldUpdate<string?> FirstName, FieldUpdate<string?> LastName,
    FieldUpdate<string?> Identification, FieldUpdate<string?> Phone, FieldUpdate<string?> Email,
    FieldUpdate<string?> Company, FieldUpdate<long?> VisitorTypeId);

internal static class VisitorDtoMapper
{
    public static VisitorDto ToDto(Visitor visitor, bool canViewContact)
    {
        var identification = visitor.Identification?.RawValue;
        return new VisitorDto(visitor.Id, MaskIdentification(identification), visitor.FirstName, visitor.LastName,
            canViewContact ? visitor.Phone : MaskPhone(visitor.Phone),
            canViewContact ? visitor.Email : MaskEmail(visitor.Email), !canViewContact,
            visitor.Company, visitor.VisitorType is null ? null : new VisitorTypeDto(
                visitor.VisitorType.Id, visitor.VisitorType.Code, visitor.VisitorType.Name),
            visitor.IsActive, visitor.CreatedAt, visitor.UpdatedAt);
    }

    private static string? MaskIdentification(string? value)
    {
        if (value is null) return null;
        var compact = value.Trim();
        if (compact.Length <= 4) return new string('*', compact.Length);
        var maskLength = Math.Max(3, compact.Length - 7);
        return compact[..3] + new string('*', maskLength) + compact[^4..];
    }

    private static string? MaskPhone(string? value)
    {
        if (string.IsNullOrEmpty(value)) return null;
        var compact = value.Trim();
        return compact.Length <= 4 ? new string('*', compact.Length) : "***" + compact[^2..];
    }

    private static string? MaskEmail(string? value)
    {
        if (string.IsNullOrEmpty(value)) return null;
        var (local, domain, hasSeparator) = SplitEmail(value.Trim());
        return !hasSeparator || local.Length == 0 ? "***" : $"{local[0]}***@{domain}";
    }

    private static (string Local, string Domain, bool HasSeparator) SplitEmail(string value)
    {
        var separator = value.IndexOf('@');
        return separator < 0 ? (value, string.Empty, false) : (value[..separator], value[(separator + 1)..], true);
    }
}
