using SeNaSaVisits.Domain.Common;
using SeNaSaVisits.Domain.Enums;
using SeNaSaVisits.Domain.Exceptions;

namespace SeNaSaVisits.Domain.Entities;

public sealed class UserPermission : CreatedEntity
{
    public long UserId { get; set; }

    public long PermissionId { get; set; }

    public long? BranchId { get; set; }

    public required PermissionEffect Effect { get; set; }

    public DateTime ValidFrom { get; set; }

    public DateTime? ValidUntil { get; set; }

    public long AssignedByUserId { get; set; }

    public bool IsActive { get; set; } = true;

    public User? User { get; set; }

    public Permission? Permission { get; set; }

    public Branch? Branch { get; set; }

    public User? AssignedBy { get; set; }

    public bool IsEffectiveAt(DateTime instant) =>
        IsActive && ValidFrom <= instant && (ValidUntil is null || ValidUntil > instant);

    public void Validate()
    {
        if (ValidUntil is not null && ValidUntil <= ValidFrom)
        {
            throw new DomainRuleViolationException("Permission end must be later than its start.");
        }
    }
}
