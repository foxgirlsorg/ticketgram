from enum import IntEnum, StrEnum

APPLICATION_NAME = "ticketgram"

MAX_SUMMARY_LINE_LENGTH = 48

TICKET_AGE_WARNING = 60 * 60 * 24  # day

TICKETS_PER_PAGE = 10

# Every message the bot posts into the support group is prefixed with
# "#T<8 hex chars of the ticket uuid>". Telegram indexes it as a hashtag, so
# tapping or searching it pulls up the whole conversation.
TICKET_TAG_PREFIX = "T"
TICKET_TAG_LENGTH = 8

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | "
    "%(name)s::%(funcName)s (line %(lineno)s) | %(message)s"
)


class WeekDay(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class TicketStatus(IntEnum):
    OPEN = 0
    CLOSED = 1


class TicketActions(StrEnum):
    SPAM = "MARK_AS_SPAM"
    CLOSE = "CLOSE_TICKET"


class PaginationActions(StrEnum):
    PREVIOUS = "PREV_PAGE"
    REFRESH = "UPD_PAGE"
    NEXT = "NEXT_PAGE"
