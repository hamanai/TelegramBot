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
ASKING_BUDGET, ASKING_CONTACT = range(2)

COUNTRY_INFO = {
    "greece": {
        "name": "یونان (آتن) 🇬🇷",
        "text": (
            "🇬🇷 *یونان*\n\n"
            "برای خرید ملک در یونان به بودجه‌ای بین ۲۵۰ تا ۴۰۰ هزار یورو نیاز دارید.\n\n"
            "مزایای خرید ملک در یونان:\n"
            "۱. اخذ اقامت اروپا برای سه خانواده (خودتون و همسر و فرزندانتون، پدر و مادر خودتون و همسرتون)\n"
            "۲. نیاز به حضور ندارید و می‌تونید درآمد خوبی از اجاره داشته باشید"
        ),
    },
    "turkey": {
        "name": "ترکیه (استانبول، ازمیر) 🇹🇷",
        "text": (
            "🇹🇷 *ترکیه*\n\n"
            "به بودجه‌ای بین ۵۰ هزار تا ۴۰۰ هزار دلار نیاز دارید.\n\n"
            "- با خرید ۴۰۰ هزار دلاری: پاسپورت و شهروندی ترکیه\n"
            "- با خرید ۲۰۰ هزار دلاری: اقامت سالیانه‌ی قابل تمدید\n"
            "- با خرید از ۵۰ هزار دلار (فقط سرمایه‌گذاری): شش ماه در سال اقامت، یا درآمد ده برابری نسبت به آپارتمان با همون مبلغ در ایران"
        ),
    },
    "iran": {
        "name": "ایران (تهران، مشهد، شهرهای شمالی) 🇮🇷",
        "text": (
            "🇮🇷 *ایران*\n\n"
            "قیمت خرید از ۲۰ هزار دلار به بالا شروع میشه.\n\n"
            "توجه: با خرید ملک هیچ گزینه‌ی اقامتی برای خارجی‌ها وجود نداره."
        ),
    },
    "cyprus": {
        "name": "قبرس شمالی (تمام شهرها) 🇨🇾",
        "text": (
            "🇨🇾 *قبرس شمالی*\n\n"
            "هزینه‌ی خرید از ۱۱۰ هزار دلار شروع میشه.\n\n"
            "- امکان خرید کاملاً اقساطی\n"
            "- با پیش‌پرداخت ۳۰ هزار دلاری، اقامت به‌راحتی قابل دریافته\n"
            "- دریافت اقامت بسیار راحته\n"
            "- توجه: زمان فروش واحد نسبت به ترکیه پروسه‌ی طولانی‌تری داره"
        ),
    },
}


def country_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(info["name"], callback_data=key)]
        for key, info in COUNTRY_INFO.items()
    ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋 من دستیار مشاوره‌ی املاک هستم.\n\n"
        "می‌تونم درباره‌ی خرید ملک و مزایای سرمایه‌گذاری در این مناطق راهنماییتون کنم.\n"
        "لطفاً یکی از گزینه‌ها رو انتخاب کنید:",
        reply_markup=country_menu_keyboard(),
    )


async def country_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    country_key = query.data
    country = COUNTRY_INFO.get(country_key)
    if not country:
        return ConversationHandler.END

    context.user_data["country"] = country["name"]

    await query.message.reply_text(country["text"], parse_mode="Markdown")
    await query.message.reply_text(
        "برای ادامه، لطفاً بودجه‌ی تقریبی خودتون رو بنویسید (به دلار یا یورو):"
    )
    return ASKING_BUDGET


async def budget_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["budget"] = update.message.text
    await update.message.reply_text(
        "ممنون. لطفاً یک راه ارتباطی (شماره تلفن، واتساپ یا آیدی تلگرام) بفرستید تا همکاران ما باهاتون تماس بگیرن:"
    )
    return ASKING_CONTACT


async def contact_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text
    chat_id = update.effective_chat.id

    country = context.user_data.get("country", "-")
    budget = context.user_data.get("budget", "-")
    contact = context.user_data.get("contact", "-")

    lead_message = (
        "🏠 لید جدید از بات!\n\n"
        f"👤 چت آیدی مشتری: {chat_id}\n"
        f"🌍 منطقه‌ی مورد نظر: {country}\n"
        f"💰 بودجه: {budget}\n"
        f"📞 تماس: {contact}"
    )
    await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=lead_message)

    await update.message.reply_text(
        "ممنون از اعتماد شما! ✅\n"
        "اطلاعاتتون برای همکاران ما ارسال شد و به‌زودی باهاتون تماس می‌گیریم.\n\n"
        "اگه می‌خواید درباره‌ی منطقه‌ی دیگه‌ای هم بدونید، دستور /start رو بزنید."
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مکالمه لغو شد. برای شروع دوباره /start رو بزنید.")
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
            ASKING_BUDGET: [
                CallbackQueryHandler(country_selected),
                MessageHandler(filters.TEXT & ~filters.COMMAND, budget_received),
            ],
            ASKING_CONTACT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, contact_received),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(country_selected))

    app.run_polling()


if __name__ == "__main__":
    main()
