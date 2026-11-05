using System.Text.RegularExpressions;
using SeNaSaVisits.Application.Common;

namespace SeNaSaVisits.Application.Validators;

public static partial class InputValidators
{
    public static void RequiredText(string? value, string field, int maximumLength)
    {
        if (string.IsNullOrWhiteSpace(value) || value.Trim().Length > maximumLength)
            throw new ApplicationValidationException($"{field} is required and must be at most {maximumLength} characters.");
    }

    public static void StringLength(string? value, string field, int minimumLength, int maximumLength)
    {
        if (value is null || value.Length < minimumLength || value.Length > maximumLength)
            throw new ApplicationValidationException($"{field} must contain between {minimumLength} and {maximumLength} characters.");
    }

    public static string NormalizeRequiredText(string? value, string field)
    {
        if (value is null) throw new ApplicationValidationException($"{field} cannot be empty.");
        var normalized = string.Join(' ', value.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        if (normalized.Length == 0) throw new ApplicationValidationException($"{field} cannot be empty.");
        return normalized;
    }

    public static string? ValidateEmail(string? value)
    {
        if (value is null) return null;
        var normalized = value.Trim();
        if (normalized.Length == 0 || !EmailPattern().IsMatch(normalized))
            throw new ApplicationValidationException("The supplied email is invalid.");
        return normalized;
    }

    public static void MaxLength(string? value, int maximumLength, string field)
    {
        if (value?.Length > maximumLength)
            throw new ApplicationValidationException($"{field} exceeds the maximum length of {maximumLength}.");
    }

    public static bool IsValidPageSize(int page, int pageSize, int maximumPageSize = 100) =>
        page >= 1 && pageSize >= 1 && pageSize <= maximumPageSize;

    [GeneratedRegex("^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$", RegexOptions.CultureInvariant)]
    private static partial Regex EmailPattern();
}
