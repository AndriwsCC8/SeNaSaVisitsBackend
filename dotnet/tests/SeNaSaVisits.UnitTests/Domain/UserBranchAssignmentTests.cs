using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;
using SeNaSaVisits.Domain.Exceptions;

namespace SeNaSaVisits.UnitTests.Domain;

public sealed class UserBranchAssignmentTests
{
    [Fact]
    public void IsEffectiveAt_UsesInclusiveStartAndExclusiveEnd()
    {
        var startsAt = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var endsAt = startsAt.AddDays(10);
        var assignment = new UserBranchAssignment
        {
            Status = UserBranchAssignmentStatus.Active,
            ValidFrom = startsAt,
            ValidUntil = endsAt
        };

        Assert.False(assignment.IsEffectiveAt(startsAt.AddTicks(-1)));
        Assert.True(assignment.IsEffectiveAt(startsAt));
        Assert.True(assignment.IsEffectiveAt(endsAt.AddTicks(-1)));
        Assert.False(assignment.IsEffectiveAt(endsAt));
    }

    [Fact]
    public void IsEffectiveAt_RequiresActiveStatus()
    {
        var assignment = new UserBranchAssignment
        {
            Status = UserBranchAssignmentStatus.Ended,
            ValidFrom = DateTime.UtcNow.AddDays(-1),
            ValidUntil = DateTime.UtcNow.AddDays(1)
        };

        Assert.False(assignment.IsEffectiveAt(DateTime.UtcNow));
    }

    [Fact]
    public void Validate_RejectsEndAtOrBeforeStart()
    {
        var instant = DateTime.UtcNow;
        var assignment = new UserBranchAssignment
        {
            Status = UserBranchAssignmentStatus.Ended,
            ValidFrom = instant,
            ValidUntil = instant
        };

        Assert.Throws<DomainRuleViolationException>(assignment.Validate);
    }

    [Fact]
    public void Validate_RequiresStatusAndEndDateToAgree()
    {
        var assignment = new UserBranchAssignment
        {
            Status = UserBranchAssignmentStatus.Active,
            ValidFrom = DateTime.UtcNow,
            ValidUntil = DateTime.UtcNow.AddDays(1)
        };

        Assert.Throws<DomainRuleViolationException>(assignment.Validate);
    }

    [Fact]
    public void Validate_AllowsValidEndedAssignment()
    {
        var startsAt = DateTime.UtcNow;
        var assignment = new UserBranchAssignment
        {
            Status = UserBranchAssignmentStatus.Ended,
            ValidFrom = startsAt,
            ValidUntil = startsAt.AddDays(1)
        };

        assignment.Validate();
    }
}
