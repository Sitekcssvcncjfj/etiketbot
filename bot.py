import os
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
    BOT_TOKEN, SUPPORT_GROUP_URL, ADD_BOT_URL,
    LOG_CHAT_ID, ALLOWED_ADMIN_IDS, COOLDOWN_SECONDS,
    BATCH_SIZE, RANDOM_TAG_DEFAULT, ENABLE_LOG
)
from database import (
    init_db, add_or_update_member, remove_member, clear_admin_flags,
    get_members, get_admin_members, get_member_count, search_members,
    get_settings, save_settings
)
from keyboards import (
    main_menu_keyboard, panel_main_keyboard, panel_tag_keyboard,
    panel_settings_keyboard, panel_stats_keyboard, help_keyboard,
    back_to_panel_keyboard
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ALL_COOLDOWNS = {}
PENDING_SEARCH = {}


def mention_html(user_id, name):
    return f"<a href='tg://user?id={user_id}'>{html.escape(name or 'Kullanıcı')}</a>"


async def log_action(context, text):
    try:
        if LOG_CHAT_ID != 0 and ENABLE_LOG:
            await context.bot.send_message(LOG_CHAT_ID, f"📝 {text}")
    except:
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
            await update.effective_message.reply_text("❌ Bu komutu sadece yetkili adminler kullanabilir.")
        return False
    return True


def check_cooldown(chat_id, settings):
    now = time.time()
    cooldown = settings.get("cooldown", COOLDOWN_SECONDS)
    last = ALL_COOLDOWNS.get(chat_id, 0)
    diff = now - last
    if diff < cooldown:
        return int(cooldown - diff)
    ALL_COOLDOWNS[chat_id] = now
    return 0


async def sync_admins(chat_id, context):
    clear_admin_flags(chat_id)
    admins = await context.bot.get_chat_administrators(chat_id)
    for admin in admins:
        user = admin.user
        add_or_update_member(chat_id, user.id, user.first_name or "Admin",
                            user.username or "", user.is_bot, 1)


async def send_mentions(update, mentions, title, batch_size=5, reply_to=None):
    if not mentions:
        await update.effective_message.reply_text("Etiketlenecek kullanıcı bulunamadı.")
        return
    for i in range(0, len(mentions), batch_size):
        batch = mentions[i:i + batch_size]
        await update.effective_message.reply_text(
            f"{title}\n" + " ".join(batch),
            parse_mode="HTML",
            reply_to_message_id=reply_to
        )


async def start(update, context):
    text = (
        "✨ <b>Premium Etiket Botu</b>\n\n"
        "👋 Merhaba! Ben grup yönetimi için tasarlandım.\n\n"
        "📌 <b>Özelliklerim:</b>\n"
        "• Üye ve admin etiketleme\n"
        "• Rastgele etiketleme\n"
        "• Kullanıcı arama\n"
        "• Gelişmiş admin paneli\n\n"
        "👇 Aşağıdaki butonları kullan:"
    )
    await update.effective_message.reply_text(
        text, parse_mode="HTML", reply_markup=main_menu_keyboard()
    )


async def panel(update, context):
    if not await admin_only(update, context):
        return
    text = "⚙️ <b>Admin Paneli</b>\n\nBuradan bot ayarlarını yönetebilirsin."
    await update.effective_message.reply_text(
        text, parse_mode="HTML", reply_markup=panel_main_keyboard()
    )


async def panel_callback(update, context):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id
    settings = get_settings(chat_id)

    # === Geri butonları ===
    if data == "back_main":
        text = "✨ <b>Premium Etiket Botu</b>\n\n👇 Menüden seçim yap:"
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=main_menu_keyboard())
        return

    if data == "panel_main":
        text = "⚙️ <b>Admin Paneli</b>\n\nYapmak istediğin işlemi seç:"
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=panel_main_keyboard())
        return

    # === Tag paneli ===
    if data == "panel_tag":
        text = "🏷 <b>Etiket İşlemleri</b>\n\nBir işlem seç:"
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=panel_tag_keyboard())
        return

    # === Settings paneli ===
    if data == "panel_settings":
        text = "⚙️ <b>Ayarlar</b>\n\nMevcut ayarlarınız:"
        await query.message.edit_text(
            text, parse_mode="HTML", reply_markup=panel_settings_keyboard(chat_id, settings)
        )
        return

    # === Ayarları değiştir ===
    if data == "setting_cooldown":
        settings["cooldown"] = max(5, min(120, settings["cooldown"] - 5 if settings["cooldown"] > 10 else settings["cooldown"] + 5))
        save_settings(chat_id, **settings)
        await query.message.edit_reply_markup(reply_markup=panel_settings_keyboard(chat_id, settings))
        return

    if data == "setting_batch":
        settings["batch_size"] = max(1, min(20, settings["batch_size"] - 1 if settings["batch_size"] > 3 else settings["batch_size"] + 1))
        save_settings(chat_id, **settings)
        await query.message.edit_reply_markup(reply_markup=panel_settings_keyboard(chat_id, settings))
        return

    if data == "setting_random":
        settings["random_tag_default"] = max(5, min(50, settings["random_tag_default"] - 5 if settings["random_tag_default"] > 10 else settings["random_tag_default"] + 5))
        save_settings(chat_id, **settings)
        await query.message.edit_reply_markup(reply_markup=panel_settings_keyboard(chat_id, settings))
        return

    if data == "setting_log_toggle":
        settings["enable_log"] = not settings["enable_log"]
        save_settings(chat_id, **settings)
        await query.message.edit_reply_markup(reply_markup=panel_settings_keyboard(chat_id, settings))
        return

    # === İstatistik paneli ===
    if data == "panel_stats":
        await sync_admins(chat_id, context)
        total = await context.bot.get_chat_member_count(chat_id)
        saved = get_member_count(chat_id)
        admins = get_admin_members(chat_id)
        text = (
            f"📊 <b>İstatistikler</b>\n\n"
            f"👥 Toplam üye: {total}\n"
            f"💾 Kayıtlı: {saved}\n"
            f"👮 Admin sayısı: {len(admins)}"
        )
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=panel_stats_keyboard())
        return

    if data == "stats_members":
        count = get_member_count(chat_id)
        await query.message.reply_text(f"📋 Kayıtlı üye sayısı: <b>{count}</b>", parse_mode="HTML")
        return

    if data == "stats_admins":
        await sync_admins(chat_id, context)
        admins = get_admin_members(chat_id)
        await query.message.reply_text(f"👮 Admin sayısı: <b>{len(admins)}</b>", parse_mode="HTML")
        return

    # === Komutlar butonları ===
    if data == "cmd_all":
        await query.message.reply_text("📝 Lütfen etiketlemek istediğin kişi sayısını yaz.\nÖrnek: <code>20</code>\n veya <code>0</code> = hepsi", parse_mode="HTML", reply_markup=back_to_panel_keyboard())
        PENDING_SEARCH[chat_id] = {"action": "all"}
        return

    if data == "cmd_alladmins":
        await sync_admins(chat_id, context)
        admins = get_admin_members(chat_id)
        mentions = [mention_html(a["user_id"], a["first_name"]) for a in admins]
        batch = settings.get("batch_size", BATCH_SIZE)
        await send_mentions(update, mentions, "👮 <b>Adminler:</b>", batch)
        return

    if data == "cmd_silentall":
        await query.message.reply_text("🔕 <b>Sessiz etiket</b> için bir mesaja yanıtla ve sayı gir.\nÖrnek: <code>10</code>", parse_mode="HTML", reply_markup=back_to_panel_keyboard())
        PENDING_SEARCH[chat_id] = {"action": "silentall", "reply_to": query.message.reply_to_message.message_id if query.message.reply_to_message else None}
        return

    if data == "cmd_randomtag":
        members = get_members(chat_id)
        if not members:
            await query.message.reply_text("Kayıtlı üye yok.")
            return
        limit = settings.get("random_tag_default", RANDOM_TAG_DEFAULT)
        sampled = random.sample(members, min(limit, len(members)))
        mentions = [mention_html(m["user_id"], m["first_name"]) for m in sampled]
        batch = settings.get("batch_size", BATCH_SIZE)
        await send_mentions(update, mentions, f"🎲 <b>Rastgele {len(sampled)} kişi:</b>", batch)
        return

    if data == "cmd_search":
        await query.message.reply_text("🔍 Aramak istediğin ismi veya kullanıcı adını yaz:", reply_markup=back_to_panel_keyboard())
        PENDING_SEARCH[chat_id] = {"action": "search"}
        return

    if data == "panel_help":
        text = (
            "📖 <b>Komut Listesi</b>\n\n"
            "<b>Etiket Komutları:</b>\n"
            "/admins - Adminleri etiketle\n"
            "/all [sayı] - Üyeleri etiketle\n"
            "/alladmins - Sadece adminleri etiketle\n"
            "/silentall - Sessiz etiket\n"
            "/randomtag [sayı] - Rastgele etiket\n"
            "/search [isim] - Kullanıcı ara\n"
            "\n<b>Diğer:</b>\n"
            "/count - Kayıtlı üye sayısı\n"
            "/membercount - Toplam üye sayısı\n"
            "/panel - Admin paneli\n"
            "/settings - Ayarlar"
        )
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=help_keyboard())
        return


