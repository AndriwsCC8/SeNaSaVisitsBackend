using SeNaSaVisits.Domain.Entities;

namespace SeNaSaVisits.Application.Interfaces;

public sealed record VisitorSearchCriteria(string? Search, bool? IsActive, long? VisitorTypeId, bool IncludeContact);

public interface IVisitorRepository
{
    Task<Visitor?> GetByIdAsync(long visitorId, CancellationToken cancellationToken);

    /// <summary>Searches name, normalized identification and company; include email/phone only when IncludeContact is true.</summary>
    Task<(IReadOnlyList<Visitor> Items, int Total)> SearchAsync(
        VisitorSearchCriteria criteria, int page, int pageSize, CancellationToken cancellationToken);

    Task<bool> IdentificationExistsAsync(string normalizedIdentification, long? excludingVisitorId, CancellationToken cancellationToken);

    Task AddAsync(Visitor visitor, CancellationToken cancellationToken);

    Task SaveChangesAsync(Visitor visitor, CancellationToken cancellationToken);
}

public interface IVisitorTypeRepository
{
    Task<VisitorType?> GetByIdAsync(long visitorTypeId, CancellationToken cancellationToken);
}
