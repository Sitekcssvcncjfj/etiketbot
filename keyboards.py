from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import SUPPORT_GROUP_URL, ADD_BOT_URL, OWNER_URL


def home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Paneli Aç", callback_data="panel_home")],
        [
            InlineKeyboardButton("➕ Gruba Ekle", url=ADD_BOT_URL),
            InlineKeyboardButton("📢 Destek", url=SUPPORT_GROUP_URL)
        ],
        [InlineKeyboardButton("👤 Kurucu", url=OWNER_URL)]
    ])


def panel_home_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷 Etiket İşlemleri", callback_data="panel_tags")],
        [
            InlineKeyboardButton("📊 İstatistikler", callback_data="panel_stats"),
            InlineKeyboardButton("⚙️ Ayarlar", callback_data="panel_settings")
        ],
        [
            InlineKeyboardButton("📖 Komutlar", callback_data="panel_help"),
            InlineKeyboardButton("🛟 Destek", callback_data="panel_support")
        ],
        [InlineKeyboardButton("❌ Kapat", callback_data="close_panel")]
    ])


def tags_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👮 Adminleri Göster", callback_data="tag_admins")],
        [InlineKeyboardButton("👥 Kayıtlı Kullanıcıları Göster", callback_data="tag_all")],
        [
            InlineKeyboardButton("🧾 Yönetim Özeti", callback_data="tag_summary"),
            InlineKeyboardButton("🔎 Kullanıcı Ara", callback_data="tag_search")
        ],
        [InlineKeyboardButton("🎲 Rastgele Kullanıcı", callback_data="tag_random")],
        [InlineKeyboardButton("🔙 Geri", callback_data="panel_home")]
    ])


def settings_keyboard(settings):
    log_text = "✅ Açık" if settings["enable_log"] else "❌ Kapalı"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏱ Cooldown", callback_data="set_cooldown"),
            InlineKeyboardButton(f"{settings['cooldown']} sn", callback_data="noop")
        ],
        [
            InlineKeyboardButton("📦 Batch", callback_data="set_batch"),
            InlineKeyboardButton(f"{settings['batch_size']}", callback_data="noop")
        ],
        [
            InlineKeyboardButton("🎯 Rastgele", callback_data="set_random"),
            InlineKeyboardButton(f"{settings['random_tag_default']}", callback_data="noop")
        ],
        [
            InlineKeyboardButton("📝 Log", callback_data="set_log"),
            InlineKeyboardButton(log_text, callback_data="noop")
        ],
        [InlineKeyboardButton("🔙 Geri", callback_data="panel_home")]
    ])


def stats_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Yenile", callback_data="panel_stats")],
        [InlineKeyboardButton("🔙 Geri", callback_data="panel_home")]
    ])


def support_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Destek Grubu", url=SUPPORT_GROUP_URL)],
        [InlineKeyboardButton("➕ Beni Gruba Ekle", url=ADD_BOT_URL)],
        [InlineKeyboardButton("👤 Kurucu", url=OWNER_URL)],
        [InlineKeyboardButton("🔙 Geri", callback_data="panel_home")]
    ])


def help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Ana Panel", callback_data="panel_home")],
        [InlineKeyboardButton("❌ Kapat", callback_data="close_panel")]
    ])


def close_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Yeniden Aç", callback_data="panel_home")]
    ])


def back_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Panele Dön", callback_data="panel_home")]
    ])
