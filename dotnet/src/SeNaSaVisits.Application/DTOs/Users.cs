using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Domain.Entities;

namespace SeNaSaVisits.Application.DTOs;

public sealed record RoleDto(long Id, string Code, string Name);
public sealed record BranchDto(long Id, string Code, string Name);
public sealed record AssignmentDto(long Id, long BranchId, BranchDto Branch, DateTime ValidFrom, DateTime? ValidUntil, string Status, string? Reason);
public sealed record UserDto(long Id, string Username, string? Email, string FirstName, string LastName,
    string? EmployeeCode, bool IsActive, DateTime CreatedAt, DateTime UpdatedAt, DateTime? DeactivatedAt,
    IReadOnlyList<RoleDto> Roles, AssignmentDto? CurrentAssignment);
public sealed record UserSearchRequest(PageRequest Page, string? Search = null, bool? IsActive = null, long? BranchId = null, string? RoleCode = null);
public sealed record UserCreateRequest(string Username, string? Email, string FirstName, string LastName,
    string? EmployeeCode, string Password, string? RoleCode = null, long? BranchId = null, DateTime? AssignmentValidFrom = null);
public sealed record UserUpdateRequest(FieldUpdate<string?> Email, FieldUpdate<string?> FirstName,
    FieldUpdate<string?> LastName, FieldUpdate<string?> EmployeeCode, FieldUpdate<string?> RoleCode);
public sealed record UserAssignmentRequest(long BranchId, DateTime? ValidFrom = null, DateTime? ValidUntil = null, string? Reason = null);
public sealed record UserTransferRequest(long NewBranchId, DateTime? EffectiveAt = null, string? Reason = null);

internal static class UserDtoMapper
{
    public static UserDto ToDto(User user, IReadOnlyList<UserRole> roles, IReadOnlyList<UserBranchAssignment> assignments, DateTime nowUtc)
    {
        var activeRoles = roles.Where(item => item.IsActive && item.Role is { IsActive: true })
            .Select(item => new RoleDto(item.Role!.Id, item.Role.Code, item.Role.Name)).ToArray();
        var current = assignments.Where(item => item.IsEffectiveAt(nowUtc) && item.Branch is { IsActive: true }).ToArray();
        AssignmentDto? currentDto = current.Length == 1 && current[0].Branch is not null
            ? ToDto(current[0])
            : null;
        return new UserDto(user.Id, user.Username, user.Email, user.FirstName, user.LastName,
            user.EmployeeCode, user.IsActive, user.CreatedAt, user.UpdatedAt, user.DeactivatedAt,
            activeRoles, currentDto);
    }

    public static AssignmentDto ToDto(UserBranchAssignment assignment)
    {
        if (assignment.Branch is null)
        {
            throw new InvalidOperationException("Assignment branch navigation must be loaded to create the application DTO.");
        }

        return new AssignmentDto(assignment.Id, assignment.BranchId,
            new BranchDto(assignment.Branch.Id, assignment.Branch.Code, assignment.Branch.Name),
            assignment.ValidFrom, assignment.ValidUntil, assignment.Status.ToString().ToUpperInvariant(), assignment.Reason);
    }
}
