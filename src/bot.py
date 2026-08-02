import logging
from warnings import filterwarnings

from callbacks import (
    ban_user,
    error_handler,
    leave_chat,
    open_tickets,
    post_init,
    preprocess_update,
    process_user_message,
    set_staff_pseudonym,
    start,
    ticket,
    ticket_actions,
    ticket_response,
    unban_user,
)
from config import AUTHORIZED_GROUP_ID, TELEGRAM_TOKEN
from consts import LOG_FORMAT
from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    TypeHandler,
    filters,
)
from telegram.warnings import PTBUserWarning
from utils import validate_ticket_query

logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
# suppress the noisy httpx
__httpx_logger = logging.getLogger("httpx")
__httpx_logger.setLevel(logging.WARNING)
# suppress the PTB warning
filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)

__logger = logging.getLogger(__name__)

if __name__ == "__main__":
    application = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )
    # runs checks before passing the update to other handlers
    application.add_handler(TypeHandler(Update, preprocess_update), -1)
    # leaves from unauthorized chats and channels
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS
            & ~filters.StatusUpdate.LEFT_CHAT_MEMBER
            & ~filters.Chat(chat_id=AUTHORIZED_GROUP_ID),
            leave_chat,
        )
    )
    # Client side of the bot
    application.add_handler(
        CommandHandler("start", start, filters.ChatType.PRIVATE)
    )
    application.add_handler(
        CommandHandler("ticket", ticket, filters.ChatType.PRIVATE)
    )
    # Everything else a reader sends — text, media, stickers, voice — joins
    # their open ticket, or opens one. No conversation state to fall out of.
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & ~filters.COMMAND
            & ~filters.StatusUpdate.ALL,
            process_user_message,
        )
    )
    # Support side of the bot
    # handle the response to tickets — any message type, not just text
    application.add_handler(
        MessageHandler(
            filters.REPLY
            & ~filters.COMMAND
            & ~filters.StatusUpdate.ALL
            & filters.Chat(chat_id=AUTHORIZED_GROUP_ID),
            ticket_response,
        )
    )
    application.add_handler(
        CommandHandler(
            "ban", ban_user, filters.Chat(chat_id=AUTHORIZED_GROUP_ID)
        )
    )
    application.add_handler(
        CommandHandler(
            "unban", unban_user, filters.Chat(chat_id=AUTHORIZED_GROUP_ID)
        )
    )
    application.add_handler(
        CommandHandler(
            "pseudonym",
            set_staff_pseudonym,
            filters.Chat(chat_id=AUTHORIZED_GROUP_ID),
        )
    )
    application.add_handler(
        CommandHandler(
            "open", open_tickets, filters.Chat(chat_id=AUTHORIZED_GROUP_ID)
        )
    )
    # open tickets list's buttons
    application.add_handler(
        CallbackQueryHandler(open_tickets, pattern="^OPEN_TICKETS_")
    )
    # ticket's buttons
    application.add_handler(
        CallbackQueryHandler(ticket_actions, pattern=validate_ticket_query)
    )

    application.add_error_handler(error_handler)

    application.run_polling()
