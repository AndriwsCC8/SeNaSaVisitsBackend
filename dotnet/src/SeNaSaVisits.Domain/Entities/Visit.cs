using SeNaSaVisits.Domain.Common;
using SeNaSaVisits.Domain.Enums;
using SeNaSaVisits.Domain.Exceptions;

namespace SeNaSaVisits.Domain.Entities;

public sealed class Visit : TimestampedEntity
{
    public long VisitorId { get; set; }

    public long BranchId { get; set; }

    public long RegisteredByUserId { get; set; }

    public DateTime EntryAt { get; set; }

    public DateTime? ExitAt { get; private set; }

    public long ReasonId { get; set; }

    public string? Destination { get; set; }

    public string? VisitedPerson { get; set; }

    public VisitStatus Status { get; private set; } = VisitStatus.Active;

    public string? Notes { get; set; }

    public long? CompletedByUserId { get; private set; }

    public long? CancelledByUserId { get; private set; }

    public DateTime? CancelledAt { get; private set; }

    public string? CancellationReason { get; private set; }

    public Visitor? Visitor { get; set; }

    public Branch? Branch { get; set; }

    public User? RegisteredBy { get; set; }

    public User? CompletedBy { get; set; }

    public User? CancelledBy { get; set; }

    public VisitReason? Reason { get; set; }

    public void Complete(long completedByUserId, DateTime exitAt)
    {
        EnsureActive();
        if (exitAt < EntryAt)
        {
            throw new DomainRuleViolationException("Visit exit time cannot be earlier than its entry time.");
        }

        Status = VisitStatus.Completed;
        ExitAt = exitAt;
        CompletedByUserId = completedByUserId;
    }

    public void Cancel(long cancelledByUserId, DateTime cancelledAt, string cancellationReason)
    {
        EnsureActive();
        var normalizedReason = NormalizeRequiredText(cancellationReason);

        Status = VisitStatus.Cancelled;
        CancelledByUserId = cancelledByUserId;
        CancelledAt = cancelledAt;
        CancellationReason = normalizedReason;
    }

    /// <summary>Validates checks represented by the approved visits table schema.</summary>
    public void Validate()
    {
        if (!Enum.IsDefined(Status))
        {
            throw new DomainRuleViolationException("Visit status is not supported.");
        }

        if (ExitAt is not null && ExitAt < EntryAt)
        {
            throw new DomainRuleViolationException("Visit exit time cannot be earlier than its entry time.");
        }

        if (Status == VisitStatus.Cancelled &&
            (CancelledByUserId is null || CancelledAt is null || CancellationReason is null))
        {
            throw new DomainRuleViolationException("Cancelled visits require cancellation details.");
        }
    }

    private void EnsureActive()
    {
        if (Status != VisitStatus.Active)
        {
            throw new DomainRuleViolationException("Only active visits can be completed or cancelled.");
        }
    }

    private static string NormalizeRequiredText(string value)
    {
        ArgumentNullException.ThrowIfNull(value);
        var normalized = string.Join(' ', value.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        if (normalized.Length == 0)
        {
            throw new DomainRuleViolationException("Cancellation reason cannot be empty.");
        }

        return normalized;
    }
}
