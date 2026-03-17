from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Destek Grubu", url="https://t.me/your_support_group")],
        [InlineKeyboardButton("➕ Gruba Ekle", url="https://t.me/your_bot?startgroup=true")],
        [InlineKeyboardButton("👮 Admin Paneli", callback_data="panel_main")],
        [InlineKeyboardButton("📖 Komutlar", callback_data="panel_help")],
    ])


def panel_main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷 Etiket İşlemleri", callback_data="panel_tag")],
        [InlineKeyboardButton("⚙️ Ayarlar", callback_data="panel_settings")],
        [InlineKeyboardButton("📊 İstatistik", callback_data="panel_stats")],
        [InlineKeyboardButton("🔙 Geri", callback_data="back_main")],
    ])


def panel_tag_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Tüm Üyeleri Etiketle", callback_data="cmd_all")],
        [InlineKeyboardButton("👮 Sadece Adminleri Etiketle", callback_data="cmd_alladmins")],
        [InlineKeyboardButton("🔕 Sessiz Etiket", callback_data="cmd_silentall")],
        [InlineKeyboardButton("🎲 Rastgele Etiket", callback_data="cmd_randomtag")],
        [InlineKeyboardButton("🔍 Kullanıcı Ara", callback_data="cmd_search")],
        [InlineKeyboardButton("🔙 Geri", callback_data="panel_main")],
    ])


def panel_settings_keyboard(chat_id, settings):
    enable_emoji = "✅" if settings["enable_log"] else "❌"

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏱ Cooldown", callback_data="setting_cooldown"),
            InlineKeyboardButton(f"{settings['cooldown']}sn", callback_data="setting_cooldown"),
        ],
        [
            InlineKeyboardButton("📦 Batch", callback_data="setting_batch"),
            InlineKeyboardButton(f"{settings['batch_size']}", callback_data="setting_batch"),
        ],
        [
            InlineKeyboardButton("🎯 Rastgele Limit", callback_data="setting_random"),
            InlineKeyboardButton(f"{settings['random_tag_default']}", callback_data="setting_random"),
        ],
        [
            InlineKeyboardButton(f"📝 Log {enable_emoji}", callback_data="setting_log_toggle"),
        ],
        [InlineKeyboardButton("🔙 Geri", callback_data="panel_main")],
    ])


def panel_stats_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Sayıları Yenile", callback_data="panel_stats")],
        [InlineKeyboardButton("👥 Kayıtlı Üyeler", callback_data="stats_members")],
        [InlineKeyboardButton("👮 Admin Sayısı", callback_data="stats_admins")],
        [InlineKeyboardButton("🔙 Geri", callback_data="panel_main")],
    ])


def help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Geri", callback_data="back_main")],
    ])


def back_to_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Panele Dön", callback_data="panel_main")],
    ])
