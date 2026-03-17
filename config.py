import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

SUPPORT_GROUP_URL = "https://t.me/KGBotomasyon"
ADD_BOT_URL = os.getenv("ADD_BOT_URL", "https://t.me/your_bot?startgroup=true")

LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))

ALLOWED_ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ALLOWED_ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "20"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
RANDOM_TAG_DEFAULT = int(os.getenv("RANDOM_TAG_DEFAULT", "10"))
ENABLE_LOG = os.getenv("ENABLE_LOG", "true").lower() == "true"
