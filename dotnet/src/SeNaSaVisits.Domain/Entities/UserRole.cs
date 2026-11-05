using SeNaSaVisits.Domain.Common;

namespace SeNaSaVisits.Domain.Entities;

public sealed class UserRole : TimestampedEntity
{
    public long UserId { get; set; }

    public long RoleId { get; set; }

    public long AssignedByUserId { get; set; }

    public DateTime AssignedAt { get; set; }

    public DateTime? RevokedAt { get; set; }

    public bool IsActive { get; set; } = true;

    public User? User { get; set; }

    public Role? Role { get; set; }

    public User? AssignedBy { get; set; }
}
