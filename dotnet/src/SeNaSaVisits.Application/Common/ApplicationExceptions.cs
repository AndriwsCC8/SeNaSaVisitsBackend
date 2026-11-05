namespace SeNaSaVisits.Application.Common;

public abstract class ApplicationExceptionBase(string message) : Exception(message);

public sealed class ApplicationNotFoundException(string message) : ApplicationExceptionBase(message);

public sealed class ApplicationConflictException(string message) : ApplicationExceptionBase(message);

public sealed class ApplicationValidationException(string message) : ApplicationExceptionBase(message);

public sealed class ApplicationForbiddenException(string message) : ApplicationExceptionBase(message);
