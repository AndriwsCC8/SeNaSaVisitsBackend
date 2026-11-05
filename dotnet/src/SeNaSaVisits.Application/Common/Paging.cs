namespace SeNaSaVisits.Application.Common;

public sealed record PageRequest(int Page = 1, int PageSize = 20)
{
    public void Validate(int maximumPageSize = 100)
    {
        if (Page < 1 || PageSize < 1 || PageSize > maximumPageSize)
        {
            throw new ApplicationValidationException($"Page must be >= 1 and page size must be between 1 and {maximumPageSize}.");
        }
    }
}

public sealed record PageResult<T>(IReadOnlyList<T> Items, int Total, int Page, int PageSize);

/// <summary>Preserves the distinction between an omitted PATCH field and an explicit null.</summary>
public readonly record struct FieldUpdate<T>(bool IsSpecified, T? Value)
{
    public static FieldUpdate<T> Omitted => new(false, default);

    public static FieldUpdate<T> Specified(T? value) => new(true, value);
}
