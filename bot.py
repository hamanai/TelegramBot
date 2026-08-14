import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ---------- Configuration ----------

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
if not OWNER_CHAT_ID:
    raise RuntimeError("OWNER_CHAT_ID environment variable is not set")
OWNER_CHAT_ID = int(OWNER_CHAT_ID)

# Conversation states
CHOOSING_COUNTRY, CHOOSING_BUDGET, ASKING_CONTACT = range(3)

# ---------- Translated content ----------

UI_TEXT = {
    "fa": {
        "welcome": (
            "سلام! 👋 من دستیار مشاوره‌ی املاک هستم.\n\n"
            "می‌تونم درباره‌ی خرید ملک و مزایای سرمایه‌گذاری در این مناطق راهنماییتون کنم.\n"
            "لطفاً یکی از گزینه‌ها رو انتخاب کنید:"
        ),
        "ask_budget": "برای ادامه، لطفاً بودجه‌ی تقریبی خودتون رو انتخاب کنید:",
        "ask_contact": "ممنون. لطفاً یک راه ارتباطی (شماره تلفن، واتساپ یا آیدی تلگرام) بفرستید تا همکاران ما باهاتون تماس بگیرن:",
        "thank_you": (
            "ممنون از اعتماد شما! ✅\n"
            "اطلاعاتتون برای همکاران ما ارسال شد و به‌زودی باهاتون تماس می‌گیریم.\n\n"
            "اگه می‌خواید درباره‌ی منطقه‌ی دیگه‌ای هم بدونید، دستور /start رو بزنید."
        ),
        "cancelled": "مکالمه لغو شد. برای شروع دوباره /start رو بزنید.",
        "budget_labels": ["۲۰ تا ۵۰ هزار", "۵۰ تا ۷۵ هزار", "۷۵ تا ۱۰۰ هزار", "۱۰۰ تا ۲۰۰ هزار", "بالای ۴۰۰ هزار"],
    },
    "en": {
        "welcome": (
            "Hello! 👋 I'm your real estate consulting assistant.\n\n"
            "I can help you with property purchase and investment benefits in these regions.\n"
            "Please choose one:"
        ),
        "ask_budget": "To continue, please select your approximate budget:",
        "ask_contact": "Thank you. Please send a contact method (phone number, WhatsApp, or Telegram ID) so our team can reach you:",
        "thank_you": (
            "Thank you for your trust! ✅\n"
            "Your information has been sent to our team and we'll contact you soon.\n\n"
            "If you'd like info about another region, send /start."
        ),
        "cancelled": "Conversation cancelled. Send /start to begin again.",
        "budget_labels": ["$20K - $50K", "$50K - $75K", "$75K - $100K", "$100K - $200K", "$400K+"],
    },
    "tr": {
        "welcome": (
            "Merhaba! 👋 Ben emlak danışmanlık asistanınızım.\n\n"
            "Bu bölgelerde mülk alımı ve yatırım avantajları konusunda size yardımcı olabilirim.\n"
            "Lütfen birini seçin:"
        ),
        "ask_budget": "Devam etmek için lütfen yaklaşık bütçenizi seçin:",
        "ask_contact": "Teşekkürler. Ekibimizin sizinle iletişime geçebilmesi için lütfen bir iletişim yöntemi (telefon numarası, WhatsApp veya Telegram kimliği) gönderin:",
        "thank_you": (
            "Güveniniz için teşekkür ederiz! ✅\n"
            "Bilgileriniz ekibimize iletildi, yakında sizinle iletişime geçeceğiz.\n\n"
            "Başka bir bölge hakkında bilgi almak isterseniz /start yazabilirsiniz."
        ),
        "cancelled": "Görüşme iptal edildi. Yeniden başlamak için /start yazın.",
        "budget_labels": ["20-50 Bin $", "50-75 Bin $", "75-100 Bin $", "100-200 Bin $", "400 Bin $ Üzeri"],
    },
}

COUNTRY_NAMES = {
    "greece": {"fa": "یونان (آتن) 🇬🇷", "en": "Greece (Athens) 🇬🇷", "tr": "Yunanistan (Atina) 🇬🇷"},
    "turkey": {"fa": "ترکیه (استانبول، ازمیر) 🇹🇷", "en": "Turkey (Istanbul, Izmir) 🇹🇷", "tr": "Türkiye (İstanbul, İzmir) 🇹🇷"},
    "iran": {"fa": "ایران (تهران، مشهد، شهرهای شمالی) 🇮🇷", "en": "Iran (Tehran, Mashhad, Northern cities) 🇮🇷", "tr": "İran (Tahran, Meşhed, Kuzey şehirleri) 🇮🇷"},
    "cyprus": {"fa": "قبرس شمالی (تمام شهرها) 🇨🇾", "en": "North Cyprus (all cities) 🇨🇾", "tr": "Kuzey Kıbrıs (tüm şehirler) 🇨🇾"},
}

