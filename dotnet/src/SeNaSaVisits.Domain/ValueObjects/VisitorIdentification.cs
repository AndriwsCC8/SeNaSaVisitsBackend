namespace SeNaSaVisits.Domain.ValueObjects;

/// <summary>
/// Carries the visitor identification as entered (trimmed at the ends) and its
/// database deduplication form. Whitespace is removed and casing is uppercased;
/// punctuation, including hyphens, is preserved to match the current backend.
/// </summary>
public sealed record VisitorIdentification
{
    private VisitorIdentification(string rawValue, string? normalizedValue)
    {
        RawValue = rawValue;
        NormalizedValue = normalizedValue;
    }

    public string RawValue { get; }

    public string? NormalizedValue { get; }

    public static VisitorIdentification? From(string? value)
    {
        if (value is null)
        {
            return null;
        }

        var rawValue = value.Trim();
        var normalizedValue = string.Concat(rawValue.Where(character => !char.IsWhiteSpace(character)))
            .ToUpperInvariant();

        return new VisitorIdentification(rawValue, normalizedValue.Length == 0 ? null : normalizedValue);
    }
}
