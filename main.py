import os
import io
import requests
import asyncio
from threading import Thread
from flask import Flask

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

import arabic_reshaper
from bidi.algorithm import get_display

# ==========================================
# ⚙️ الإعدادات
# ==========================================
TARGET_CHANNEL_ID = 1555520611411824711

BG_URL = "https://cdn.discordapp.com/attachments/1339684080224174141/1555517159046774854/IMG_9353.jpg?backend=b2&ex=6ac0cfbe&is=6abf7e3e&hm=83cbeeb7e5efa4d6a1f08261fc9dac3ee2b85dd13fec999470477ea666c12c7c&"

BOT_TOKEN = os.getenv("DISCORD_TOKEN", "ضع_توكن_البوت_هنا_إن_لم_تستخدم_متغيرات_البيئة")

BG_FILE = "background.jpg"
FONT_FILE = "Cairo-Bold.ttf"

# ==========================================
# 🌐 سيرفر Flask
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Evaluation Bot is Running!"

def run_flask():
    port = int(os.getenv("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()

# ==========================================
# 🛠️ تحميل الملحقات
# ==========================================
def download_assets():
    if not os.path.exists(BG_FILE):
        print("📥 جاري تحميل صورة الخلفية...", flush=True)
        try:
            res = requests.get(BG_URL, timeout=15)
            with open(BG_FILE, "wb") as f:
                f.write(res.content)
            print("✅ تم تحميل صورة الخلفية بنجاح.", flush=True)
        except Exception as e:
            print(f"❌ خطأ أثناء تحميل الخلفية: {e}", flush=True)

    if not os.path.exists(FONT_FILE):
        print("📥 جاري تحميل الخط العربي...", flush=True)
        try:
            font_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/cairo/static/Cairo-Bold.ttf"
            res = requests.get(font_url, timeout=15)
            with open(FONT_FILE, "wb") as f:
                f.write(res.content)
            print("✅ تم تحميل الخط العربي بنجاح.", flush=True)
        except Exception as e:
            print(f"❌ خطأ أثناء تحميل الخط: {e}", flush=True)

# ==========================================
# 🎨 دالة تصميم الصورة
# ==========================================
def create_evaluation_card(text: str, username: str, avatar_url: str) -> io.BytesIO:
    bg = Image.open(BG_FILE).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    try:
        av_res = requests.get(avatar_url, timeout=5)
        av_img = Image.open(io.BytesIO(av_res.content)).convert("RGBA")
    except Exception as e:
        print(f"⚠️ تعذر جلب الأفتار: {e}", flush=True)
        av_img = Image.new("RGBA", (100, 100), (120, 120, 120, 255))

    av_size = (38, 38)
    av_img = av_img.resize(av_size, Image.Resampling.LANCZOS)
    mask = Image.new("L", av_size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, av_size[0], av_size[1]), fill=255)

    av_x = 803 - 6 - av_size[0]
    av_y = 190 + (47 - av_size[1]) // 2
    bg.paste(av_img, (av_x, av_y), mask)

    user_font = ImageFont.truetype(FONT_FILE, 18)
    reshaped_user = get_display(arabic_reshaper.reshape(f"@{username}"))
    draw.text((av_x - 10, av_y + 19), reshaped_user, fill=(255, 255, 255, 255), font=user_font, anchor="rm")

    text_font = ImageFont.truetype(FONT_FILE, 20)
    reshaped_full_text = arabic_reshaper.reshape(text)

    words = reshaped_full_text.split(' ')
    lines = []
    current_line = []
    max_width = 620

    for word in words:
        test_line = ' '.join(current_line + [word])
        display_test = get_display(test_line)
        bbox = draw.textbbox((0, 0), display_test, font=text_font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line:
        lines.append(' '.join(current_line))

    display_lines = [get_display(line) for line in lines]

    line_height = 28
    total_height = len(display_lines) * line_height
    start_y = 350 - (total_height // 2) + 4

    for i, line in enumerate(display_lines):
        y_pos = start_y + (i * line_height)
        draw.text((500, y_pos), line, fill=(45, 38, 30, 255), font=text_font, anchor="mm")

    output = io.BytesIO()
    bg.save(output, format="PNG")
    output.seek(0)
    return output

# ==========================================
# 🤖 الأحداث
# ==========================================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    download_assets()
    print(f"✅ [ON_READY] البوت متصل الآن باسم: {bot.user}", flush=True)
    print(f"🎯 [ON_READY] يراقب الروم ID: {TARGET_CHANNEL_ID}", flush=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # لوق للتأكد من وصول الرسالة للبوت
    print(f"📩 [MESSAGE RECEIVED] في روم ID: {message.channel.id} من: {message.author}", flush=True)

    if message.channel.id == TARGET_CHANNEL_ID:
        print(f"✨ [MATCH] الرسالة في روم التقييم! المحتوى: '{message.content}'", flush=True)
        if not message.content.strip():
            print("⚠️ الرسالة فارغة، تم التجاهل.", flush=True)
            return

        text_content = message.content
        author_name = message.author.display_name
        avatar_url = message.author.display_avatar.with_format("png").url

        try:
            await message.delete()
            print("🗑️ تم حذف رسالة العضو الأصلية.", flush=True)
        except Exception as e:
            print(f"⚠️ تعذر حذف الرسالة (تأكد من صلاحية Manage Messages): {e}", flush=True)

        loop = asyncio.get_running_loop()
        try:
            img_bytes = await loop.run_in_executor(
                None, create_evaluation_card, text_content, author_name, str(avatar_url)
            )
            discord_file = discord.File(fp=img_bytes, filename="evaluation.png")
            await message.channel.send(file=discord_file)
            print("📸 تم إرسال صورة التقييم بنجاح!", flush=True)
        except Exception as e:
            print(f"❌ خطأ أثناء تحويل الرسالة لصورة: {e}", flush=True)

    await bot.process_commands(message)

# ==========================================
# 🚀 التشغيل
# ==========================================
if __name__ == "__main__":
    keep_alive()
    if BOT_TOKEN and BOT_TOKEN != "ضع_توكن_البوت_هنا_إن_لم_تستخدم_متغيرات_البيئة":
        bot.run(BOT_TOKEN)
    else:
        print("❌ خطأ: يرجى وضع التوكن الخاص بالبوت!", flush=True)
