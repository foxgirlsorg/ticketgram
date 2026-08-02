from i18n import gt as _

# Header the staff answer is delivered under. It has to work as a prefix for
# any message type — a letter form with a signature below the body cannot wrap
# a sticker or a voice note, and the answer already arrives as a reply to the
# reader's own message.
ticket_response_message = _("<b>ℹ️ AudioRanobe support</b> · {staff_pseudonym}")

start_message = _(
    "Hi! This is the AudioRanobe support bot. Just describe it here,"
    " attach screenshots or a recording if that helps,"
    " and the team will answer right in this chat.\n\n"
    "You can write at any hour. If we are out of office at that moment,"
    " support will get to your ticket once they are back."
)

# Appended to the confirmation when the ticket is opened outside the working
# window, so nobody sits waiting for an answer that is hours away.
outside_hours_notice = _(
    "🌙 Right now it is outside our working hours — support will get back to"
    " you once they are in."
)