# Fixed Persian names used only in the lead notification sent to the owner,
# so the owner always sees a consistent format regardless of customer's language.
COUNTRY_NAMES_OWNER = {
    "greece": "یونان",
    "turkey": "ترکیه",
    "iran": "ایران",
    "cyprus": "قبرس شمالی",
}

COUNTRY_TEXT = {
    "greece": {
        "fa": (
            "🇬🇷 *یونان*\n\n"
            "برای خرید ملک در یونان به بودجه‌ای بین ۲۵۰ تا ۴۰۰ هزار یورو نیاز دارید.\n\n"
            "مزایای خرید ملک در یونان:\n"
            "۱. اخذ اقامت اروپا برای سه خانواده (خودتون و همسر و فرزندانتون، پدر و مادر خودتون و همسرتون)\n"
            "۲. نیاز به حضور ندارید و می‌تونید درآمد خوبی از اجاره داشته باشید"
        ),
        "en": (
            "🇬🇷 *Greece*\n\n"
            "To buy property in Greece you need a budget between €250,000 and €400,000.\n\n"
            "Benefits of buying property in Greece:\n"
            "1. European residency for three families (you, your spouse and children, and your parents and your spouse's parents)\n"
            "2. No need to reside there — you can earn good rental income"
        ),
        "tr": (
            "🇬🇷 *Yunanistan*\n\n"
            "Yunanistan'da mülk almak için 250.000 ile 400.000 Euro arasında bir bütçeye ihtiyacınız var.\n\n"
            "Yunanistan'da mülk almanın avantajları:\n"
            "1. Üç aile için Avrupa oturma izni (siz, eşiniz ve çocuklarınız, anne-babanız ve eşinizin anne-babası)\n"
            "2. Orada ikamet etme zorunluluğu yok — kira geliriyle iyi bir gelir elde edebilirsiniz"
        ),
    },
    "turkey": {
        "fa": (
            "🇹🇷 *ترکیه*\n\n"
            "به بودجه‌ای بین ۵۰ هزار تا ۴۰۰ هزار دلار نیاز دارید.\n\n"
            "- با خرید ۴۰۰ هزار دلاری: پاسپورت و شهروندی ترکیه\n"
            "- با خرید ۲۰۰ هزار دلاری: اقامت سالیانه‌ی قابل تمدید\n"
            "- با خرید از ۵۰ هزار دلار (فقط سرمایه‌گذاری): شش ماه در سال اقامت، یا درآمد ده برابری نسبت به آپارتمان با همون مبلغ در ایران"
        ),
        "en": (
            "🇹🇷 *Turkey*\n\n"
            "You need a budget between $50,000 and $400,000.\n\n"
            "- With a $400,000 purchase: Turkish passport and citizenship\n"
            "- With a $200,000 purchase: renewable annual residency\n"
            "- Starting from $50,000 (investment only): 6 months of residency per year, or up to 10x the rental income compared to a similarly priced apartment in Iran"
        ),
        "tr": (
            "🇹🇷 *Türkiye*\n\n"
            "50.000 ile 400.000 Dolar arasında bir bütçeye ihtiyacınız var.\n\n"
            "- 400.000 Dolarlık alımla: Türk pasaportu ve vatandaşlığı\n"
            "- 200.000 Dolarlık alımla: yenilenebilir yıllık oturma izni\n"
            "- 50.000 Dolardan itibaren (sadece yatırım amaçlı): yılda 6 ay Türkiye'de ikamet, ya da İran'daki aynı fiyattaki bir daireye kıyasla 10 kat daha fazla kira geliri"
        ),
    },
    "iran": {
        "fa": (
            "🇮🇷 *ایران*\n\n"
            "قیمت خرید از ۲۰ هزار دلار به بالا شروع میشه.\n\n"
            "توجه: با خرید ملک هیچ گزینه‌ی اقامتی برای خارجی‌ها وجود نداره."
        ),
        "en": (
            "🇮🇷 *Iran*\n\n"
            "Prices start from $20,000.\n\n"
            "Note: Property purchase does not provide any residency option for foreign nationals."
        ),
        "tr": (
            "🇮🇷 *İran*\n\n"
            "Fiyatlar 20.000 Dolardan başlıyor.\n\n"
            "Not: Mülk satın almak yabancılar için herhangi bir oturma izni seçeneği sağlamaz."
        ),
    },
    "cyprus": {
        "fa": (
            "🇨🇾 *قبرس شمالی*\n\n"
            "هزینه‌ی خرید از ۱۱۰ هزار دلار شروع میشه.\n\n"
            "- امکان خرید کاملاً اقساطی\n"
            "- با پیش‌پرداخت ۳۰ هزار دلاری، اقامت به‌راحتی قابل دریافته\n"
            "- دریافت اقامت بسیار راحته\n"
            "- توجه: زمان فروش واحد نسبت به ترکیه پروسه‌ی طولانی‌تری داره"
        ),
        "en": (
            "🇨🇾 *North Cyprus*\n\n"
            "Prices start from $110,000.\n\n"
            "- Fully installment-based purchase available\n"
            "- With a $30,000 down payment, residency is easy to obtain\n"
            "- Getting residency is very straightforward\n"
            "- Note: reselling a unit takes longer compared to Turkey"
        ),
        "tr": (
            "🇨🇾 *Kuzey Kıbrıs*\n\n"
            "Fiyatlar 110.000 Dolardan başlıyor.\n\n"
            "- Tamamen taksitli satın alma imkanı\n"
            "- 30.000 Dolar peşinatla oturma izni kolayca alınabilir\n"
            "- Oturma izni almak çok kolaydır\n"
            "- Not: birimin satışı Türkiye'ye kıyasla daha uzun sürer"
        ),
    },
}

