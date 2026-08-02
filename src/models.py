from datetime import datetime
from uuid import uuid4

from config import (
    DB_URI,
)
from consts import TicketStatus
from peewee import (
    BooleanField,
    DateTimeField,
    ForeignKeyField,
    IntegerField,
    Model,
    SqliteDatabase,
    TextField,
    UUIDField,
)

sqlite_db = SqliteDatabase(
    DB_URI,
    pragmas={
        "journal_mode": "wal",
        "cache_size": -1 * 64000,  # 64MB
        "foreign_keys": True,
        "ignore_check_constraints": False,
    },
)


class BaseModel(Model):
    """
    Base model for all models
    """

    class Meta:
        database = sqlite_db


class User(BaseModel):
    """
    Data model representing a user
    """

    id = IntegerField(primary_key=True)
    first_name = TextField()

    last_name = TextField(null=True)
    username = TextField(null=True)
    language_code = TextField(null=True)

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(null=True)

    class Meta:
        table_name = "users"


class Employee(BaseModel):
    """
    Data model representing an employee
    """

    user = ForeignKeyField(
        User, backref="employees", to_field="id", primary_key=True
    )

    pseudonym = TextField(null=True)

    class Meta:
        table_name = "employees"


class SupportTicket(BaseModel):
    """
    Data model representing a support ticket
    """

    id = UUIDField(primary_key=True, default=uuid4)
    user = ForeignKeyField(User, backref="support_tickets", to_field="id")
    message = TextField()
    support_message_id = IntegerField(null=True)
    private_message_id = IntegerField(null=True)
    status = IntegerField(default=TicketStatus.OPEN)

    resolved_at = DateTimeField(null=True)
    resolved_by = ForeignKeyField(
        User, backref="support_tickets", to_field="id", null=True
    )

    created_at = DateTimeField(default=datetime.utcnow)
    updated_at = DateTimeField(null=True)

    class Meta:
        table_name = "support_tickets"


class TicketMessage(BaseModel):
    """
    One relayed message, in either direction, tied to its ticket.

    A ticket is a running conversation, so a single pair of message ids on the
    ticket is not enough: staff may reply to any message in the thread, and the
    reader may reply to any answer. This table is the lookup that turns a
    replied-to message back into a ticket, and into the message to answer on
    the other side.
    """

    id = UUIDField(primary_key=True, default=uuid4)
    ticket = ForeignKeyField(SupportTicket, backref="messages")
    # id of the message in the support group
    support_message_id = IntegerField(index=True)
    # id of the message in the reader's private chat
    private_message_id = IntegerField(index=True, null=True)
    # True when the message originated from support, False when from the reader
    from_staff = BooleanField(default=False)

    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "ticket_messages"


class UserBan(BaseModel):
    """
    Data model representing a user ban entry
    """

    user = ForeignKeyField(
        User, backref="banlist", to_field="id", primary_key=True
    )

    reason = TextField(null=True)

    created_at = DateTimeField(default=datetime.utcnow)

    class Meta:
        table_name = "user_banlist"


tables = BaseModel.__subclasses__()
