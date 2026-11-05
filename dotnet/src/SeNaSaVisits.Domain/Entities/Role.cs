using SeNaSaVisits.Domain.Common;

namespace SeNaSaVisits.Domain.Entities;

public sealed class Role : TimestampedEntity
{
    public required string Code { get; set; }

    public required string Name { get; set; }

    public string? Description { get; set; }

    public bool IsActive { get; set; } = true;

    public ICollection<UserRole> UserRoles { get; } = new List<UserRole>();

    public ICollection<RolePermission> RolePermissions { get; } = new List<RolePermission>();
}
