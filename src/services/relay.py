"""
Moves messages between the reader's private chat and the support group.

Anything Telegram can carry is relayed as-is — photos, voice notes, stickers,
documents, video notes — by copying the original message rather than
re-sending its text. Copying keeps the media without downloading it, and it
strips the forward header, so the reader is only ever identified by the link
the bot puts in the tagged header.
"""

import logging
import re

from config import AUTHORIZED_GROUP_ID
from models import SupportTicket
from telegram import InlineKeyboardMarkup, Message
from telegram.error import BadRequest

__logger = logging.getLogger(__name__)

# Message types Telegram lets a copy carry a caption on. Everything else
# (stickers, video notes, polls, dice, locations…) gets the tagged header as a
# separate message with the media attached underneath it.
CAPTIONABLE = ("photo", "video", "animation", "audio", "document", "voice")


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def supports_caption(message: Message) -> bool:
    return any(getattr(message, attr, None) for attr in CAPTIONABLE)


async def copy_with_header(
    bot,
    chat_id: int,
    header: str,
    message: Message,
    reply_to_message_id: int | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
):
    """
    Relays ``message`` into ``chat_id`` underneath ``header``.

    Returns the object carrying the header — its ``message_id`` is the one
    worth remembering, since that is what a reply will point at.
    """
    # Plain text: no copy needed, header and body go out as one message.
    if message.text:
        return await bot.send_message(
            chat_id,
            collapse_blank_lines(f"{header}\n\n{message.text_html}"),
            parse_mode="HTML",
            reply_to_message_id=reply_to_message_id,
            allow_sending_without_reply=True,
            reply_markup=reply_markup,
        )

    if supports_caption(message):
        caption = message.caption_html or ""
        try:
            return await bot.copy_message(
                chat_id,
                message.chat_id,
                message.message_id,
                caption=collapse_blank_lines(f"{header}\n\n{caption}"),
                parse_mode="HTML",
                reply_to_message_id=reply_to_message_id,
                allow_sending_without_reply=True,
                reply_markup=reply_markup,
            )
        except BadRequest as e:
            # Safety net: the caption-capable list above is ours, Telegram's is
            # authoritative. Fall through to the two-message form.
            __logger.debug("Copy with caption rejected, splitting: %s", e)

    head = await bot.send_message(
        chat_id,
        header,
        parse_mode="HTML",
        reply_to_message_id=reply_to_message_id,
        allow_sending_without_reply=True,
        reply_markup=reply_markup,
    )
    await bot.copy_message(
        chat_id,
        message.chat_id,
        message.message_id,
        reply_to_message_id=head.message_id,
        allow_sending_without_reply=True,
    )
    return head


async def to_support_group(
    bot,
    ticket: SupportTicket,
    header: str,
    message: Message,
    reply_to_message_id: int | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
):
    """Relays a reader's message into the support group"""
    return await copy_with_header(
        bot,
        AUTHORIZED_GROUP_ID,
        header,
        message,
        reply_to_message_id=reply_to_message_id,
        reply_markup=reply_markup,
    )
