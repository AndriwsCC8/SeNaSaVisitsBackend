using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Application.Validators;
using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Enums;

namespace SeNaSaVisits.Application.Services;

/// <summary>Application use cases for user administration, role replacement, and branch assignment history.</summary>
public sealed class UserManagementService(
    IUserRepository users,
    IRoleRepository roles,
    IUserBranchAssignmentRepository assignments,
    IBranchRepository branches,
    IPasswordHasher passwordHasher,
    IClock clock,
    ICurrentUser currentUser,
    IPermissionEvaluator permissionEvaluator,
    ITransactionRunner transactions,
    AuditService audit)
{
    public async Task<PageResult<UserDto>> SearchAsync(UserSearchRequest request, CancellationToken cancellationToken)
    {
        await EnsurePermission("MANAGE_USERS", null, cancellationToken).ConfigureAwait(false);
        request.Page.Validate();
        InputValidators.MaxLength(request.Search, 100, "search");
        var result = await users.SearchAsync(new UserSearchCriteria(request.Search, request.IsActive,
            request.BranchId, request.RoleCode, Now()), request.Page.Page, request.Page.PageSize, cancellationToken).ConfigureAwait(false);
        var mapped = result.Items.Select(user => MapUser(user)).ToArray();
        return new PageResult<UserDto>(mapped, result.Total, request.Page.Page, request.Page.PageSize);
    }

    public async Task<UserDto> GetAsync(long userId, CancellationToken cancellationToken)
    {
        await EnsurePermission("MANAGE_USERS", null, cancellationToken).ConfigureAwait(false);
        return MapUser(await GetUser(userId, cancellationToken).ConfigureAwait(false));
    }

    public async Task<UserDto> CreateAsync(UserCreateRequest request, AuditContext? auditContext, CancellationToken cancellationToken)
    {
        await EnsurePermission("MANAGE_USERS", null, cancellationToken).ConfigureAwait(false);
        if (request.BranchId is not null)
            await EnsurePermission("ASSIGN_USER_BRANCH", null, cancellationToken).ConfigureAwait(false);
        ValidateCreate(request);
        var actorId = currentUser.UserId;
        var user = new User
        {
            Username = request.Username,
            Email = request.Email,
            FirstName = request.FirstName,
            LastName = request.LastName,
            EmployeeCode = request.EmployeeCode,
            PasswordHash = passwordHasher.Hash(request.Password),
            IsActive = true,
            CreatedAt = Now(),
            UpdatedAt = Now()
        };

        return await transactions.ExecuteAsync(async ct =>
        {
            if (await users.UsernameExistsAsync(user.Username, null, ct).ConfigureAwait(false) ||
                (user.Email is not null && await users.EmailExistsAsync(user.Email, null, ct).ConfigureAwait(false)) ||
                (user.EmployeeCode is not null && await users.EmployeeCodeExistsAsync(user.EmployeeCode, null, ct).ConfigureAwait(false)))
                throw new ApplicationConflictException("Username, email or employee code already exists.");

            await users.AddAsync(user, ct).ConfigureAwait(false);
            if (request.RoleCode is not null)
                await ReplaceRole(user.Id, request.RoleCode, actorId, ct).ConfigureAwait(false);
            if (request.BranchId is not null)
                await CreateAssignmentCore(user.Id, new UserAssignmentRequest(request.BranchId.Value,
                    request.AssignmentValidFrom), actorId, ct).ConfigureAwait(false);
            await audit.RecordAsync(actorId, "CREATE_USER", "User", user.Id, request.BranchId,
                newValues: new Dictionary<string, object?>
                {
                    ["user_id"] = user.Id, ["username"] = user.Username, ["is_active"] = true,
                    ["role_code"] = request.RoleCode, ["branch_id"] = request.BranchId
                }, context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            var saved = await GetUser(user.Id, ct).ConfigureAwait(false);
            return MapUser(saved);
        }, cancellationToken).ConfigureAwait(false);
    }

    public async Task<UserDto> UpdateAsync(long userId, UserUpdateRequest request, AuditContext? auditContext, CancellationToken cancellationToken)
    {
        await EnsurePermission("MANAGE_USERS", null, cancellationToken).ConfigureAwait(false);
        return await transactions.ExecuteAsync(async ct =>
        {
            var user = await GetUser(userId, ct).ConfigureAwait(false);
            var oldValues = new Dictionary<string, object?>();
            var newValues = new Dictionary<string, object?>();
            if (request.Email.IsSpecified && request.Email.Value is not null && request.Email.Value != user.Email)
            {
                if (await users.EmailExistsAsync(request.Email.Value, userId, ct).ConfigureAwait(false))
                    throw new ApplicationConflictException("Email is already registered.");
                oldValues["email"] = user.Email; user.Email = request.Email.Value; newValues["email"] = user.Email;
            }
            if (request.FirstName.IsSpecified && request.FirstName.Value is not null)
            {
                InputValidators.StringLength(request.FirstName.Value, "first_name", 1, 100);
                oldValues["first_name"] = user.FirstName; user.FirstName = request.FirstName.Value; newValues["first_name"] = user.FirstName;
            }
            if (request.LastName.IsSpecified && request.LastName.Value is not null)
            {
                InputValidators.StringLength(request.LastName.Value, "last_name", 1, 100);
                oldValues["last_name"] = user.LastName; user.LastName = request.LastName.Value; newValues["last_name"] = user.LastName;
            }
            if (request.EmployeeCode.IsSpecified && request.EmployeeCode.Value is not null && request.EmployeeCode.Value != user.EmployeeCode)
            {
                if (await users.EmployeeCodeExistsAsync(request.EmployeeCode.Value, userId, ct).ConfigureAwait(false))
                    throw new ApplicationConflictException("Employee code is already registered.");
                oldValues["employee_code"] = user.EmployeeCode; user.EmployeeCode = request.EmployeeCode.Value; newValues["employee_code"] = user.EmployeeCode;
            }
            if (request.RoleCode.IsSpecified && request.RoleCode.Value is not null)
            {
                await ReplaceRole(userId, request.RoleCode.Value, currentUser.UserId, ct).ConfigureAwait(false);
                newValues["role_code"] = request.RoleCode.Value;
            }
            user.UpdatedAt = Now();
            await users.SaveChangesAsync(user, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "UPDATE_USER", "User", userId,
                oldValues: oldValues, newValues: newValues, context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            return MapUser(await GetUser(userId, ct).ConfigureAwait(false));
        }, cancellationToken).ConfigureAwait(false);
    }

    public async Task<UserDto> SetActiveAsync(long userId, bool active, AuditContext? auditContext, CancellationToken cancellationToken)
    {
        await EnsurePermission("MANAGE_USERS", null, cancellationToken).ConfigureAwait(false);
        return await transactions.ExecuteAsync(async ct =>
        {
            var user = await GetUser(userId, ct).ConfigureAwait(false);
            user.IsActive = active;
            user.DeactivatedAt = active ? null : Now();
            user.UpdatedAt = Now();
            await users.SaveChangesAsync(user, ct).ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, active ? "UPDATE_USER" : "DEACTIVATE_USER", "User", userId,
                oldValues: new Dictionary<string, object?> { ["is_active"] = !active },
                newValues: new Dictionary<string, object?> { ["is_active"] = active }, context: auditContext,
                cancellationToken: ct).ConfigureAwait(false);
            return MapUser(await GetUser(userId, ct).ConfigureAwait(false));
        }, cancellationToken).ConfigureAwait(false);
    }

    public async Task<IReadOnlyList<AssignmentDto>> ListAssignmentsAsync(long userId, CancellationToken cancellationToken)
    {
        await EnsurePermission("MANAGE_USERS", null, cancellationToken).ConfigureAwait(false);
        _ = await GetUser(userId, cancellationToken).ConfigureAwait(false);
        var items = await assignments.ListForUserAsync(userId, cancellationToken).ConfigureAwait(false);
        return items.OrderByDescending(item => item.ValidFrom).Select(UserDtoMapper.ToDto).ToArray();
    }

    public async Task<AssignmentDto> AssignBranchAsync(long userId, UserAssignmentRequest request,
        AuditContext? auditContext, CancellationToken cancellationToken)
    {
        await EnsurePermission("ASSIGN_USER_BRANCH", null, cancellationToken).ConfigureAwait(false);
        var actorId = currentUser.UserId;
        var assignment = await transactions.ExecuteAsync(async ct =>
        {
            var created = await CreateAssignmentCore(userId, request, actorId, ct).ConfigureAwait(false);
            await audit.RecordAsync(actorId, "ASSIGN_USER_BRANCH", "UserBranchAssignment", created.Id,
                created.BranchId, newValues: new Dictionary<string, object?>
                {
                    ["user_id"] = userId, ["branch_id"] = created.BranchId,
                    ["valid_from"] = created.ValidFrom, ["valid_until"] = created.ValidUntil, ["reason"] = created.Reason
                }, context: auditContext, cancellationToken: ct).ConfigureAwait(false);
            return created;
        }, cancellationToken).ConfigureAwait(false);
        return UserDtoMapper.ToDto(assignment);
    }

    public async Task<AssignmentDto> TransferAsync(long userId, UserTransferRequest request,
        AuditContext? auditContext, CancellationToken cancellationToken)
    {
        await EnsurePermission("MOVE_USER_BRANCH", null, cancellationToken).ConfigureAwait(false);
        var user = await GetUser(userId, cancellationToken).ConfigureAwait(false);
        if (!user.IsActive) throw new ApplicationValidationException("An inactive user cannot be transferred.");
        var branch = await branches.GetByIdAsync(request.NewBranchId, cancellationToken).ConfigureAwait(false)
            ?? throw new ApplicationNotFoundException("The requested branch does not exist.");
        if (!branch.IsActive) throw new ApplicationValidationException("The requested branch is inactive.");

        var effectiveAt = request.EffectiveAt is null ? Now() : ApplicationTime.ToUtc(request.EffectiveAt.Value);
        var created = await transactions.ExecuteWithTransactionAsync(async (transaction, ct) =>
        {
            // This protected read is the sole source of truth for conflict checks and the audit's prior branch.
            var history = await assignments.GetHistoryForTransferAsync(userId, transaction, ct).ConfigureAwait(false);
            var current = history.Where(item => item.IsEffectiveAt(effectiveAt)).ToArray();
            if (current.Length > 1)
                throw new ApplicationConflictException("Multiple current assignments exist for the user.");
            if (current.Length == 1 && current[0].BranchId == request.NewBranchId)
                throw new ApplicationConflictException("The user is already assigned to this branch.");

            var previousBranchId = current.Length == 1 ? current[0].BranchId : (long?)null;
            if (current.Length == 1)
            {
                current[0].ValidUntil = effectiveAt;
                current[0].Status = UserBranchAssignmentStatus.Ended;
                current[0].UpdatedAt = Now();
                current[0].Validate();
                await assignments.SaveTransferChangeAsync(current[0], transaction, ct).ConfigureAwait(false);
            }

            EnsureNoOverlap(history, effectiveAt, null);
            var newAssignment = new UserBranchAssignment
            {
                UserId = userId,
                BranchId = request.NewBranchId,
                Branch = branch,
                ValidFrom = effectiveAt,
                AssignedByUserId = currentUser.UserId,
                Reason = request.Reason,
                Status = UserBranchAssignmentStatus.Active,
                CreatedAt = Now(),
                UpdatedAt = Now()
            };
            newAssignment.Validate();
            var transferred = await assignments.AddTransferAssignmentAsync(newAssignment, transaction, ct)
                .ConfigureAwait(false);
            await audit.RecordAsync(currentUser.UserId, "MOVE_USER_BRANCH", "User", userId, transferred.BranchId,
                oldValues: new Dictionary<string, object?> { ["old_branch_id"] = previousBranchId },
                newValues: new Dictionary<string, object?>
                {
                    ["user_id"] = userId, ["new_branch_id"] = transferred.BranchId,
                    ["effective_at"] = effectiveAt, ["reason"] = request.Reason
                }, context: auditContext, transaction: transaction, cancellationToken: ct).ConfigureAwait(false);
            return transferred;
        }, cancellationToken).ConfigureAwait(false);
        return UserDtoMapper.ToDto(created);
    }

    public async Task<IReadOnlyList<RoleDto>> ListRolesAsync(long userId, CancellationToken cancellationToken)
    {
        await EnsurePermission("MANAGE_USERS", null, cancellationToken).ConfigureAwait(false);
        _ = await GetUser(userId, cancellationToken).ConfigureAwait(false);
        var userRoles = await roles.ListActiveForUserAsync(userId, cancellationToken).ConfigureAwait(false);
        return userRoles.Where(role => role.IsActive).Select(role => new RoleDto(role.Id, role.Code, role.Name)).ToArray();
    }

    private async Task<UserBranchAssignment> CreateAssignmentCore(long userId, UserAssignmentRequest request,
        long actorId, CancellationToken cancellationToken)
    {
        var user = await GetUser(userId, cancellationToken).ConfigureAwait(false);
        if (!user.IsActive) throw new ApplicationValidationException("An inactive user cannot be assigned to a branch.");
        var branch = await branches.GetByIdAsync(request.BranchId, cancellationToken).ConfigureAwait(false)
            ?? throw new ApplicationNotFoundException("The requested branch does not exist.");
        if (!branch.IsActive) throw new ApplicationValidationException("The requested branch is inactive.");

        var start = request.ValidFrom is null ? Now() : ApplicationTime.ToUtc(request.ValidFrom.Value);
        DateTime? end = request.ValidUntil is null ? null : ApplicationTime.ToUtc(request.ValidUntil.Value);
        if (end is not null && end <= start) throw new ApplicationValidationException("valid_until must be later than valid_from.");
        var existing = await assignments.ListForOverlapCheckAsync(userId, cancellationToken).ConfigureAwait(false);
        if (end is null && existing.Any(item => item.IsEffectiveAt(start)))
            throw new ApplicationConflictException("The user already has a current branch assignment.");
        EnsureNoOverlap(existing, start, end);

        var assignment = new UserBranchAssignment
        {
            UserId = userId, BranchId = request.BranchId, ValidFrom = start, ValidUntil = end,
            AssignedByUserId = actorId, Reason = request.Reason,
            Status = end is null ? UserBranchAssignmentStatus.Active : UserBranchAssignmentStatus.Ended,
            Branch = branch, CreatedAt = Now(), UpdatedAt = Now()
        };
        assignment.Validate();
        await assignments.AddAsync(assignment, cancellationToken).ConfigureAwait(false);
        return assignment;
    }

    private async Task ReplaceRole(long userId, string roleCode, long actorId, CancellationToken cancellationToken)
    {
        var role = await roles.GetByCodeAsync(roleCode, cancellationToken).ConfigureAwait(false)
            ?? throw new ApplicationNotFoundException("The requested role does not exist.");
        if (!role.IsActive) throw new ApplicationValidationException("The requested role is inactive.");
        await roles.ReplaceActiveRoleAsync(userId, role, actorId, Now(), cancellationToken).ConfigureAwait(false);
    }

    private async Task<User> GetUser(long userId, CancellationToken cancellationToken) =>
        await users.GetByIdAsync(userId, cancellationToken).ConfigureAwait(false)
        ?? throw new ApplicationNotFoundException("The requested user does not exist.");

    private UserDto MapUser(User user) => UserDtoMapper.ToDto(user, user.UserRoles.ToArray(), user.BranchAssignments.ToArray(), Now());

    private async Task EnsurePermission(string permission, long? branchId, CancellationToken cancellationToken) =>
        await EnsureAnyPermission([permission], branchId, cancellationToken).ConfigureAwait(false);

    private async Task EnsureAnyPermission(IReadOnlyList<string> permissionsToCheck, long? branchId, CancellationToken cancellationToken)
    {
        foreach (var permission in permissionsToCheck)
            if (await permissionEvaluator.HasPermissionAsync(currentUser.UserId, permission, branchId, cancellationToken).ConfigureAwait(false)) return;
        throw new ApplicationForbiddenException("The authenticated user does not have the required permission.");
    }

    private DateTime Now() => ApplicationTime.ToUtc(clock.UtcNow);

    private static void ValidateCreate(UserCreateRequest request)
    {
        InputValidators.StringLength(request.Username, "username", 1, 80);
        InputValidators.StringLength(request.FirstName, "first_name", 1, 100);
        InputValidators.StringLength(request.LastName, "last_name", 1, 100);
        InputValidators.StringLength(request.Password, "password", 8, 256);
        InputValidators.MaxLength(request.Email, 254, "email");
        InputValidators.MaxLength(request.EmployeeCode, 50, "employee_code");
        InputValidators.MaxLength(request.RoleCode, 50, "role_code");
    }

    private static void EnsureNoOverlap(IEnumerable<UserBranchAssignment> assignments, DateTime start, DateTime? end)
    {
        foreach (var existing in assignments)
        {
            var existingStart = ApplicationTime.ToUtc(existing.ValidFrom);
            var existingEnd = existing.ValidUntil is null ? (DateTime?)null : ApplicationTime.ToUtc(existing.ValidUntil.Value);
            if (existingStart < (end ?? DateTime.MaxValue) && (existingEnd is null || start < existingEnd))
                throw new ApplicationConflictException("The assignment interval overlaps existing history.");
        }
    }
}
