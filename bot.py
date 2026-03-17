import time
import html
import random
import logging

from telegram import Update
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
    BOT_NAME,
    LOG_CHAT_ID,
    ALLOWED_ADMIN_IDS,
    COOLDOWN_SECONDS,
    BATCH_SIZE,
    RANDOM_TAG_DEFAULT,
    ENABLE_LOG,
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
    get_settings,
    save_settings,
)
from keyboards import (
    home_keyboard,
    panel_home_keyboard,
    tags_keyboard,
    settings_keyboard,
    stats_keyboard,
    support_keyboard,
    help_keyboard,
    close_keyboard,
    back_keyboard,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ALL_COOLDOWNS = {}
PENDING_ACTIONS = {}


def mention_html(user_id, name):
    return f"<a href='tg://user?id={user_id}'>{html.escape(name or 'Kullanıcı')}</a>"


async def log_action(context, chat_id, user_id, action_text):
    try:
        if LOG_CHAT_ID != 0 and ENABLE_LOG:
            await context.bot.send_message(
                LOG_CHAT_ID,
                f"📝 İşlem: {action_text}\n🏠 Chat: <code>{chat_id}</code>\n👤 User: <code>{user_id}</code>",
                parse_mode="HTML"
            )
    except Exception:
        pass


async def is_group_admin(update, context):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return False

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return False

    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ["administrator", "creator"]


async def is_allowed_admin(update, context):
    user = update.effective_user
    if not user:
        return False

    admin_status = await is_group_admin(update, context)
    if not admin_status:
        return False

    if not ALLOWED_ADMIN_IDS:
        return True

    return user.id in ALLOWED_ADMIN_IDS


async def admin_only(update, context):
    if not await is_allowed_admin(update, context):
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ Bu işlem sadece yetkili grup adminleri tarafından kullanılabilir."
            )
        return False
    return True


def check_cooldown(chat_id, settings):
    now = time.time()
    cooldown = settings.get("cooldown", COOLDOWN_SECONDS)
    last_used = ALL_COOLDOWNS.get(chat_id, 0)
    diff = now - last_used

    if diff < cooldown:
        return int(cooldown - diff)

    ALL_COOLDOWNS[chat_id] = now
    return 0


async def sync_admins(chat_id, context):
    clear_admin_flags(chat_id)
    admins = await context.bot.get_chat_administrators(chat_id)

    for admin in admins:
        user = admin.user
        add_or_update_member(
            chat_id,
            user.id,
            user.first_name or "Admin",
            user.username or "",
            user.is_bot,
            1
        )


async def send_mentions(update, mentions, title, batch_size=5, reply_to=None):
    if not mentions:
        await update.effective_message.reply_text("Liste boş.")
        return

    for i in range(0, len(mentions), batch_size):
        batch = mentions[i:i + batch_size]
        await update.effective_message.reply_text(
            f"{title}\n" + " ".join(batch),
            parse_mode="HTML",
            reply_to_message_id=reply_to
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        f"✨ <b>{BOT_NAME}</b>\n\n"
        "Merhaba, ben şık arayüzlü grup yönetim botuyum.\n\n"
        "📌 <b>Özellikler</b>\n"
        "• Admin araçları\n"
        "• Kullanıcı kayıt takibi\n"
        "• Arama ve istatistik\n"
        "• Butonlu yönetim paneli\n\n"
        "Aşağıdaki menüden devam edebilirsin."
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=home_keyboard()
    )


async def panel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    text = (
        "🏠 <b>Yönetim Paneli</b>\n\n"
        "Aşağıdaki kategorilerden birini seçerek devam et."
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=panel_home_keyboard()
    )