async def handle_text_input(update, context):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    if chat_id not in PENDING_SEARCH:
        return

    action_data = PENDING_SEARCH[chat_id]
    action = action_data.get("action")
    settings = get_settings(chat_id)
    batch = settings.get("batch_size", BATCH_SIZE)

    if action == "all":
        try:
            limit = int(text) if text != "0" else None
            if limit is not None and limit <= 0:
                limit = None
        except ValueError:
            limit = None

        members = get_members(chat_id)
        if not members:
            await update.message.reply_text("Kayıtlı üye yok.")
            del PENDING_SEARCH[chat_id]
            return

        if limit:
            members = members[:limit]

        mentions = [mention_html(m["user_id"], m["first_name"]) for m in members]
        await send_mentions(update, mentions, f"🏷 <b>Etiket ({len(members)} kişi):</b>", batch)
        await log_action(context, f"/all | {len(members)} kişi etiketlendi")

    elif action == "silentall":
        reply_to = action_data.get("reply_to")
        try:
            limit = int(text) if text != "0" else None
            if limit is not None and limit <= 0:
                limit = None
        except ValueError:
            limit = None

        members = get_members(chat_id)
        if not members:
            await update.message.reply_text("Kayıtlı üye yok.")
            del PENDING_SEARCH[chat_id]
            return

        if limit:
            members = members[:limit]

        mentions = [mention_html(m["user_id"], m["first_name"]) for m in members]
        await send_mentions(update, mentions, f"🔕 <b>Sessiz Etiket ({len(members)} kişi):</b>", batch, reply_to)
        await log_action(context, f"/silentall | {len(members)} kişi")

    elif action == "search":
        results = search_members(chat_id, text)
        if not results:
            await update.message.reply_text(f"'{html.escape(text)}' ile eşleşen kullanıcı bulunamadı.")
            del PENDING_SEARCH[chat_id]
            return

        mentions = [mention_html(r["user_id"], f"{r['first_name']} @{r['username']}" if r["username"] else r["first_name"]) for r in results[:20]]
        await send_mentions(update, mentions, f"🔎 <b>Arama: {html.escape(text)}</b> ({len(results)} sonuç)", batch)
        await log_action(context, f"/search | '{text}' | {len(results)} sonuç")

    del PENDING_SEARCH[chat_id]


