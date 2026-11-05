namespace SeNaSaVisits.Application.Interfaces;

public interface IClock
{
    DateTime UtcNow { get; }
}

/// <summary>Identity comes from a trusted host adapter, never from a request's branch/user fields.</summary>
public interface ICurrentUser
{
    long UserId { get; }
}

/// <summary>Abstraction only; password hashing implementations belong outside Application.</summary>
public interface IPasswordHasher
{
    string Hash(string password);
}
