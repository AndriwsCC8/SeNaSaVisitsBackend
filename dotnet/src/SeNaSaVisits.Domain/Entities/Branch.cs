using SeNaSaVisits.Domain.Common;

namespace SeNaSaVisits.Domain.Entities;

public sealed class Branch : TimestampedEntity
{
    public required string Code { get; set; }

    public required string Name { get; set; }

    public long BranchTypeId { get; set; }

    public string? Region { get; set; }

    public string? Address { get; set; }

    public string? Phone { get; set; }

    public bool IsActive { get; set; } = true;

    public BranchType? BranchType { get; set; }

    public ICollection<UserPermission> UserPermissions { get; } = new List<UserPermission>();

    public ICollection<UserBranchAssignment> UserBranchAssignments { get; } = new List<UserBranchAssignment>();

    public ICollection<Visit> Visits { get; } = new List<Visit>();

    public ICollection<AuditLog> AuditLogs { get; } = new List<AuditLog>();

    public ICollection<Notification> Notifications { get; } = new List<Notification>();
}