# Budget option keys shared across languages; label shown to owner is always in this fixed format.
BUDGET_KEYS = ["20_50", "50_75", "75_100", "100_200", "400_plus"]
BUDGET_LABELS_FOR_OWNER = {
    "20_50": "$20K - $50K",
    "50_75": "$50K - $75K",
    "75_100": "$75K - $100K",
    "100_200": "$100K - $200K",
    "400_plus": "$400K+",
}


def language_keyboard():
    buttons = [
        [
            InlineKeyboardButton("فارسی 🇮🇷", callback_data="lang_fa"),
            InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"),
            InlineKeyboardButton("Türkçe 🇹🇷", callback_data="lang_tr"),
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def country_menu_keyboard(lang):
    buttons = [
        [InlineKeyboardButton(COUNTRY_NAMES[key][lang], callback_data=f"country_{key}")]
        for key in COUNTRY_NAMES
    ]
    return InlineKeyboardMarkup(buttons)


def budget_keyboard(lang):
    labels = UI_TEXT[lang]["budget_labels"]
    buttons = [
        [InlineKeyboardButton(label, callback_data=f"budget_{key}")]
        for key, label in zip(BUDGET_KEYS, labels)
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "لطفاً زبان خود را انتخاب کنید / Please choose your language / Lütfen dilinizi seçin:",
        reply_markup=language_keyboard(),
    )
    return CHOOSING_COUNTRY  # next step after language selection is choosing a country


async def language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = query.data.replace("lang_", "")
    context.user_data["lang"] = lang

    await query.message.reply_text(
        UI_TEXT[lang]["welcome"],
        reply_markup=country_menu_keyboard(lang),
    )
    return CHOOSING_COUNTRY


async def country_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = context.user_data.get("lang", "fa")
    country_key = query.data.replace("country_", "")
    if country_key not in COUNTRY_TEXT:
        return CHOOSING_COUNTRY

    context.user_data["country_key"] = country_key

    await query.message.reply_text(COUNTRY_TEXT[country_key][lang], parse_mode="Markdown")
    await query.message.reply_text(
        UI_TEXT[lang]["ask_budget"],
        reply_markup=budget_keyboard(lang),
    )
    return CHOOSING_BUDGET


async def budget_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    lang = context.user_data.get("lang", "fa")
    budget_key = query.data.replace("budget_", "")
    context.user_data["budget_key"] = budget_key

    await query.message.reply_text(UI_TEXT[lang]["ask_contact"])
    return ASKING_CONTACT


async def contact_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "fa")
    chat_id = update.effective_chat.id
    contact = update.message.text

    country_key = context.user_data.get("country_key")
    budget_key = context.user_data.get("budget_key")

    country_owner_name = COUNTRY_NAMES_OWNER.get(country_key, "-")
    budget_owner_label = BUDGET_LABELS_FOR_OWNER.get(budget_key, "-")

    lead_message = (
        "🏠 لید جدید از بات!\n\n"
        f"👤 چت آیدی مشتری: {chat_id}\n"
        f"🌐 زبان مشتری: {lang}\n"
        f"🌍 منطقه‌ی مورد نظر: {country_owner_name}\n"
        f"💰 بودجه: {budget_owner_label}\n"
        f"📞 تماس: {contact}"
    )
    await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=lead_message)

    await update.message.reply_text(UI_TEXT[lang]["thank_you"])
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "fa")
    await update.message.reply_text(UI_TEXT[lang]["cancelled"])
    return ConversationHandler.END


# ---------- Tiny HTTP server so Render detects an open port ----------

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def main():
    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_COUNTRY: [
                CallbackQueryHandler(language_selected, pattern="^lang_"),
                CallbackQueryHandler(country_selected, pattern="^country_"),
            ],
            CHOOSING_BUDGET: [
                CallbackQueryHandler(budget_selected, pattern="^budget_"),
            ],
            ASKING_CONTACT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, contact_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(conv_handler)

    app.run_polling()


if __name__ == "__main__":
    main()
