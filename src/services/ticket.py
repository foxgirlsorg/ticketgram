from datetime import datetime

from consts import TicketStatus
from models import SupportTicket, TicketMessage, User
from peewee import DoesNotExist


def get_open_ticket(user: User) -> SupportTicket | None:
    """Returns the reader's open ticket, or :obj:`None` if there is none"""
    return (
        SupportTicket.select()
        .where(
            (SupportTicket.user == user)
            & (SupportTicket.status == TicketStatus.OPEN)
        )
        .order_by(SupportTicket.created_at.desc())
        .first()
    )


def open_ticket(user: User, summary: str) -> SupportTicket:
    """Creates a new open ticket for the reader"""
    return SupportTicket.create(user=user, message=summary)


def close_ticket(ticket: SupportTicket, by_user: User):
    """Marks the :obj:`SupportTicket` as resolved by :obj:`User` and closes it"""
    ticket.status = TicketStatus.CLOSED
    ticket.resolved_at = datetime.utcnow()
    ticket.resolved_by = by_user.id
    ticket.save()


def record_message(
    ticket: SupportTicket,
    support_message_id: int,
    private_message_id: int | None,
    from_staff: bool = False,
) -> TicketMessage:
    """Remembers both ends of a relayed message so replies can be routed back"""
    return TicketMessage.create(
        ticket=ticket,
        support_message_id=support_message_id,
        private_message_id=private_message_id,
        from_staff=from_staff,
    )


def by_support_message(message_id: int) -> TicketMessage | None:
    """Finds the relayed message a support-group message belongs to"""
    try:
        return TicketMessage.get(
            TicketMessage.support_message_id == message_id
        )
    except DoesNotExist:
        return None


def by_private_message(message_id: int) -> TicketMessage | None:
    """Finds the relayed message a private-chat message belongs to"""
    try:
        return TicketMessage.get(
            TicketMessage.private_message_id == message_id
        )
    except DoesNotExist:
        return None
