import html
import logging
import traceback

import services
from config import AUTHORIZED_GROUP_ID
from consts import (
    TICKETS_PER_PAGE,
    PaginationActions,
    TicketActions,
    TicketStatus,
)
from i18n import gt as _
from models import Employee, SupportTicket, User
from peewee import DoesNotExist
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    Update,
)
from telegram.error import BadRequest
from telegram.ext import Application, ApplicationHandlerStop, ContextTypes
from templates import (
    outside_hours_notice,
    start_message,
    ticket_response_message,
)
from utils import (
    create_ticket_summary,
    is_within_working_hours,
    parse_command_target,
    ticket_tag,
)

__logger = logging.getLogger(__name__)

# Shown in the open-tickets list when a ticket was opened with media only.
MEDIA_ONLY_SUMMARY = "📎"


def __ticket_buttons(ticket: SupportTicket) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _("SPAM 🗑️"),
                    callback_data=f"{ticket.id}_{TicketActions.SPAM}",
                ),
                InlineKeyboardButton(
                    _("CLOSE ✅"),
                    callback_data=f"{ticket.id}_{TicketActions.CLOSE}",
                ),
            ]
        ]
    )


def __group_header(ticket: SupportTicket, user: User) -> str:
    """Tagged one-liner that every relayed reader message sits under"""
    name = html.escape(user.first_name or str(user.id))
    return (
        f"{ticket_tag(ticket)} | "
        f"<a href='tg://user?id={user.id}'>{name}</a>"
    )


async def error_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    __logger.error(
        "Exception while handling an update:", exc_info=context.error
    )

    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )

    bot_data_dump = html.escape(str(context.bot_data))
    chat_data_dump = html.escape(str(context.chat_data))
    user_data_dump = html.escape(str(context.user_data))
    tb_dump = html.escape("".join(tb_list))

    message = _(
        "⚠️ Unexpected Error has occurred:\n\n"
        "<pre>context.bot_data = {}</pre>\n"
        "<pre>context.chat_data = {}</pre>\n"
        "<pre>context.user_data = {}</pre>\n\n"
        "<pre>{}</pre>\n"
    ).format(bot_data_dump, chat_data_dump, user_data_dump, tb_dump)

    await context.bot.send_message(
        AUTHORIZED_GROUP_ID,
        message,
        parse_mode="HTML",
    )


async def post_init(application: Application) -> None:
    """Called after the initialization and before polling for updates"""
    await services.bot.check_prerequisites(application)

    services.db.init_db()

    await services.bot.add_commands(application)


