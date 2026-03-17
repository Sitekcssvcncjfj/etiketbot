import os
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

from database import init_db, add_member, get_members, get_member_count

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

TOKEN = os.getenv("BOT_TOKEN")


def mention_html(user_id: int, name: str) -> str:
    safe_name = (
        name.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )
    return f"<a href='tg://user?id={user_id}'>{safe_name}</a>"


async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return False

    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ["administrator", "creator"]


async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_group_admin(update, context):
        await update.message.reply_text("Bu komutu sadece grup adminleri kullanabilir.")
        return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Merhaba! Ben grup etiket botuyum.\n\n"
        "Komutlar:\n"
        "/admins - Adminleri etiketle\n"
        "/all - Kayıtlı üyeleri etiketle\n"
        "/count - Kayıtlı üye sayısı"
    )


async def track_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or not update.effective_user:
        return

    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    user = update.effective_user

    add_member(
        chat_id=update.effective_chat.id,
        user_id=user.id,
        first_name=user.first_name or "Kullanıcı",
        username=user.username or "",
        is_bot=user.is_bot
    )


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
    members = get_members(chat_id)

    if not members:
        await update.message.reply_text(
            "Henüz kayıtlı üye yok.\n"
            "Botun kullanıcıları tanıması için üyelerin grupta mesaj yazmış olması gerekir."
        )
        return

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


def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN ortam değişkeni eksik!")

    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admins", admins_command))
    app.add_handler(CommandHandler("all", all_command))
    app.add_handler(CommandHandler("count", count_command))

    app.add_handler(
        MessageHandler(
            filters.ALL & ~filters.StatusUpdate.ALL,
            track_users
        )
    )

    print("Bot çalışıyor...")
    app.run_polling()


if __name__ == "__main__":
    main()
