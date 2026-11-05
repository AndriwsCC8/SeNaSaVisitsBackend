using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Services;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.UnitTests.Application;

public sealed class DashboardAndReportUseCaseTests
{
    private static readonly DateTime Now = new(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc);

    [Fact]
    public async Task DashboardUsesCurrentBranchUnlessGlobalPermissionIsGranted()
    {
        var reader = new FakeDashboardReader();
        var permissions = new FakePermissions(global: false);
        var service = new DashboardService(reader, permissions, CreateBranchAccess(), new FakeCurrentUser());

        var branchResult = await service.SummaryAsync(new ScopedDateRequest(), default);
        Assert.Equal(7, branchResult.BranchId);
        Assert.Equal(7, reader.LastBranchId);

        permissions.Global = true;
        var globalResult = await service.SummaryAsync(new ScopedDateRequest(), default);
        Assert.True(globalResult.BranchId is null);
        Assert.True(reader.LastBranchId is null);
    }

    [Fact]
    public async Task DashboardRejectsInvalidExclusiveDateRange()
    {
        var service = new DashboardService(new FakeDashboardReader(), new FakePermissions(false),
            CreateBranchAccess(), new FakeCurrentUser());
        var date = new DateTime(2026, 10, 1, 12, 0, 0, DateTimeKind.Utc);

        await Assert.ThrowsAsync<ApplicationValidationException>(() =>
            service.SummaryAsync(new ScopedDateRequest(date, date), default));
    }

    [Fact]
    public async Task ReportBranchUserCannotWidenScopeAndGlobalBranchGroupingIsExplicit()
    {
        var reader = new FakeReportReader();
        var permissions = new FakePermissions(global: false);
        var service = new VisitReportService(reader, permissions, CreateBranchAccess(), new FakeCurrentUser());

        await Assert.ThrowsAsync<ApplicationForbiddenException>(() => service.SearchAsync(
            new VisitReportFilters(BranchId: 8), new PageRequest(), default));
        Assert.Null(reader.LastScopeBranch);

        await Assert.ThrowsAsync<ApplicationValidationException>(() => service.SummaryAsync(
            new VisitReportFilters(), VisitReportGroupBy.Branch, default));
        permissions.Global = true;
        await service.SummaryAsync(new VisitReportFilters(BranchId: 8), VisitReportGroupBy.Branch, default);
        Assert.True(reader.LastScopeBranch is null);
        Assert.Equal(8, reader.LastGroupFilters!.BranchId);
        Assert.Equal("branch", reader.LastGroupBy);
    }

    private static BranchAccessService CreateBranchAccess() =>
        new(new OneBranchAssignmentReader(), new FakeClock());

    private sealed class FakeDashboardReader : IDashboardReader
    {
        public long? LastBranchId { get; private set; }
        public Task<DashboardAggregate> GetSummaryAsync(long? branchId, DateTime? dateFromUtc, DateTime? dateToUtc, CancellationToken cancellationToken)
        {
            LastBranchId = branchId;
            return Task.FromResult(new DashboardAggregate(1, 1, 0, 0, 1));
        }
        public Task<IReadOnlyList<DashboardDay>> GetVisitsByDayAsync(long? branchId, DateTime? dateFromUtc, DateTime? dateToUtc, CancellationToken cancellationToken) => Task.FromResult<IReadOnlyList<DashboardDay>>([]);
        public Task<IReadOnlyList<DistributionItem>> GetVisitsByStatusAsync(long? branchId, DateTime? dateFromUtc, DateTime? dateToUtc, CancellationToken cancellationToken) => Task.FromResult<IReadOnlyList<DistributionItem>>([]);
        public Task<IReadOnlyList<DistributionItem>> GetVisitsByReasonAsync(long? branchId, DateTime? dateFromUtc, DateTime? dateToUtc, CancellationToken cancellationToken) => Task.FromResult<IReadOnlyList<DistributionItem>>([]);
    }

    private sealed class FakeReportReader : IVisitReportReader
    {
        public long? LastScopeBranch { get; private set; }
        public string? LastGroupBy { get; private set; }
        public VisitReportSearch? LastGroupFilters { get; private set; }
        public Task<(IReadOnlyList<VisitReportRow> Items, int Total)> SearchAsync(VisitReportSearch filters, long? scopedBranchId, int page, int pageSize, CancellationToken cancellationToken)
        {
            LastScopeBranch = scopedBranchId;
            return Task.FromResult<(IReadOnlyList<VisitReportRow>, int)>(([], 0));
        }
        public Task<IReadOnlyList<DistributionItem>> GroupAsync(VisitReportSearch filters, long? scopedBranchId, string groupBy, CancellationToken cancellationToken)
        {
            LastScopeBranch = scopedBranchId;
            LastGroupBy = groupBy;
            LastGroupFilters = filters;
            return Task.FromResult<IReadOnlyList<DistributionItem>>([]);
        }
        public Task<bool> BranchExistsAndIsActiveAsync(long branchId, CancellationToken cancellationToken) => Task.FromResult(true);
        public Task<bool> ReasonExistsAsync(long reasonId, CancellationToken cancellationToken) => Task.FromResult(true);
        public Task<bool> VisitorExistsAsync(long visitorId, CancellationToken cancellationToken) => Task.FromResult(true);
        public Task<bool> UserExistsAsync(long userId, CancellationToken cancellationToken) => Task.FromResult(true);
    }

    private sealed class FakePermissions(bool global) : IPermissionEvaluator
    {
        public bool Global { get; set; } = global;
        public Task<bool> HasPermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) =>
            Task.FromResult(permissionCode == "VIEW_GLOBAL_REPORTS" && Global);
        public Task RequirePermissionAsync(long userId, string permissionCode, long? branchId, CancellationToken cancellationToken) =>
            permissionCode == "VIEW_REPORTS" && !Global
                ? Task.CompletedTask
                : Task.FromException(new ApplicationForbiddenException("Forbidden"));
    }

    private sealed class FakeCurrentUser : ICurrentUser { public long UserId => 1; }
    private sealed class FakeClock : IClock { public DateTime UtcNow => Now; }
    private sealed class OneBranchAssignmentReader : IBranchAssignmentReader
    {
        public Task<IReadOnlyList<CurrentBranchAssignment>> GetCurrentAssignmentsAsync(long userId, DateTime atUtc, CancellationToken cancellationToken)
        {
            var branch = new Branch { Id = 7, Code = "B", Name = "Branch", BranchTypeId = 1, IsActive = true };
            var assignment = new UserBranchAssignment { Id = 9, UserId = userId, BranchId = 7,
                AssignedByUserId = userId, Branch = branch, Status = UserBranchAssignmentStatus.Active, ValidFrom = Now.AddDays(-1) };
            return Task.FromResult<IReadOnlyList<CurrentBranchAssignment>>([new CurrentBranchAssignment(assignment, true)]);
        }
    }
}