async def track_users(update, context):
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return
    if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return
    add_or_update_member(chat.id, user.id, user.first_name or "Kullanıcı", user.username or "", user.is_bot, 0)


async def handle_new_members(update, context):
    message = update.message
    chat = update.effective_chat
    if not message or not chat or not message.new_chat_members:
        return
    for user in message.new_chat_members:
        add_or_update_member(chat.id, user.id, user.first_name or "Kullanıcı", user.username or "", user.is_bot, 0)


async def handle_left_member(update, context):
    message = update.message
    chat = update.effective_chat
    if not message or not chat or not message.left_chat_member:
        return
    remove_member(chat.id, message.left_chat_member.id)


async def admins_command(update, context):
    if not await admin_only(update, context):
        return
    chat_id = update.effective_chat.id
    await sync_admins(chat_id, context)
    settings = get_settings(chat_id)
    batch = settings.get("batch_size", BATCH_SIZE)
    admins = get_admin_members(chat_id)
    mentions = [mention_html(a["user_id"], a["first_name"]) for a in admins]
    await send_mentions(update, mentions, "👮 <b>Adminler:</b>", batch)
    await log_action(context, f"/admins | {len(admins)} admin etiketlendi")


async def alladmins_command(update, context):
    if not await admin_only(update, context):
        return
    chat_id = update.effective_chat.id
    await sync_admins(chat_id, context)
    settings = get_settings(chat_id)
    batch = settings.get("batch_size", BATCH_SIZE)
    admins = get_admin_members(chat_id)
    mentions = [mention_html(a["user_id"], a["first_name"]) for a in admins]
    await send_mentions(update, mentions, "👮 <b>Sadece Adminler:</b>", batch)


