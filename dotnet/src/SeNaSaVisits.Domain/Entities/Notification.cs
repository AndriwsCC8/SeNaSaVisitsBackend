using SeNaSaVisits.Domain.Common;
using SeNaSaVisits.Domain.Exceptions;

namespace SeNaSaVisits.Domain.Entities;

public sealed class Notification : CreatedEntity
{
    public long UserId { get; set; }

    public long? BranchId { get; set; }

    public required string Title { get; set; }

    public required string Message { get; set; }

    public required string Type { get; set; }

    public bool IsRead { get; set; }

    public DateTime? ReadAt { get; set; }

    public string? RelatedEntityType { get; set; }

    public long? RelatedEntityId { get; set; }

    public User? User { get; set; }

    public Branch? Branch { get; set; }

    public void Validate()
    {
        if (IsRead != (ReadAt is not null))
        {
            throw new DomainRuleViolationException("Notification read state and timestamp are inconsistent.");
        }
    }
}
