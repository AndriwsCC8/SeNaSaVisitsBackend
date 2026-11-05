namespace SeNaSaVisits.Application.Interfaces;

/// <summary>
/// Opaque transaction scope supplied by Infrastructure. Repositories must bind commands using this scope
/// to the same connection and transaction that the runner opened; Application cannot inspect provider details.
/// </summary>
public interface IApplicationTransaction;

/// <summary>Runs a caller-supplied application operation in one infrastructure transaction.</summary>
public interface ITransactionRunner
{
    Task<T> ExecuteAsync<T>(Func<CancellationToken, Task<T>> operation, CancellationToken cancellationToken);

    /// <summary>
    /// Opens one transaction and passes its opaque scope to every participating repository call.
    /// Commit only after the delegate succeeds; rollback if it throws or is cancelled.
    /// </summary>
    Task<T> ExecuteWithTransactionAsync<T>(
        Func<IApplicationTransaction, CancellationToken, Task<T>> operation,
        CancellationToken cancellationToken);
}
