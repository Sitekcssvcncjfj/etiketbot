import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

SUPPORT_GROUP_URL = os.getenv("SUPPORT_GROUP_URL", "https://t.me/yourgroup")
ADD_BOT_URL = os.getenv("ADD_BOT_URL", "https://t.me/your_bot_username?startgroup=true")

# Log kanalı / grup chat id
# örnek: -1001234567890
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))

# Sadece belirli adminler komut kullansın istiyorsan:
# Virgülle ayır: 12345,67890
ALLOWED_ADMIN_IDS = [
    int(x.strip()) for x in os.getenv("ALLOWED_ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", "20"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
