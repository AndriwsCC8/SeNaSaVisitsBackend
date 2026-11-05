namespace SeNaSaVisits.Domain.Exceptions;

/// <summary>Represents a violation of a confirmed domain invariant.</summary>
public sealed class DomainRuleViolationException(string message) : InvalidOperationException(message);