async def all_command(update, context):
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
        await update.effective_message.reply_text("Kayıtlı üye yok.")
        return

    limit = None
    if context.args:
        try:
            limit = int(context.args[0])
            if limit <= 0:
                limit = None
        except:
            pass

    if limit:
        members = members[:limit]

    batch = settings.get("batch_size", BATCH_SIZE)
    mentions = [mention_html(m["user_id"], m["first_name"]) for m in members]
    await send_mentions(update, mentions, f"🏷 <b>Etiket ({len(members)} kişi):</b>", batch)
    await log_action(context, f"/all | {len(members)} kişi etiketlendi")


async def silentall_command(update, context):
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
        await update.effective_message.reply_text("Kayıtlı üye yok.")
        return

    limit = None
    if context.args:
        try:
            limit = int(context.args[0])
            if limit <= 0:
                limit = None
        except:
            pass

    if limit:
        members = members[:limit]

    reply_to = None
    if update.effective_message.reply_to_message:
        reply_to = update.effective_message.reply_to_message.message_id

    batch = settings.get("batch_size", BATCH_SIZE)
    mentions = [mention_html(m["user_id"], m["first_name"]) for m in members]
    await send_mentions(update, mentions, f"🔕 <b>Sessiz Etiket ({len(members)} kişi):</b>", batch, reply_to)


async def randomtag_command(update, context):
    if not await admin_only(update, context):
        return
    chat_id = update.effective_chat.id
    settings = get_settings(chat_id)
    members = get_members(chat_id)

    if not members:
        await update.effective_message.reply_text("Kayıtlı üye yok.")
        return

    limit = settings.get("random_tag_default", RANDOM_TAG_DEFAULT)
    if context.args:
        try:
            limit = int(context.args[0])
        except:
            pass

    sampled = random.sample(members, min(limit, len(members)))
    batch = settings.get("batch_size", BATCH_SIZE)
    mentions = [mention_html(m["user_id"], m["first_name"]) for m in sampled]
    await send_mentions(update, mentions, f"🎲 <b>Rastgele {len(sampled)} kişi:</b>", batch)
    await log_action(context, f"/randomtag | {len(sampled)} kişi")


async def search_command(update, context):
    if not await admin_only(update, context):
        return
    if not context.args:
        await update.effective_message.reply_text("Kullanım: /search isim")
        return

    keyword = " ".join(context.args)
    chat_id = update.effective_chat.id
    settings = get_settings(chat_id)
    batch = settings.get("batch_size", BATCH_SIZE)
    results = search_members(chat_id, keyword)

    if not results:
        await update.effective_message.reply_text("Eşleşen kullanıcı bulunamadı.")
        return

    mentions = [mention_html(r["user_id"], f"{r['first_name']} @{r['username']}" if r["username"] else r["first_name"]) for r in results[:20]]
    await send_mentions(update, mentions, f"🔎 <b>Arama: {html.escape(keyword)}</b> ({len(results)} sonuç)", batch)
    await log_action(context, f"/search | '{keyword}' | {len(results)} sonuç")


async def count_command(update, context):
    if not await admin_only(update, context):
        return
    count = get_member_count(update.effective_chat.id)
    await update.effective_message.reply_text(f"📋 Kayıtlı üye sayısı: <b>{count}</b>", parse_mode="HTML")


async def membercount_command(update, context):
    if not await admin_only(update, context):
        return
    chat_id = update.effective_chat.id
    total = await context.bot.get_chat_member_count(chat_id)
    saved = get_member_count(chat_id)
    await update.effective_message.reply_text(
        f"👥 Toplam grup üyesi: <b>{total}</b>\n"
        f"💾 Botun kayıtlı bildiği: <b>{saved}</b>",
        parse_mode="HTML"
    )


async def settings_command(update, context):
    if not await admin_only(update, context):
        return
    chat_id = update.effective_chat.id
    settings = get_settings(chat_id)
    text = (
        f"⚙️ <b>Mevcut Ayarlar</b>\n\n"
        f"⏱ Cooldown: {settings['cooldown']}sn\n"
        f"📦 Batch: {settings['batch_size']}\n"
        f"🎯 Rastgele limit: {settings['random_tag_default']}\n"
        f"📝 Log: {'✅ Açık' if settings['enable_log'] else '❌ Kapalı'}"
    )
    await update.effective_message.reply_text(text, parse_mode="HTML")


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
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("admins", admins_command))
    app.add_handler(CommandHandler("alladmins", alladmins_command))
    app.add_handler(CommandHandler("all", all_command))
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

    logger.info("Premium bot çalışıyor...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