async def panel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    chat = query.message.chat
    chat_id = chat.id
    settings = get_settings(chat_id)

    if data == "noop":
        return

    if data == "close_panel":
        await query.message.edit_text(
            "❌ <b>Panel kapatıldı.</b>\nTekrar açmak için aşağıdaki butonu kullan.",
            parse_mode="HTML",
            reply_markup=close_keyboard()
        )
        return

    if data == "panel_home":
        await query.message.edit_text(
            "🏠 <b>Yönetim Paneli</b>\n\n"
            "İşlem kategorilerinden birini seç.",
            parse_mode="HTML",
            reply_markup=panel_home_keyboard()
        )
        return

    if data == "panel_tags":
        await query.message.edit_text(
            "🏷 <b>Etiket ve Liste Araçları</b>\n\n"
            "Aşağıdaki araçlardan birini seç.",
            parse_mode="HTML",
            reply_markup=tags_keyboard()
        )
        return

    if data == "panel_settings":
        text = (
            "⚙️ <b>Bot Ayarları</b>\n\n"
            "Butonlara basarak grup ayarlarını güncelleyebilirsin."
        )
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=settings_keyboard(settings)
        )
        return

    if data == "panel_stats":
        await sync_admins(chat_id, context)
        total = await context.bot.get_chat_member_count(chat_id)
        saved = get_member_count(chat_id)
        admins = get_admin_members(chat_id)

        text = (
            "📊 <b>Grup İstatistikleri</b>\n\n"
            f"👥 Toplam Üye: <b>{total}</b>\n"
            f"💾 Kayıtlı Kullanıcı: <b>{saved}</b>\n"
            f"👮 Admin Sayısı: <b>{len(admins)}</b>"
        )

        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=stats_keyboard()
        )
        return

    if data == "panel_support":
        text = (
            "🛟 <b>Destek Merkezi</b>\n\n"
            "Destek, iletişim ve bot ekleme işlemleri için aşağıdaki butonları kullan."
        )
        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=support_keyboard()
        )
        return

    if data == "panel_help":
        text = (
            "📖 <b>Komut Rehberi</b>\n\n"
            "<b>Yönetim Komutları</b>\n"
            "/panel - Yönetim panelini açar\n"
            "/settings - Mevcut ayarları gösterir\n"
            "/count - Kayıtlı kullanıcı sayısı\n"
            "/membercount - Toplam grup üye sayısı\n\n"
            "<b>Listeleme Komutları</b>\n"
            "/admins - Admin listesini gösterir\n"
            "/all - Kayıtlı kullanıcıları gösterir\n"
            "/alladmins - Kayıtlı adminleri gösterir\n"
            "/silentall - Sessiz listeleme\n"
            "/randomtag sayı - Rastgele kullanıcı seçer\n"
            "/search isim - Kullanıcı arar"
        )

        await query.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=help_keyboard()
        )
        return

    if data == "set_cooldown":
        current = settings["cooldown"]
        current = 10 if current >= 60 else current + 5
        settings["cooldown"] = current
        save_settings(chat_id, **settings)
        await query.message.edit_reply_markup(reply_markup=settings_keyboard(settings))
        return

    if data == "set_batch":
        current = settings["batch_size"]
        current = 3 if current >= 10 else current + 1
        settings["batch_size"] = current
        save_settings(chat_id, **settings)
        await query.message.edit_reply_markup(reply_markup=settings_keyboard(settings))
        return

    if data == "set_random":
        current = settings["random_tag_default"]
        current = 5 if current >= 30 else current + 5
        settings["random_tag_default"] = current
        save_settings(chat_id, **settings)
        await query.message.edit_reply_markup(reply_markup=settings_keyboard(settings))
        return

    if data == "set_log":
        settings["enable_log"] = not settings["enable_log"]
        save_settings(chat_id, **settings)
        await query.message.edit_reply_markup(reply_markup=settings_keyboard(settings))
        return

    if data == "tag_admins":
        await sync_admins(chat_id, context)
        admins = get_admin_members(chat_id)
        mentions = [mention_html(x["user_id"], x["first_name"]) for x in admins]
        await send_mentions(update, mentions, "👮 <b>Admin Listesi</b>", settings["batch_size"])
        return

    if data == "tag_all":
        PENDING_ACTIONS[chat_id] = {"action": "all"}
        await query.message.reply_text(
            "👥 Kaç kayıtlı kullanıcı gösterilsin?\n"
            "Bir sayı gönder. Örnek: <code>10</code>\n"
            "Hepsi için: <code>0</code>",
            parse_mode="HTML",
            reply_markup=back_keyboard()
        )
        return

    if data == "tag_summary":
        total = await context.bot.get_chat_member_count(chat_id)
        saved = get_member_count(chat_id)
        await sync_admins(chat_id, context)
        admins = get_admin_members(chat_id)

        text = (
            "🧾 <b>Yönetim Özeti</b>\n\n"
            f"👥 Toplam Üye: <b>{total}</b>\n"
            f"💾 Kayıtlı Kullanıcı: <b>{saved}</b>\n"
            f"👮 Kayıtlı Admin: <b>{len(admins)}</b>\n"
            f"⏱ Cooldown: <b>{settings['cooldown']}</b> sn\n"
            f"📦 Batch: <b>{settings['batch_size']}</b>"
        )
        await query.message.reply_text(text, parse_mode="HTML")
        return

    if data == "tag_search":
        PENDING_ACTIONS[chat_id] = {"action": "search"}
        await query.message.reply_text(
            "🔎 Aramak istediğin ismi veya kullanıcı adını yaz.",
            reply_markup=back_keyboard()
        )
        return

    if data == "tag_random":
        members = get_members(chat_id)
        if not members:
            await query.message.reply_text("Kayıtlı kullanıcı yok.")
            return

        limit = settings["random_tag_default"]
        sampled = random.sample(members, min(limit, len(members)))
        mentions = [mention_html(x["user_id"], x["first_name"]) for x in sampled]

        await send_mentions(
            update,
            mentions,
            f"🎲 <b>Rastgele Seçilen {len(sampled)} Kullanıcı</b>",
            settings["batch_size"]
        )
        return


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if chat_id not in PENDING_ACTIONS:
        return

    action_data = PENDING_ACTIONS[chat_id]
    action = action_data.get("action")
    text = update.effective_message.text.strip()
    settings = get_settings(chat_id)

    if action == "all":
        members = get_members(chat_id)

        try:
            limit = int(text)
            if limit > 0:
                members = members[:limit]
        except ValueError:
            pass

        mentions = [mention_html(x["user_id"], x["first_name"]) for x in members]
        await send_mentions(
            update,
            mentions,
            f"👥 <b>Kayıtlı Kullanıcılar ({len(members)})</b>",
            settings["batch_size"]
        )
        del PENDING_ACTIONS[chat_id]
        return

    if action == "search":
        results = search_members(chat_id, text)

        if not results:
            await update.effective_message.reply_text("Sonuç bulunamadı.")
            del PENDING_ACTIONS[chat_id]
            return

        mentions = []
        for user in results[:20]:
            label = user["first_name"]
            if user["username"]:
                label += f" @{user['username']}"
            mentions.append(mention_html(user["user_id"], label))

        await send_mentions(
            update,
            mentions,
            f"🔎 <b>Arama Sonuçları</b>\nSorgu: <code>{html.escape(text)}</code>",
            settings["batch_size"]
        )
        del PENDING_ACTIONS[chat_id]
        return


