using SeNaSaVisits.Domain.Entities;
using SeNaSaVisits.Domain.Exceptions;

namespace SeNaSaVisits.UnitTests.Domain;

public sealed class NotificationTests
{
    [Fact]
    public void Validate_AcceptsUnreadWithoutReadTimestamp()
    {
        var notification = Create(isRead: false, readAt: null);

        notification.Validate();
    }

    [Fact]
    public void Validate_AcceptsReadWithReadTimestamp()
    {
        var notification = Create(isRead: true, readAt: DateTime.UtcNow);

        notification.Validate();
    }

    [Theory]
    [InlineData(false, true)]
    [InlineData(true, false)]
    public void Validate_RejectsInconsistentReadState(bool isRead, bool hasReadAt)
    {
        var notification = Create(isRead, hasReadAt ? DateTime.UtcNow : null);

        Assert.Throws<DomainRuleViolationException>(notification.Validate);
    }

    private static Notification Create(bool isRead, DateTime? readAt) => new()
    {
        Title = "Title",
        Message = "Message",
        Type = "Type",
        IsRead = isRead,
        ReadAt = readAt
    };
}
