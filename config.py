import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

BOT_NAME = os.getenv("BOT_NAME", "Premium Etiket Botu")
SUPPORT_GROUP_URL = "https://t.me/KGBotomasyon"
ADD_BOT_URL = os.getenv("ADD_BOT_URL", "https://t.me/your_bot_username?startgroup=true")
OWNER_URL = os.getenv("OWNER_URL", "https://t.me/your_username")

LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))

ALLOWED_ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ALLOWED_ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "20"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
RANDOM_TAG_DEFAULT = int(os.getenv("RANDOM_TAG_DEFAULT", "10"))
ENABLE_LOG = os.getenv("ENABLE_LOG", "true").lower() == "true"
