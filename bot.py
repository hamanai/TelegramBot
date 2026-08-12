import os
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ---------- Configuration ----------

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set")

OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID")
if not OWNER_CHAT_ID:
    raise RuntimeError("OWNER_CHAT_ID environment variable is not set")
OWNER_CHAT_ID = int(OWNER_CHAT_ID)

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# In-memory conversation history per user (resets if the bot restarts)
conversations = {}

SYSTEM_PROMPT = """تو یک مشاور املاک هستی که برای یک آژانس مشاوره‌ی املاک بین‌المللی کار می‌کنی.
شرکت در این مناطق فعالیت می‌کند:
- یونان: شهر آتن
- قبرس شمالی: تمام شهرها
- ایران: مشهد، تهران و شهرهای شمالی
- ترکیه: استانبول و ازمیر

وظیفه‌ی تو:
1. فقط و فقط درباره‌ی خرید ملک، مزایای سرمایه‌گذاری، و شرایط زندگی در همین مناطق بالا صحبت کن. اگر کاربر سوالی خارج از این موضوع پرسید (مثلا سوال عمومی، فنی، شخصی و غیره)، مودبانه بگو که فقط در زمینه‌ی مشاوره‌ی املاک این مناطق می‌تونی کمک کنی.
2. با کاربر مثل یک مشاور حرفه‌ای و دوستانه صحبت کن، به فارسی پاسخ بده مگر اینکه کاربر به زبان دیگری بنویسه.
3. درباره‌ی مزایای هر منطقه (قیمت، اقامت، سرمایه‌گذاری، کیفیت زندگی) اطلاعات کلی و مفید بده.
4. در طول مکالمه، به آرامی و به‌طور طبیعی این اطلاعات رو از کاربر بپرس (نه همه با هم، یکی‌یکی و طبیعی):
   - کدام کشور/شهر مورد نظرشونه
   - بودجه‌ی تقریبی‌شون
   - یک راه تماس (شماره تلفن، واتساپ یا آیدی تلگرام)
5. وقتی هر سه مورد بالا (منطقه، بودجه، تماس) رو از کاربر گرفتی، در همون پاسخ یک بلوک مخفی به این شکل دقیق اضافه کن (کاربر این بلوک رو نمی‌بینه، فقط سیستم می‌بینه):

[[LEAD]]{"country": "...", "budget": "...", "contact": "...", "summary": "..."}[[/LEAD]]

فیلد summary باید یک خلاصه‌ی کوتاه فارسی از خواسته‌ی مشتری باشه.
این بلوک رو فقط یک بار و فقط وقتی هر سه اطلاعات کامل شد بفرست، نه زودتر.
"""


def build_gemini_history(chat_id):
    if chat_id not in conversations:
        conversations[chat_id] = model.start_chat(history=[
            {"role": "user", "parts": [SYSTEM_PROMPT]},
            {"role": "model", "parts": ["باشه، متوجه شدم. من به عنوان مشاور املاک این مناطق در خدمت مشتریان هستم."]},
        ])
    return conversations[chat_id]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "سلام! 👋 من دستیار مشاوره‌ی املاک هستم.\n\n"
        "می‌تونم درباره‌ی خرید ملک و مزایای سرمایه‌گذاری در این مناطق راهنماییتون کنم:\n"
        "🇬🇷 یونان (آتن)\n"
        "🇹🇷 ترکیه (استانبول، ازمیر)\n"
        "🇮🇷 ایران (تهران، مشهد، شهرهای شمالی)\n"
        "🇨🇾 قبرس شمالی (تمام شهرها)\n\n"
        "بفرمایید کدوم منطقه مد نظرتونه؟"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_text = update.message.text

    try:
        chat = build_gemini_history(chat_id)
        response = chat.send_message(user_text)
        reply_text = response.text

        # Check if a lead block was included
        lead_match = re.search(r"\[\[LEAD\]\](.*?)\[\[/LEAD\]\]", reply_text, re.DOTALL)
        if lead_match:
            try:
                lead_data = json.loads(lead_match.group(1))
                lead_message = (
                    "🏠 لید جدید از بات!\n\n"
                    f"👤 چت آیدی مشتری: {chat_id}\n"
                    f"🌍 کشور/منطقه: {lead_data.get('country', '-')}\n"
                    f"💰 بودجه: {lead_data.get('budget', '-')}\n"
                    f"📞 تماس: {lead_data.get('contact', '-')}\n"
                    f"📝 خلاصه: {lead_data.get('summary', '-')}"
                )
                await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=lead_message)
            except json.JSONDecodeError:
                pass  # if Gemini format is off, just skip silently

            # Remove the hidden block before showing reply to the user
            reply_text = re.sub(r"\[\[LEAD\]\].*?\[\[/LEAD\]\]", "", reply_text, flags=re.DOTALL).strip()

        await update.message.reply_text(reply_text)

    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("متاسفم، الان مشکلی پیش اومد. لطفاً دوباره امتحان کنید.")


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # silence default request logging


def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()


def main():
    # Start a tiny HTTP server in the background so Render detects an open port.
    threading.Thread(target=run_health_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
