import os
import time
import html
import random
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError

from config import (
    BOT_TOKEN,
    SUPPORT_GROUP_URL,
    ADD_BOT_URL,
    LOG_CHAT_ID,
    ALLOWED_ADMIN_IDS,
    COOLDOWN_SECONDS,
    BATCH_SIZE,
)
from database import (
    init_db,
    add_or_update_member,
    remove_member,
    clear_admin_flags,
    get_members,
    get_admin_members,
    get_member_count,
    search_members,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)
ALL_COOLDOWNS = {}


def mention_html(user_id: int, name: str) -> str:
    return f"<a href='tg://user?id={user_id}'>{html.escape(name or 'Kullanıcı')}</a>"


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📢 Destek Grubu", url=SUPPORT_GROUP_URL),
            InlineKeyboardButton("➕ Beni Gruba Ekle", url=ADD_BOT_URL)
        ],
        [
            InlineKeyboardButton("👮 Adminler", callback_data="menu_admins"),
            InlineKeyboardButton("🏷 Herkesi Etiketle", callback_data="menu_all")
        ],
        [
            InlineKeyboardButton("📊 Kayıtlı Sayı", callback_data="menu_count"),
            InlineKeyboardButton("ℹ️ Yardım", callback_data="menu_help")
        ]
    ])


async def log_action(context: ContextTypes.DEFAULT_TYPE, text: str):
    if LOG_CHAT_ID != 0:
        try:
            await context.bot.send_message(LOG_CHAT_ID, text)
        except Exception as e:
            logger.warning(f"Log gönderilemedi: {e}")


async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return False

    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ["administrator", "creator"]


async def is_allowed_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False

    admin_status = await is_group_admin(update, context)
    if not admin_status:
        return False

    if not ALLOWED_ADMIN_IDS:
        return True

    return user.id in ALLOWED_ADMIN_IDS


async def admin_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not await is_allowed_admin(update, context):
        if update.effective_message:
            await update.effective_message.reply_text(
                "Bu komutu sadece yetkili adminler kullanabilir."
            )
        return False
    return True


def check_cooldown(chat_id: int) -> int:
    now = time.time()
    last_used = ALL_COOLDOWNS.get(chat_id, 0)
    diff = now - last_used

    if diff < COOLDOWN_SECONDS:
        return int(COOLDOWN_SECONDS - diff)

    ALL_COOLDOWNS[chat_id] = now
    return 0


def parse_limit(args):
    if not args:
        return None
    try:
        value = int(args[0])
        if value > 0:
            return value
    except:
        pass
    return None


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


