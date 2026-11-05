using SeNaSaVisits.Domain.Common;

namespace SeNaSaVisits.Domain.Entities;

public sealed class RolePermission : Entity
{
    public long RoleId { get; set; }

    public long PermissionId { get; set; }

    public DateTime AssignedAt { get; set; }

    public long AssignedByUserId { get; set; }

    public bool IsActive { get; set; } = true;

    public Role? Role { get; set; }

    public Permission? Permission { get; set; }

    public User? AssignedBy { get; set; }
}