async def track_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if not chat or not user:
        return

    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    add_or_update_member(
        chat.id,
        user.id,
        user.first_name or "Kullanıcı",
        user.username or "",
        user.is_bot,
        0
    )


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    chat = update.effective_chat

    if not message or not chat or not message.new_chat_members:
        return

    for user in message.new_chat_members:
        add_or_update_member(
            chat.id,
            user.id,
            user.first_name or "Kullanıcı",
            user.username or "",
            user.is_bot,
            0
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
    settings = get_settings(chat_id)

    admins = get_admin_members(chat_id)
    mentions = [mention_html(x["user_id"], x["first_name"]) for x in admins]

    await send_mentions(update, mentions, "👮 <b>Admin Listesi</b>", settings["batch_size"])
    await log_action(context, chat_id, update.effective_user.id, "/admins")


async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    settings = get_settings(chat_id)

    remain = check_cooldown(chat_id, settings)
    if remain > 0:
        await update.effective_message.reply_text(f"⏱ Bekle: {remain} saniye")
        return

    members = get_members(chat_id)
    if not members:
        await update.effective_message.reply_text("Kayıtlı kullanıcı yok.")
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

    mentions = [mention_html(x["user_id"], x["first_name"]) for x in members]
    await send_mentions(
        update,
        mentions,
        f"👥 <b>Kayıtlı Kullanıcılar ({len(members)})</b>",
        settings["batch_size"]
    )
    await log_action(context, chat_id, update.effective_user.id, "/all")


async def alladmins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    await sync_admins(chat_id, context)
    settings = get_settings(chat_id)

    admins = get_admin_members(chat_id)
    mentions = [mention_html(x["user_id"], x["first_name"]) for x in admins]

    await send_mentions(
        update,
        mentions,
        f"👮 <b>Kayıtlı Adminler ({len(admins)})</b>",
        settings["batch_size"]
    )
    await log_action(context, chat_id, update.effective_user.id, "/alladmins")


async def silentall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    settings = get_settings(chat_id)

    remain = check_cooldown(chat_id, settings)
    if remain > 0:
        await update.effective_message.reply_text(f"⏱ Bekle: {remain} saniye")
        return

    members = get_members(chat_id)
    if not members:
        await update.effective_message.reply_text("Kayıtlı kullanıcı yok.")
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

    reply_to = None
    if update.effective_message.reply_to_message:
        reply_to = update.effective_message.reply_to_message.message_id

    mentions = [mention_html(x["user_id"], x["first_name"]) for x in members]
    await send_mentions(
        update,
        mentions,
        f"🔕 <b>Sessiz Liste ({len(members)})</b>",
        settings["batch_size"],
        reply_to
    )
    await log_action(context, chat_id, update.effective_user.id, "/silentall")


async def randomtag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    settings = get_settings(chat_id)

    members = get_members(chat_id)
    if not members:
        await update.effective_message.reply_text("Kayıtlı kullanıcı yok.")
        return

    limit = settings["random_tag_default"]
    if context.args:
        try:
            limit = int(context.args[0])
        except ValueError:
            pass

    sampled = random.sample(members, min(limit, len(members)))
    mentions = [mention_html(x["user_id"], x["first_name"]) for x in sampled]

    await send_mentions(
        update,
        mentions,
        f"🎲 <b>Rastgele Seçilen {len(sampled)} Kullanıcı</b>",
        settings["batch_size"]
    )
    await log_action(context, chat_id, update.effective_user.id, "/randomtag")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    if not context.args:
        await update.effective_message.reply_text("Kullanım: /search isim")
        return

    keyword = " ".join(context.args)
    chat_id = update.effective_chat.id
    settings = get_settings(chat_id)

    results = search_members(chat_id, keyword)
    if not results:
        await update.effective_message.reply_text("Sonuç bulunamadı.")
        return

    mentions = []
    for user in results[:20]:
        label = user["first_name"]
        if user["username"]:
            label += f" @{user['username']}"
        mentions.append(mention_html(user["user_id"], label))

    await send_mentions(
        update,
        mentions,
        f"🔎 <b>Arama Sonuçları</b>\nSorgu: <code>{html.escape(keyword)}</code>",
        settings["batch_size"]
    )
    await log_action(context, chat_id, update.effective_user.id, "/search")


async def count_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    count = get_member_count(update.effective_chat.id)
    await update.effective_message.reply_text(
        f"📊 Kayıtlı kullanıcı sayısı: <b>{count}</b>",
        parse_mode="HTML"
    )


async def membercount_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    chat_id = update.effective_chat.id
    total = await context.bot.get_chat_member_count(chat_id)
    saved = get_member_count(chat_id)

    await update.effective_message.reply_text(
        f"👥 Toplam grup üyesi: <b>{total}</b>\n"
        f"💾 Botun bildiği kayıtlı kullanıcı: <b>{saved}</b>",
        parse_mode="HTML"
    )


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await admin_only(update, context):
        return

    settings = get_settings(update.effective_chat.id)
    text = (
        "⚙️ <b>Mevcut Ayarlar</b>\n\n"
        f"⏱ Cooldown: <b>{settings['cooldown']}</b> sn\n"
        f"📦 Batch: <b>{settings['batch_size']}</b>\n"
        f"🎯 Rastgele Limit: <b>{settings['random_tag_default']}</b>\n"
        f"📝 Log: <b>{'Açık' if settings['enable_log'] else 'Kapalı'}</b>"
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=settings_keyboard(settings)
    )


async def error_handler(update, context):
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
    app.add_handler(CommandHandler("panel", panel_command))
    app.add_handler(CommandHandler("admins", admins_command))
    app.add_handler(CommandHandler("all", all_command))
    app.add_handler(CommandHandler("alladmins", alladmins_command))
    app.add_handler(CommandHandler("silentall", silentall_command))
    app.add_handler(CommandHandler("randomtag", randomtag_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("count", count_command))
    app.add_handler(CommandHandler("membercount", membercount_command))
    app.add_handler(CommandHandler("settings", settings_command))

    app.add_handler(CallbackQueryHandler(panel_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))
    app.add_handler(MessageHandler(filters.ALL & ~filters.StatusUpdate.ALL, track_users))

    app.add_error_handler(error_handler)

    logger.info("Şık full final premium bot çalışıyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