async def send_mentions(update: Update, mentions: list[str], title: str, reply_to_message_id=None):
    if not update.effective_message:
        return

    if not mentions:
        await update.effective_message.reply_text("Etiketlenecek kullanıcı bulunamadı.")
        return

    for i in range(0, len(mentions), BATCH_SIZE):
        batch = mentions[i:i + BATCH_SIZE]
        await update.effective_message.reply_text(
            f"{title}\n" + " ".join(batch),
            parse_mode="HTML",
            reply_to_message_id=reply_to_message_id
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "✨ <b>Gelişmiş Etiket Botu</b>\n\n"
        "Komutlar:\n"
        "/admins - Adminleri etiketle\n"
        "/all - Kayıtlı üyeleri etiketle\n"
        "/alladmins - Sadece adminleri etiketle\n"
        "/silentall - Komutu cevaplanan mesaja bağlı etiket at\n"
        "/randomtag 10 - Rastgele 10 kişi etiketle\n"
        "/search isim - İsim/kullanıcı adı ara\n"
        "/count - Kayıtlı üye sayısı\n"
        "/membercount - Toplam grup sayısı\n"
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard()
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_help":
        await query.message.reply_text(
            "Komutlar:\n"
            "/admins\n/all\n/alladmins\n/silentall\n/randomtag 10\n/search isim\n/count\n/membercount"
        )
    elif query.data == "menu_count":
        if query.message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            count = get_member_count(query.message.chat.id)
            await query.message.reply_text(f"Kayıtlı üye sayısı: {count}")
        else:
            await query.message.reply_text("Bu butonu grup içinde kullan.")
    elif query.data == "menu_admins":
        await query.message.reply_text("Grup içinde /admins komutunu kullan.")
    elif query.data == "menu_all":
        await query.message.reply_text("Grup içinde /all komutunu kullan.")


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

    remove_member(chat.id, message.left_chat_member.id)


async def admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    await sync_admins(chat_id, context)
    admins = get_admin_members(chat_id)

    mentions = [mention_html(x["user_id"], x["first_name"]) for x in admins]
    await send_mentions(update, mentions, "👮 Adminler:")
    await log_action(context, f"/admins kullanıldı | chat={chat_id} | user={update.effective_user.id}")


async def alladmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    await sync_admins(chat_id, context)
    admins = get_admin_members(chat_id)
    mentions = [mention_html(x["user_id"], x["first_name"]) for x in admins]

    await send_mentions(update, mentions, "👮 Sadece Adminler:")
    await log_action(context, f"/alladmins kullanıldı | chat={chat_id} | user={update.effective_user.id}")


async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    remain = check_cooldown(chat_id)
    if remain > 0:
        await update.effective_message.reply_text(f"Bekle: {remain} saniye")
        return

    members = get_members(chat_id)
    if not members:
        await update.effective_message.reply_text("Kayıtlı üye bulunamadı.")
        return

    limit = parse_limit(context.args)
    if limit:
        members = members[:limit]

    mentions = [mention_html(x["user_id"], x["first_name"]) for x in members]
    await send_mentions(update, mentions, "🏷 Etiket:")
    await log_action(context, f"/all kullanıldı | chat={chat_id} | user={update.effective_user.id}")


async def silentall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    remain = check_cooldown(chat_id)
    if remain > 0:
        await update.effective_message.reply_text(f"Bekle: {remain} saniye")
        return

    members = get_members(chat_id)
    if not members:
        await update.effective_message.reply_text("Kayıtlı üye bulunamadı.")
        return

    reply_to = None
    if update.effective_message.reply_to_message:
        reply_to = update.effective_message.reply_to_message.message_id

    mentions = [mention_html(x["user_id"], x["first_name"]) for x in members]
    await send_mentions(update, mentions, "🔕 Sessiz Etiket:", reply_to_message_id=reply_to)
    await log_action(context, f"/silentall kullanıldı | chat={chat_id} | user={update.effective_user.id}")


async def randomtag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    members = get_members(chat_id)

    if not members:
        await update.effective_message.reply_text("Kayıtlı üye yok.")
        return

    limit = parse_limit(context.args) or 5
    sampled = random.sample(members, min(limit, len(members)))

    mentions = [mention_html(x["user_id"], x["first_name"]) for x in sampled]
    await send_mentions(update, mentions, f"🎲 Rastgele {len(sampled)} kişi:")
    await log_action(context, f"/randomtag kullanıldı | chat={chat_id} | user={update.effective_user.id}")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    if not context.args:
        await update.effective_message.reply_text("Kullanım: /search isim")
        return

    keyword = " ".join(context.args).strip().lower()
    chat_id = update.effective_chat.id
    results = search_members(chat_id, keyword)

    if not results:
        await update.effective_message.reply_text("Eşleşen kullanıcı bulunamadı.")
        return

    mentions = []
    for x in results[:20]:
        label = x["first_name"]
        if x["username"]:
            label += f" (@{x['username']})"
        mentions.append(mention_html(x["user_id"], label))

    await send_mentions(update, mentions, f"🔎 Arama sonucu: {html.escape(keyword)}")
    await log_action(context, f"/search kullanıldı | chat={chat_id} | user={update.effective_user.id} | q={keyword}")


async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    count = get_member_count(update.effective_chat.id)
    await update.effective_message.reply_text(f"📊 Kayıtlı üye sayısı: {count}")


async def membercount_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    total = await context.bot.get_chat_member_count(update.effective_chat.id)
    saved = get_member_count(update.effective_chat.id)

    await update.effective_message.reply_text(
        f"👥 Toplam grup üyesi: {total}\n"
        f"💾 Botun kayıtlı bildiği: {saved}"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Hata:", exc_info=context.error)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("Bir hata oluştu.")
    except TelegramError:
        pass


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN eksik!")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admins", admins_command))
    app.add_handler(CommandHandler("alladmins", alladmins_command))
    app.add_handler(CommandHandler("all", all_command))
    app.add_handler(CommandHandler("silentall", silentall_command))
    app.add_handler(CommandHandler("randomtag", randomtag_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("count", count_command))
    app.add_handler(CommandHandler("membercount", membercount_command))

    app.add_handler(CallbackQueryHandler(menu_callback))

    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, track_users))

    app.add_error_handler(error_handler)

    logger.info("Ultra bot çalışıyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