async def leave_chat(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Leaves from the chat
    """
    __logger.info("Chat is not authorized: '%s'", update.effective_chat.id)
    context.application.create_task(
        update.effective_chat.leave(), update=update
    )
    raise ApplicationHandlerStop


async def ticket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Explains how to reach support.

    Tickets are not created by a command any more — the reader's next message
    opens one — so this only tells them what to do, and says so plainly when a
    ticket is already running.
    """
    message = update.effective_message
    db_user = User.get(User.id == update.effective_user.id)

    open_ticket = services.ticket.get_open_ticket(db_user)
    if open_ticket:
        await message.reply_text(
            _(
                "You already have an open ticket {tag} — just send your"
                " message here and it will land in it."
            ).format(tag=ticket_tag(open_ticket)),
            parse_mode="HTML",
        )
        return

    await message.reply_text(
        _("Send your question and we'll do our best to assist you! 😉")
    )


async def process_user_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """
    Relays anything the reader sends into their open ticket.

    The first message opens a ticket; every message after it joins the same
    one until support closes it. Media, stickers and voice notes are copied
    across as-is.
    """
    bot = context.bot
    message = update.effective_message
    db_user = User.get(User.id == update.effective_user.id)

    open_ticket = services.ticket.get_open_ticket(db_user)
    is_new = open_ticket is None

    if is_new:
        summary = message.text or message.caption or MEDIA_ONLY_SUMMARY
        open_ticket = services.ticket.open_ticket(db_user, summary)

    # If the reader is answering something support sent, point the relayed
    # message at that staff message so the thread reads correctly in the group.
    reply_to_support_id = None
    if message.reply_to_message:
        answered = services.ticket.by_private_message(
            message.reply_to_message.message_id
        )
        if answered and answered.ticket.id == open_ticket.id:
            reply_to_support_id = answered.support_message_id

    group_message = await services.relay.to_support_group(
        bot,
        open_ticket,
        __group_header(open_ticket, db_user),
        message,
        reply_to_message_id=reply_to_support_id,
        # Only the opening message carries the action buttons — repeating them
        # on every message would give the group a wall of them.
        reply_markup=__ticket_buttons(open_ticket) if is_new else None,
    )

    services.ticket.record_message(
        open_ticket,
        support_message_id=group_message.message_id,
        private_message_id=message.message_id,
        from_staff=False,
    )

    if is_new:
        open_ticket.support_message_id = group_message.message_id
        open_ticket.private_message_id = message.message_id
        open_ticket.save()

        confirmation = _(
            "✅ Ticket {tag} has been created. Everything you send from now on"
            " goes into it until support closes it."
        ).format(tag=ticket_tag(open_ticket))

        if not is_within_working_hours():
            confirmation = f"{confirmation}\n\n{outside_hours_notice}"

        await message.reply_text(confirmation, parse_mode="HTML")


async def ticket_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Forwards a staff reply to the reader, keeping the ticket open"""
    message = update.effective_message
    user = update.effective_user
    reply_message = message.reply_to_message
    bot = context.bot

    # only replies to the bot's own relayed messages are answers to a ticket
    if reply_message.from_user.id != bot.id:
        return

    relayed = services.ticket.by_support_message(reply_message.message_id)
    if relayed is None:
        __logger.debug(
            "Reply message with id '%s' is not associated with a support ticket",
            reply_message.message_id,
        )
        return

    support_ticket = relayed.ticket

    if support_ticket.status == TicketStatus.CLOSED:
        await message.reply_text(
            _("⚠️ This ticket is closed — the reader will not see the reply.")
        )
        return

    try:
        pseudonym = Employee.get(Employee.user_id == user.id).pseudonym
    except DoesNotExist:
        __logger.debug("Fallback pseudonym to default value")
        pseudonym = _("Support Staff")

    header = ticket_response_message.format(
        staff_pseudonym=html.escape(pseudonym or _("Support Staff"))
    )

    delivered = await services.relay.copy_with_header(
        bot,
        support_ticket.user.id,
        header,
        message,
        reply_to_message_id=relayed.private_message_id,
    )

    services.ticket.record_message(
        support_ticket,
        support_message_id=message.message_id,
        private_message_id=delivered.message_id,
        from_staff=True,
    )


async def ticket_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    query_user = query.from_user
    message = update.effective_message
    bot = context.bot

    if update.effective_chat.id != AUTHORIZED_GROUP_ID:
        __logger.info("Callback query tampering attempt by %s", query_user)
        return

    raw_ticket_id, action = query.data.split("_", 1)

    try:
        support_ticket = SupportTicket.get_by_id(raw_ticket_id)
    except DoesNotExist:
        return

    tag = ticket_tag(support_ticket)
    edit_header = (
        f"{message.text_html or message.caption_html or tag}\n\n"
        f"<a href='tg://user?id={query_user.id}'>"
        f"{html.escape(query_user.first_name or '')}</a> "
    )

    if action == TicketActions.SPAM:
        reason = _("Spam")
        reader = support_ticket.user

        services.user.ban(reader, reason)

        edit_body = _(
            "🛑 <b>has issued a ban</b>, <i>reason: {reason}</i>"
        ).format(reason=reason)
        # notify the reader about the action
        await bot.send_message(
            reader.id,
            _("<b>System</b> {body}").format(body=edit_body),
            parse_mode="HTML",
        )
        # wipe the banned reader's open tickets out of the group
        deleted_count = 0
        for spam_ticket in SupportTicket.select().where(
            (SupportTicket.user == reader)
            & (SupportTicket.status == TicketStatus.OPEN)
        ):
            for relayed in spam_ticket.messages:
                try:
                    await bot.delete_message(
                        chat_id=AUTHORIZED_GROUP_ID,
                        message_id=relayed.support_message_id,
                    )
                except BadRequest as e:
                    __logger.debug("Could not delete relayed message: %s", e)
                relayed.delete_instance()
            spam_ticket.delete_instance()
            deleted_count += 1

        # notify the staff about the action
        await bot.send_message(
            chat_id=AUTHORIZED_GROUP_ID,
            text=_(
                "{header}{body}\n\n<i>Deleted {count} open tickets</i>"
            ).format(header=edit_header, body=edit_body, count=deleted_count),
            parse_mode="HTML",
            reply_markup=None,
        )
    elif action == TicketActions.CLOSE:
        db_user = User.get(User.id == query_user.id)
        services.ticket.close_ticket(support_ticket, db_user)

        await message.edit_reply_markup(reply_markup=None)
        await bot.send_message(
            chat_id=AUTHORIZED_GROUP_ID,
            text=_("{header}✅ <b>marked this ticket as resolved</b>").format(
                header=edit_header
            ),
            parse_mode="HTML",
        )
        # the reader has to know the thread is over: their next message opens
        # a brand new ticket rather than continuing this one
        await bot.send_message(
            support_ticket.user.id,
            _(
                "ℹ️ Your ticket {tag} has been closed. Write again if you need"
                " anything else — that will open a new one."
            ).format(tag=tag),
            parse_mode="HTML",
        )
    else:
        return

    await query.answer()


async def preprocess_update(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Called before every update"""
    user = update.effective_user

    if user is None or user.is_bot:
        return

    try:
        db_user = User.get(User.id == user.id)
    except DoesNotExist:
        User.create(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            language_code=user.language_code,
        )
        return


    chat = update.effective_chat
    if chat is not None and chat.id == AUTHORIZED_GROUP_ID:
        return

    if services.user.is_banned(db_user):
        raise ApplicationHandlerStop


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows welcome message"""
    await update.message.reply_text(start_message, parse_mode="HTML")


async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Blocks the user in the system"""
    message = update.effective_message

    async def usage(message: Message):
        await message.reply_text(
            _(
                "ℹ️ Usage: {} <ticket_id OR username OR user_id> <reason>"
            ).format(command)
        )

    command, *args = message.text.split(" ", 1)
    if not args:
        return context.application.create_task(usage(message))

    target, *reason = args[0].split(" ", 1)
    if not reason:
        return context.application.create_task(usage(message))

    user = await parse_command_target(update, target)

    if not user:
        return

    if services.user.is_banned(user):
        await message.reply_text(_("⚠️ User is already banned"))
    else:
        services.user.ban(user, reason=reason[0])
        await message.reply_text(_("✅ User has been banned"))


async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unblocks the user in the system"""
    message = update.effective_message

    async def usage(message: Message):
        await message.reply_text(
            _("ℹ️ Usage: {} <ticket_id OR username OR user_id>").format(
                command
            )
        )

    command, *target = message.text.split(" ", 1)
    if not target:
        return context.application.create_task(usage(message))

    user = await parse_command_target(update, target[0])

    if not user:
        return

    if services.user.unban(user):
        await message.reply_text(_("✅ User has been unbanned"))
    else:
        await message.reply_text(_("⚠️ User is not banned"))


async def set_staff_pseudonym(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    """Set pseudonym of the staff member"""
    message = update.effective_message
    user = update.effective_user

    async def usage(message: Message):
        await message.reply_text(_("ℹ️ Usage: {} <pseudonym>").format(command))

    command, *pseudonym = message.text.split(" ", 1)
    if not pseudonym:
        return context.application.create_task(usage(message))

    user_db = User.get_by_id(user.id)
    employee, __ = Employee.get_or_create(user=user_db)

    services.employee.set_pseudonym(employee, pseudonym[0])

    await message.reply_text(
        _("✅ Pseudonym has been set to '{}'").format(pseudonym[0])
    )


async def open_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists open tickets for the staff member"""
    query_prefix = "OPEN_TICKETS_"

    message = update.effective_message
    query = update.callback_query

    page = context.user_data.get("open_tickets_page", 0)

    if query:
        if update.effective_chat.id != AUTHORIZED_GROUP_ID:
            __logger.info(
                "Callback query tampering attempt by %s", update.effective_user
            )
            return

        command = query.data.replace(query_prefix, "")
        if command == PaginationActions.PREVIOUS:
            page -= 1
        elif command == PaginationActions.REFRESH:
            pass
        elif command == PaginationActions.NEXT:
            page += 1
        else:
            return
        await query.answer()

    tickets_count = (
        SupportTicket.select()
        .where(SupportTicket.status == TicketStatus.OPEN)
        .count()
    )

    pages_count, remainder = divmod(tickets_count, TICKETS_PER_PAGE)
    if remainder:
        pages_count += 1

    # bounds check
    if page >= pages_count:
        page = 0
    elif page < 0:
        page = pages_count - 1

    limit = TICKETS_PER_PAGE
    offset = TICKETS_PER_PAGE * page

    tickets = (
        SupportTicket.select()
        .where(SupportTicket.status == TicketStatus.OPEN)
        .order_by(SupportTicket.created_at)
        .offset(offset)
        .limit(limit)
    )
    if not tickets:
        summary = _("🥳 Hooray, all tickets are resolved!")
    else:
        summary = create_ticket_summary(tickets)

    keyboard = [
        [
            InlineKeyboardButton(
                "⏮️", callback_data=(query_prefix + PaginationActions.PREVIOUS)
            ),
            InlineKeyboardButton(
                "🔄", callback_data=(query_prefix + PaginationActions.REFRESH)
            ),
            InlineKeyboardButton(
                "⏭️", callback_data=(query_prefix + PaginationActions.NEXT)
            ),
        ]
    ]
    markup = InlineKeyboardMarkup(keyboard)

    pages_str = (
        _("<b>(page {}/{})</b>").format(page + 1, pages_count)
        if pages_count
        else ""
    )

    msg_text = _("📂 Open tickets {}\n{}").format(pages_str, summary)

    if query:
        try:
            await message.edit_text(
                msg_text, parse_mode="HTML", reply_markup=markup
            )
        except BadRequest as e:
            if "Message is not modified: " in str(
                e
            ):  # no error type for that, yuck
                pass
            else:
                raise

    else:
        await message.reply_text(
            msg_text,
            parse_mode="HTML",
            reply_markup=markup,
        )

    context.user_data["open_tickets_page"] = page
