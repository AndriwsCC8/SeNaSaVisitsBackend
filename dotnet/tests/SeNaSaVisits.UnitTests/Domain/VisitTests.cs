using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;
using SeNaSaVisits.Domain.Exceptions;

namespace SeNaSaVisits.UnitTests.Domain;

public sealed class VisitTests
{
    [Fact]
    public void Complete_ActiveVisit_RecordsExitAndCompletingUser()
    {
        var entryAt = new DateTime(2026, 1, 1, 10, 0, 0, DateTimeKind.Utc);
        var exitAt = entryAt.AddHours(2);
        var visit = new Visit { EntryAt = entryAt };

        visit.Complete(completedByUserId: 12, exitAt);

        Assert.Equal(VisitStatus.Completed, visit.Status);
        Assert.Equal(exitAt, visit.ExitAt);
        Assert.Equal(12, visit.CompletedByUserId);
        visit.Validate();
    }

    [Fact]
    public void Complete_RejectsExitBeforeEntry()
    {
        var entryAt = new DateTime(2026, 1, 1, 10, 0, 0, DateTimeKind.Utc);
        var visit = new Visit { EntryAt = entryAt };

        Assert.Throws<DomainRuleViolationException>(() => visit.Complete(12, entryAt.AddTicks(-1)));
        Assert.Equal(VisitStatus.Active, visit.Status);
    }

    [Fact]
    public void Cancel_RequiresActiveVisitAndNormalizesRequiredReason()
    {
        var cancelledAt = new DateTime(2026, 1, 1, 11, 0, 0, DateTimeKind.Utc);
        var visit = new Visit();

        visit.Cancel(12, cancelledAt, "  No   se   presentó  ");

        Assert.Equal(VisitStatus.Cancelled, visit.Status);
        Assert.Equal(12, visit.CancelledByUserId);
        Assert.Equal(cancelledAt, visit.CancelledAt);
        Assert.Equal("No se presentó", visit.CancellationReason);
        visit.Validate();
    }

    [Fact]
    public void Cancel_RejectsBlankReason()
    {
        var visit = new Visit();

        Assert.Throws<DomainRuleViolationException>(() => visit.Cancel(12, DateTime.UtcNow, "  \t "));
        Assert.Equal(VisitStatus.Active, visit.Status);
    }

    [Fact]
    public void CompletedVisitCannotBeCancelledAgain()
    {
        var visit = new Visit { EntryAt = DateTime.UtcNow };
        visit.Complete(12, visit.EntryAt);

        Assert.Throws<DomainRuleViolationException>(() => visit.Cancel(12, DateTime.UtcNow, "Motivo"));
    }
}
