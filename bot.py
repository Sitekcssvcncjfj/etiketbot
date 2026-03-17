import os
import time
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

from database import init_db, add_member, remove_member, get_members, get_member_count

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN")
all_cooldowns = {}


def mention_html(user_id: int, name: str) -> str:
    safe_name = (
        (name or "Kullanıcı")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
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


def check_cooldown(chat_id: int, seconds: int = 20) -> int:
    now = time.time()
    last_used = all_cooldowns.get(chat_id, 0)
    diff = now - last_used

    if diff < seconds:
        return int(seconds - diff)

    all_cooldowns[chat_id] = now
    return 0


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "Merhaba! Gelişmiş etiket botu aktif.\n\n"
            "Komutlar:\n"
            "/admins - Adminleri etiketle\n"
            "/all - Kayıtlı üyeleri etiketle\n"
            "/all 10 - Sadece 10 kişiyi etiketle\n"
            "/count - Veritabanındaki kayıtlı üye sayısı\n"
            "/membercount - Gruptaki toplam üye sayısı"
        )


async def track_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    add_member(
        chat_id=chat.id,
        user_id=user.id,
        first_name=user.first_name or "Kullanıcı",
        username=user.username or "",
        is_bot=user.is_bot
    )


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = update.effective_chat

    if not message or not chat:
        return

    if not message.new_chat_members:
        return

    for user in message.new_chat_members:
        add_member(
            chat_id=chat.id,
            user_id=user.id,
            first_name=user.first_name or "Kullanıcı",
            username=user.username or "",
            is_bot=user.is_bot
        )


async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = update.effective_chat

    if not message or not chat:
        return

    if not message.left_chat_member:
        return

    user = message.left_chat_member
    remove_member(chat.id, user.id)


async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat = update.effective_chat
    admins = await context.bot.get_chat_administrators(chat.id)

    mentions = []
    for admin in admins:
        user = admin.user
        if user.is_bot:
            continue
        mentions.append(mention_html(user.id, user.first_name or "Admin"))

    if not mentions:
        await update.message.reply_text("Etiketlenecek admin bulunamadı.")
        return

    batch_size = 5
    for i in range(0, len(mentions), batch_size):
        batch = mentions[i:i + batch_size]
        await update.message.reply_text(
            "Adminler:\n" + " ".join(batch),
            parse_mode="HTML"
        )


async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    remaining = check_cooldown(chat_id, 20)
    if remaining > 0:
        await update.message.reply_text(
            f"Bu komut çok sık kullanılıyor. {remaining} saniye sonra tekrar dene."
        )
        return

    members = get_members(chat_id)

    if not members:
        await update.message.reply_text(
            "Henüz kayıtlı üye yok.\n"
            "Bot yeni girenleri ve mesaj atanları kaydeder."
        )
        return

    limit = None
    if context.args:
        try:
            limit = int(context.args[0])
            if limit <= 0:
                limit = None
        except ValueError:
            pass

    if limit:
        members = members[:limit]

    mentions = [
        mention_html(member["user_id"], member["first_name"])
        for member in members
    ]

    batch_size = 5
    for i in range(0, len(mentions), batch_size):
        batch = mentions[i:i + batch_size]
        await update.message.reply_text(
            "Etiket:\n" + " ".join(batch),
            parse_mode="HTML"
        )


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

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, track_users))

    print("Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
