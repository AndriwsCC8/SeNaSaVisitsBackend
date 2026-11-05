using SeNaSaVisits.Domain.Common;
using SeNaSaVisits.Domain.Enums;
using SeNaSaVisits.Domain.Exceptions;

namespace SeNaSaVisits.Domain.Entities;

public sealed class UserBranchAssignment : TimestampedEntity
{
    public long UserId { get; set; }

    public long BranchId { get; set; }

    public DateTime ValidFrom { get; set; }

    public DateTime? ValidUntil { get; set; }

    public long AssignedByUserId { get; set; }

    public string? Reason { get; set; }

    public required UserBranchAssignmentStatus Status { get; set; }

    public User? User { get; set; }

    public Branch? Branch { get; set; }

    public User? AssignedBy { get; set; }

    /// <summary>Checks this assignment's inclusive-start, exclusive-end validity at an instant.</summary>
    public bool IsEffectiveAt(DateTime instant) =>
        Status == UserBranchAssignmentStatus.Active &&
        ValidFrom <= instant &&
        (ValidUntil is null || ValidUntil > instant);

    /// <summary>Validates the date and state constraints in the approved schema.</summary>
    public void Validate()
    {
        if (ValidUntil is not null && ValidUntil <= ValidFrom)
        {
            throw new DomainRuleViolationException("Assignment end must be later than its start.");
        }

        var hasValidStatusDates = Status switch
        {
            UserBranchAssignmentStatus.Active => ValidUntil is null,
            UserBranchAssignmentStatus.Ended or UserBranchAssignmentStatus.Cancelled => ValidUntil is not null,
            _ => false
        };

        if (!hasValidStatusDates)
        {
            throw new DomainRuleViolationException("Assignment status and end date are inconsistent.");
        }
    }
}
