import os
import time
import html
import logging
from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError

from database import (
    init_db,
    add_or_update_member,
    remove_member,
    get_members,
    get_member_count,
    clear_admin_flags,
    get_admin_members,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
ALL_COOLDOWNS = {}
COOLDOWN_SECONDS = 20
BATCH_SIZE = 5


def mention_html(user_id: int, name: str) -> str:
    safe_name = html.escape(name or "Kullanıcı")
    return f"<a href='tg://user?id={user_id}'>{safe_name}</a>"


async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return False

    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ["administrator", "creator"]


async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_group_admin(update, context):
        if update.message:
            await update.message.reply_text("Bu komutu sadece grup adminleri kullanabilir.")
        return False
    return True


def check_cooldown(chat_id: int, seconds: int = COOLDOWN_SECONDS) -> int:
    now = time.time()
    last_used = ALL_COOLDOWNS.get(chat_id, 0)
    diff = now - last_used

    if diff < seconds:
        return int(seconds - diff)

    ALL_COOLDOWNS[chat_id] = now
    return 0


def parse_limit(args):
    if not args:
        return None

    try:
        limit = int(args[0])
        if limit > 0:
            return limit
    except (ValueError, TypeError):
        pass

    return None


async def send_mentions(update: Update, mentions: list[str], title: str):
    if not update.message:
        return

    if not mentions:
        await update.message.reply_text("Etiketlenecek kullanıcı bulunamadı.")
        return

    for i in range(0, len(mentions), BATCH_SIZE):
        batch = mentions[i:i + BATCH_SIZE]
        await update.message.reply_text(
            f"{title}\n" + " ".join(batch),
            parse_mode="HTML",
            disable_web_page_preview=True
        )


async def sync_admins(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    clear_admin_flags(chat_id)
    admins = await context.bot.get_chat_administrators(chat_id)

    for admin in admins:
        user = admin.user
        add_or_update_member(
            chat_id=chat_id,
            user_id=user.id,
            first_name=user.first_name or "Admin",
            username=user.username or "",
            is_bot=user.is_bot,
            is_admin=1
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "Merhaba! Gelişmiş etiket botu aktif.\n\n"
            "Komutlar:\n"
            "/admins - Adminleri etiketle\n"
            "/all - Kayıtlı üyeleri etiketle\n"
            "/all 20 - Sadece 20 kişiyi etiketle\n"
            "/count - Kayıtlı üye sayısı\n"
            "/membercount - Gruptaki toplam üye sayısı\n"
            "/syncadmins - Adminleri veritabanına kaydet"
        )


async def track_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    add_or_update_member(
        chat_id=chat.id,
        user_id=user.id,
        first_name=user.first_name or "Kullanıcı",
        username=user.username or "",
        is_bot=user.is_bot,
        is_admin=0
    )


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = update.effective_chat

    if not message or not chat or not message.new_chat_members:
        return

    for user in message.new_chat_members:
        add_or_update_member(
            chat_id=chat.id,
            user_id=user.id,
            first_name=user.first_name or "Kullanıcı",
            username=user.username or "",
            is_bot=user.is_bot,
            is_admin=0
        )


async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = update.effective_chat

    if not message or not chat or not message.left_chat_member:
        return

    user = message.left_chat_member
    remove_member(chat.id, user.id)


async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    await sync_admins(chat_id, context)

    admins = get_admin_members(chat_id)
    mentions = [mention_html(m["user_id"], m["first_name"]) for m in admins]

    await send_mentions(update, mentions, "Adminler:")


async def syncadmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    await sync_admins(chat_id, context)
    admin_count = len(get_admin_members(chat_id))

    await update.message.reply_text(
        f"Admin senkronizasyonu tamamlandı. Kayıtlı admin sayısı: {admin_count}"
    )


async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id

    remaining = check_cooldown(chat_id)
    if remaining > 0:
        await update.message.reply_text(
            f"Bu komut çok sık kullanılıyor. {remaining} saniye sonra tekrar dene."
        )
        return

    members = get_members(chat_id)

    if not members:
        await update.message.reply_text(
            "Henüz kayıtlı üye yok.\n"
            "Bot; mesaj atanları, yeni girenleri ve adminleri kaydeder."
        )
        return

    limit = parse_limit(context.args)
    if limit:
        members = members[:limit]

    mentions = [mention_html(member["user_id"], member["first_name"]) for member in members]
    await send_mentions(update, mentions, "Etiket:")


async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    count = get_member_count(chat_id)
    await update.message.reply_text(f"Kayıtlı üye sayısı: {count}")


async def membercount_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    total = await context.bot.get_chat_member_count(chat_id)
    saved = get_member_count(chat_id)

    await update.message.reply_text(
        f"Gruptaki toplam üye sayısı: {total}\n"
        f"Botun kayıtlı bildiği üye sayısı: {saved}"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Bir hata oluştu:", exc_info=context.error)

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Bir hata oluştu. Lütfen daha sonra tekrar dene."
            )
        except TelegramError:
            pass


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN ortam değişkeni eksik!")

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admins", admins_command))
    app.add_handler(CommandHandler("all", all_command))
    app.add_handler(CommandHandler("count", count_command))
    app.add_handler(CommandHandler("membercount", membercount_command))
    app.add_handler(CommandHandler("syncadmins", syncadmins_command))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, track_users))

    app.add_error_handler(error_handler)

    logger.info("Bot çalışıyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
