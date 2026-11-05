namespace SeNaSaVisits.Domain.Common;

/// <summary>Base identity shared by the approved persisted entities.</summary>
public abstract class Entity
{
    public long Id { get; set; }
}

/// <summary>Persistence timestamps present on entities with the existing timestamp mixin.</summary>
public abstract class TimestampedEntity : Entity
{
    public DateTime CreatedAt { get; set; }

    public DateTime UpdatedAt { get; set; }
}

/// <summary>Persistence entities that have CreatedAt but no UpdatedAt column.</summary>
public abstract class CreatedEntity : Entity
{
    public DateTime CreatedAt { get; set; }
}
