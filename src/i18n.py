import gettext

from config import BOT_LANGUAGE, BOT_ROOT

# Resolved from the bot's own directory rather than the working directory —
# with a relative path the catalog silently failed to load and every message
# fell back to English.
__translation = gettext.translation(
    "base", BOT_ROOT / "src" / "locales", [BOT_LANGUAGE], fallback=True
)

gt = __translation.gettext
