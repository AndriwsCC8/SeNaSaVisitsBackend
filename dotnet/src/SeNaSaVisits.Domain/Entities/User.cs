using SeNaSaVisits.Domain.Common;

namespace SeNaSaVisits.Domain.Entities;

public sealed class User : TimestampedEntity
{
    public required string Username { get; set; }

    public string? Email { get; set; }

    public required string FirstName { get; set; }

    public required string LastName { get; set; }

    public string? EmployeeCode { get; set; }

    public required string PasswordHash { get; set; }

    public bool IsActive { get; set; } = true;

    public DateTime? DeactivatedAt { get; set; }

    public ICollection<UserRole> UserRoles { get; } = new List<UserRole>();

    public ICollection<UserRole> AssignedUserRoles { get; } = new List<UserRole>();

    public ICollection<RolePermission> AssignedRolePermissions { get; } = new List<RolePermission>();

    public ICollection<UserPermission> UserPermissions { get; } = new List<UserPermission>();

    public ICollection<UserPermission> AssignedUserPermissions { get; } = new List<UserPermission>();

    public ICollection<UserBranchAssignment> BranchAssignments { get; } = new List<UserBranchAssignment>();

    public ICollection<UserBranchAssignment> AssignedBranchAssignments { get; } = new List<UserBranchAssignment>();

    public ICollection<Visit> RegisteredVisits { get; } = new List<Visit>();

    public ICollection<Visit> CompletedVisits { get; } = new List<Visit>();

    public ICollection<Visit> CancelledVisits { get; } = new List<Visit>();

    public ICollection<AuditLog> AuditLogs { get; } = new List<AuditLog>();

    public ICollection<Notification> Notifications { get; } = new List<Notification>();
}
