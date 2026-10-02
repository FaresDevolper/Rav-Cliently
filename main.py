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
# ⚙️ الإعدادات التلقائية
# ==========================================
# آيدي الروم المخصص للتقييمات
TARGET_CHANNEL_ID = 1555520611411824711

# رابط خلفية التقييم
BG_URL = "https://cdn.discordapp.com/attachments/1339684080224174141/1555517159046774854/IMG_9353.jpg?backend=b2&ex=6ac0cfbe&is=6abf7e3e&hm=83cbeeb7e5efa4d6a1f08261fc9dac3ee2b85dd13fec999470477ea666c12c7c&"

# توكن البوت (يفضل وضعه في Render Environment Variables باسم DISCORD_TOKEN)
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "ضع_توكن_البوت_هنا_إن_لم_تستخدم_متغيرات_البيئة")

BG_FILE = "background.jpg"
FONT_FILE = "Cairo-Bold.ttf"

# ==========================================
# 🌐 سيرفر Flask لضمان استمرار التشغيل على Render
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
# 🛠️ دمج وتحميل الملحقات (الخلفية والخط)
# ==========================================
def download_assets():
    """تحميل خلفية التقييم والخط العربي تلقائياً إذا لم يكوّنا موجودين"""
    if not os.path.exists(BG_FILE):
        print("📥 جاري تحميل صورة الخلفية...")
        try:
            res = requests.get(BG_URL, timeout=10)
            with open(BG_FILE, "wb") as f:
                f.write(res.content)
            print("✅ تم تحميل صورة الخلفية.")
        except Exception as e:
            print(f"❌ خطأ أثناء تحميل الخلفية: {e}")

    if not os.path.exists(FONT_FILE):
        print("📥 جاري تحميل الخط العربي (Cairo)...")
        try:
            font_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/cairo/static/Cairo-Bold.ttf"
            res = requests.get(font_url, timeout=10)
            with open(FONT_FILE, "wb") as f:
                f.write(res.content)
            print("✅ تم تحميل الخط العربي.")
        except Exception as e:
            print(f"❌ خطأ أثناء تحميل الخط: {e}")

# ==========================================
# 🎨 دالة تصميم صورة التقييم
# ==========================================
def create_evaluation_card(text: str, username: str, avatar_url: str) -> io.BytesIO:
    # 1. فتح صورة الخلفية
    bg = Image.open(BG_FILE).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # 2. جلب أفتار المستخدم
    try:
        av_res = requests.get(avatar_url, timeout=5)
        av_img = Image.open(io.BytesIO(av_res.content)).convert("RGBA")
    except Exception as e:
        print(f"Error fetching avatar: {e}")
        av_img = Image.new("RGBA", (100, 100), (120, 120, 120, 255))

    # 3. قص الأفتار بشكل دائري ووضعه داخل المربع الأسود (x: 541..803, y: 190..237)
    av_size = (38, 38)
    av_img = av_img.resize(av_size, Image.Resampling.LANCZOS)
    mask = Image.new("L", av_size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, av_size[0], av_size[1]), fill=255)

    av_x = 803 - 6 - av_size[0]  # x = 759
    av_y = 190 + (47 - av_size[1]) // 2  # y = 194
    bg.paste(av_img, (av_x, av_y), mask)

    # 4. كتابة اسم المستخدم داخل المربع الأسود باللون الأبيض
    user_font = ImageFont.truetype(FONT_FILE, 18)
    reshaped_user = get_display(arabic_reshaper.reshape(f"@{username}"))
    draw.text((av_x - 10, av_y + 19), reshaped_user, fill=(255, 255, 255, 255), font=user_font, anchor="rm")

    # 5. تنسيق وكتابة نص التقييم داخل المستطيل الشفاف (x: 170..830, y: 280..420)
    text_font = ImageFont.truetype(FONT_FILE, 20)
    reshaped_full_text = arabic_reshaper.reshape(text)

    # تقسيم الكلام لأسطر تناسب العرض
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

    # حساب الارتفاع لتوسيط النص عمودياً
    line_height = 28
    total_height = len(display_lines) * line_height
    start_y = 350 - (total_height // 2) + 4

    for i, line in enumerate(display_lines):
        y_pos = start_y + (i * line_height)
        # رسم النص في منتصف المستطيل البيج
        draw.text((500, y_pos), line, fill=(45, 38, 30, 255), font=text_font, anchor="mm")

    # حفظ الصورة في الذاكرة
    output = io.BytesIO()
    bg.save(output, format="PNG")
    output.seek(0)
    return output

# ==========================================
# 🤖 إعدادات البوت والأحداث
# ==========================================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    download_assets()
    print(f"✅ البوت يعمل بنجاح باسم: {bot.user}")

@bot.event
async def on_message(message):
    # تجاهل رسائل البوتات
    if message.author.bot:
        return

    # الاستجابة فقط في روم التقييم المحدد
    if message.channel.id == TARGET_CHANNEL_ID:
        if not message.content.strip():
            return

        text_content = message.content
        author_name = message.author.display_name
        avatar_url = message.author.display_avatar.with_format("png").url

        # 1. حذف رسالة العضو الأصلية
        try:
            await message.delete()
        except Exception as e:
            print(f"⚠️ تعذر حذف الرسالة (تأكد من إعطاء البوت صلاحية Manage Messages): {e}")

        # 2. إنشاء الصورة وإرسالها
        loop = asyncio.get_running_loop()
        try:
            img_bytes = await loop.run_in_executor(
                None, create_evaluation_card, text_content, author_name, str(avatar_url)
            )

            discord_file = discord.File(fp=img_bytes, filename="evaluation.png")
            await message.channel.send(file=discord_file)
        except Exception as e:
            print(f"❌ خطأ أثناء تحويل الرسالة لصورة: {e}")

    await bot.process_commands(message)

# ==========================================
# 🚀 التشغيل
# ==========================================
if __name__ == "__main__":
    keep_alive()
    if BOT_TOKEN and BOT_TOKEN != "ضع_توكن_البوت_هنا_إن_لم_تستخدم_متغيرات_البيئة":
        bot.run(BOT_TOKEN)
    else:
        print("❌ خطأ: يرجى وضع توكن البوت في ملف main.py أو في متغيّرات بيئة Render!")
