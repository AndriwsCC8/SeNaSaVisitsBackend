using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.Interfaces;

namespace SeNaSaVisits.Application.Services;

public sealed record BranchContext(long UserId, long BranchId, long AssignmentId);

public sealed class BranchAccessService(IBranchAssignmentReader assignments, IClock clock)
{
    public async Task<BranchContext?> GetCurrentContextAsync(long userId, CancellationToken cancellationToken)
    {
        var now = UtcDateTime.Normalize(clock.UtcNow);
        var current = await assignments.GetCurrentAssignmentsAsync(userId, now, cancellationToken).ConfigureAwait(false);
        var valid = current.Where(item => item.Assignment.IsEffectiveAt(now)).ToArray();
        if (valid.Length != 1 || !valid[0].BranchIsActive)
        {
            return null;
        }

        return new BranchContext(userId, valid[0].Assignment.BranchId, valid[0].Assignment.Id);
    }

    public async Task<BranchContext> RequireCurrentContextAsync(long userId, CancellationToken cancellationToken)
    {
        return await GetCurrentContextAsync(userId, cancellationToken).ConfigureAwait(false)
            ?? throw new ApplicationForbiddenException("No single active branch assignment is currently valid.");
    }

    public async Task<bool> HasCurrentBranchAsync(long userId, long branchId, CancellationToken cancellationToken)
    {
        var context = await GetCurrentContextAsync(userId, cancellationToken).ConfigureAwait(false);
        return context?.BranchId == branchId;
    }

    internal static DateTime Normalize(DateTime value) => UtcDateTime.Normalize(value);
}

internal static class UtcDateTime
{
    public static DateTime Normalize(DateTime value) => value.Kind switch
    {
        DateTimeKind.Utc => value,
        DateTimeKind.Local => value.ToUniversalTime(),
        _ => DateTime.SpecifyKind(value, DateTimeKind.Utc)
    };
}
