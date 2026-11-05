using System.Collections;
using System.Globalization;
using System.Text.Json;
using SeNaSaVisits.Application.Common;
using SeNaSaVisits.Application.DTOs;
using SeNaSaVisits.Application.Interfaces;
using SeNaSaVisits.Domain.Entities;

namespace SeNaSaVisits.Application.Services;

/// <summary>Append-only audit orchestration and deterministic sensitive-key redaction.</summary>
public sealed class AuditService(IAuditWriter writer, IClock clock)
{
    private static readonly HashSet<string> SensitiveKeys = new(StringComparer.Ordinal)
    {
        "password", "passwordhash", "token", "accesstoken", "refreshtoken",
        "authorization", "secret", "apikey", "credentials"
    };

    public async Task RecordAsync(long? actorUserId, string action, string entityType, long? entityId = null,
        long? branchId = null, IReadOnlyDictionary<string, object?>? oldValues = null,
        IReadOnlyDictionary<string, object?>? newValues = null, AuditContext? context = null,
        IApplicationTransaction? transaction = null,
        CancellationToken cancellationToken = default)
    {
        if (action.Length > 60 || entityType.Length > 80)
        {
            throw new ApplicationValidationException("Audit action or entity type exceeds its schema length.");
        }

        var auditLog = new AuditLog
        {
            ActorUserId = actorUserId,
            Action = action,
            EntityType = entityType,
            EntityId = entityId,
            BranchId = branchId,
            OldValues = Serialize(oldValues),
            NewValues = Serialize(newValues),
            IpAddress = Truncate(context?.IpAddress, 45),
            UserAgent = Truncate(context?.UserAgent, 500),
            CorrelationId = Truncate(context?.CorrelationId, 100),
            CreatedAt = UtcDateTime.Normalize(clock.UtcNow)
        };

        await writer.AppendAsync(auditLog, cancellationToken, transaction).ConfigureAwait(false);
    }

    public static string? Serialize(IReadOnlyDictionary<string, object?>? values)
    {
        if (values is null || values.Count == 0) return null;
        var safe = Redact(values);
        return safe.Count == 0 ? null : JsonSerializer.Serialize(safe);
    }

    public static string? RedactSerialized(string? serialized)
    {
        if (string.IsNullOrEmpty(serialized)) return null;
        try
        {
            using var document = JsonDocument.Parse(serialized);
            object? parsed = ConvertJson(document.RootElement);
            var wrapper = parsed as IReadOnlyDictionary<string, object?> ?? new Dictionary<string, object?> { ["value"] = parsed };
            return Serialize(wrapper);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    private static SortedDictionary<string, object?> Redact(IEnumerable<KeyValuePair<string, object?>> values)
    {
        var result = new SortedDictionary<string, object?>(StringComparer.Ordinal);
        foreach (var (key, value) in values)
        {
            if (SensitiveKeys.Contains(NormalizeKey(key))) continue;
            result[key] = RedactValue(value);
        }
        return result;
    }

    private static object? RedactValue(object? value)
    {
        if (value is null) return null;
        if (value is DateTime dateTime) return FormatDateTime(dateTime);
        if (value is DateOnly date) return date.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture);
        if (value is IReadOnlyDictionary<string, object?> readOnlyDictionary) return Redact(readOnlyDictionary);
        if (value is IDictionary dictionary)
        {
            var pairs = new List<KeyValuePair<string, object?>>();
            foreach (DictionaryEntry entry in dictionary) pairs.Add(new KeyValuePair<string, object?>(Convert.ToString(entry.Key, CultureInfo.InvariantCulture) ?? string.Empty, entry.Value));
            return Redact(pairs);
        }
        if (value is IEnumerable sequence && value is not string)
        {
            var items = new List<object?>();
            foreach (var item in sequence) items.Add(RedactValue(item));
            return items;
        }
        return value;
    }

    private static object? ConvertJson(JsonElement element) => element.ValueKind switch
    {
        JsonValueKind.Object => Redact(element.EnumerateObject().Select(property => new KeyValuePair<string, object?>(property.Name, ConvertJson(property.Value)))),
        JsonValueKind.Array => element.EnumerateArray().Select(ConvertJson).ToArray(),
        JsonValueKind.String => element.GetString(),
        JsonValueKind.Number => element.TryGetInt64(out var number) ? number : element.GetDouble(),
        JsonValueKind.True => true,
        JsonValueKind.False => false,
        _ => null
    };

    private static string NormalizeKey(string key) => key.ToLowerInvariant().Replace("_", string.Empty, StringComparison.Ordinal).Replace("-", string.Empty, StringComparison.Ordinal);

    private static string? Truncate(string? value, int length) => string.IsNullOrEmpty(value) ? null : value[..Math.Min(value.Length, length)];

    private static string FormatDateTime(DateTime value)
    {
        var utc = UtcDateTime.Normalize(value);
        return utc.ToString("O", CultureInfo.InvariantCulture).Replace("Z", "+00:00", StringComparison.Ordinal);
    }

}
