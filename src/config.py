import logging
import os
from datetime import datetime
from pathlib import Path

from consts import WeekDay
from dotenv import load_dotenv

__logger = logging.getLogger(__name__)

#
# Paths
#
# Root of the bot's own directory (the one holding src/), resolved from this
# file rather than the working directory: the bot has to find its locales and
# its database whether it is started as `python src/bot.py`, from inside src/,
# or from /app in the container.
BOT_ROOT = Path(__file__).resolve().parent.parent
# Everything the bot writes lives here, next to the code — no named volumes.
DATA_DIR = BOT_ROOT / "data"

# .env is read from the bot's own directory, for the same reason.
load_dotenv(BOT_ROOT / ".env")

#
# Required environment variables
#
# Get one from the @BotFather bot
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# Group in which the bot operates
AUTHORIZED_GROUP_ID = os.environ.get("AUTHORIZED_GROUP_ID")

#
# Optional environment variables
#
# bot language
BOT_LANGUAGE = os.environ.get("BOT_LANGUAGE", "ru")
# database connection URI; relative paths are resolved against DATA_DIR so the
# database always ends up inside the bot's folder
DB_URI = os.environ.get("DB_URI", "tickets.db")
# working time — no longer shown to readers, but still used to decide whether
# to warn them that the answer will have to wait until the team is back
BOT_TIME_ACTIVE = os.environ.get("BOT_TIME_ACTIVE", "10:00-20:00")
# timezone of the working time (Moscow by default)
BOT_TIME_ZONE = int(os.environ.get("BOT_TIME_ZONE", "+3"))
# working days
BOT_ACTIVE_DAYS = os.environ.get(
    "BOT_ACTIVE_DAYS",
    "monday tuesday wednesday thursday friday saturday sunday",
)


#
# validation
#
__null_req_vars = []

if not TELEGRAM_TOKEN:
    __null_req_vars.append("TELEGRAM_TOKEN")
if not AUTHORIZED_GROUP_ID:
    __null_req_vars.append("AUTHORIZED_GROUP_ID")
else:
    AUTHORIZED_GROUP_ID = int(AUTHORIZED_GROUP_ID)

if __null_req_vars:
    __logger.error(
        "Required environment variables are not set: %s", __null_req_vars
    )
    exit(1)

DB_URI = Path(DB_URI)
if not DB_URI.is_absolute():
    DB_URI = DATA_DIR / DB_URI
DB_URI.parent.mkdir(parents=True, exist_ok=True)
DB_URI = str(DB_URI)

BOT_TIME_ACTIVE = [
    datetime.strptime(time, "%H:%M").time()
    for time in BOT_TIME_ACTIVE.split("-", 1)
]


BOT_ACTIVE_DAYS: WeekDay = [
    WeekDay._value2member_map_[day_str]
    for day_str in BOT_ACTIVE_DAYS.split(" ", 6)
]

if BOT_TIME_ZONE not in range(-12, 14 + 1):
    __logger.error("BOT_TIME_ZONE must be a valid timezone (-12, 14)")
    exit(1)
