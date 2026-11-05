using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;
using SeNaSaVisits.Domain.Exceptions;

namespace SeNaSaVisits.UnitTests.Domain;

public sealed class UserPermissionTests
{
    [Fact]
    public void IsEffectiveAt_UsesInclusiveStartAndExclusiveEndAndRequiresActiveGrant()
    {
        var startsAt = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var endsAt = startsAt.AddDays(1);
        var permission = new UserPermission
        {
            Effect = PermissionEffect.Deny,
            IsActive = true,
            ValidFrom = startsAt,
            ValidUntil = endsAt
        };

        Assert.False(permission.IsEffectiveAt(startsAt.AddTicks(-1)));
        Assert.True(permission.IsEffectiveAt(startsAt));
        Assert.False(permission.IsEffectiveAt(endsAt));
        permission.IsActive = false;
        Assert.False(permission.IsEffectiveAt(startsAt));
    }

    [Fact]
    public void Validate_RejectsEndAtOrBeforeStart()
    {
        var instant = DateTime.UtcNow;
        var permission = new UserPermission
        {
            Effect = PermissionEffect.Allow,
            ValidFrom = instant,
            ValidUntil = instant
        };

        Assert.Throws<DomainRuleViolationException>(permission.Validate);
    }
}
