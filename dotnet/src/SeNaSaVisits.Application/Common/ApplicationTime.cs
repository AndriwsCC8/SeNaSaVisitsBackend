namespace SeNaSaVisits.Application.Common;

public static class ApplicationTime
{
    /// <summary>Matches Python's interpretation: aware values become UTC; naive values are assumed UTC.</summary>
    public static DateTime ToUtc(DateTime value) => value.Kind switch
    {
        DateTimeKind.Utc => value,
        DateTimeKind.Local => value.ToUniversalTime(),
        _ => DateTime.SpecifyKind(value, DateTimeKind.Utc)
    };
}
