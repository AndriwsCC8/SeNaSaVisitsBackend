using SeNaSaVisits.Domain.Common;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.Domain.Entities;

public sealed class Permission : TimestampedEntity
{
    public required string Code { get; set; }

    public required string Name { get; set; }

    public string? Description { get; set; }

    public required string Resource { get; set; }

    public required string Action { get; set; }

    public required PermissionScope Scope { get; set; }

    public bool IsActive { get; set; } = true;

    public ICollection<RolePermission> RolePermissions { get; } = new List<RolePermission>();

    public ICollection<UserPermission> UserPermissions { get; } = new List<UserPermission>();
}
