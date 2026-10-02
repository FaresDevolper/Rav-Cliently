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

# ==========================================
# ⚙️ الإعدادات
# ==========================================
TARGET_CHANNEL_ID = 1555520611411824711

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
# 🛠️ التأكد من وجود الملحقات
# ==========================================
def check_assets():
    if not os.path.exists(FONT_FILE):
        print(f"⚠️ تنبيه: ملف الخط '{FONT_FILE}' غير موجود في المشروع!", flush=True)
    else:
        print(f"✅ تم العثور على ملف الخط: {FONT_FILE}", flush=True)

    if not os.path.exists(BG_FILE):
        print(f"⚠️ تنبيه: ملف الخلفية '{BG_FILE}' غير موجود في المشروع!", flush=True)
    else:
        print(f"✅ تم العثور على ملف الخلفية: {BG_FILE}", flush=True)

# ==========================================
# ✍️ دالة معالجة النصوص العربية لـ Pillow
# ==========================================
def format_text_for_pil(text: str) -> str:
    """
    تشكيل وعكس النص العربي ليتم رسمه من اليمين للجميع بشكل صحيح
    """
    has_arabic = any('\u0600' <= c <= '\u06FF' or '\uFE70' <= c <= '\uFEFF' for c in text)
    if has_arabic:
        reshaped = arabic_reshaper.reshape(text)
        return reshaped[::-1]
    return text

# ==========================================
# 🎨 دالة تصميم الصورة
# ==========================================
def create_evaluation_card(text: str, username: str, avatar_url: str) -> io.BytesIO:
    if not os.path.exists(BG_FILE):
        raise FileNotFoundError(f"ملف الخلفية '{BG_FILE}' غير موجود!")

    if not os.path.exists(FONT_FILE):
        raise FileNotFoundError(f"ملف الخط '{FONT_FILE}' غير موجود!")

    bg = Image.open(BG_FILE).convert("RGBA")
    draw = ImageDraw.Draw(bg)

    # 1. جلب صورة الأفتار وتشكيلها كدائرة
    try:
        av_res = requests.get(avatar_url, timeout=5)
        av_res.raise_for_status()
        av_img = Image.open(io.BytesIO(av_res.content)).convert("RGBA")
    except Exception as e:
        print(f"⚠️ تعذر جلب الأفتار: {e}", flush=True)
        av_img = Image.new("RGBA", (100, 100), (120, 120, 120, 255))

    av_size = (42, 42)
    av_img = av_img.resize(av_size, Image.Resampling.LANCZOS)
    
    mask = Image.new("L", av_size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, av_size[0], av_size[1]), fill=255)

    # وضع الأفتار داخل المربع الأسود العلوي
    av_x = 755
    av_y = 192
    bg.paste(av_img, (av_x, av_y), mask)

    # 2. رسم اسم العضو (اليوزر) باللون الأبيض بجانب الأفتار
    user_font = ImageFont.truetype(FONT_FILE, 20)
    formatted_username = format_text_for_pil(username)
    
    draw.text(
        (av_x - 15, av_y + (av_size[1] // 2)),
        formatted_username,
        fill=(255, 255, 255, 255),
        font=user_font,
        anchor="rm"  # محاذاة يمين النص ليلتصق بجانب الأفتار
    )

    # 3. رسم نص التقييم في المستطيل البيج السفلي بالكامل
    text_font = ImageFont.truetype(FONT_FILE, 22)
    
    words = text.split(' ')
    lines = []
    current_line = []
    max_width = 650

    for word in words:
        test_line = ' '.join(current_line + [word])
        display_test = format_text_for_pil(test_line)
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

    display_lines = [format_text_for_pil(line) for line in lines]

    line_height = 34
    total_height = len(display_lines) * line_height
    
    # تحديد منتصف المستطيل البيج السفلي
    center_y = int(bg.height * 0.63) if bg.height > 400 else 470
    start_y = center_y - (total_height // 2)
    center_x = bg.width // 2

    for i, line in enumerate(display_lines):
        y_pos = start_y + (i * line_height)
        draw.text(
            (center_x, y_pos),
            line,
            fill=(45, 38, 30, 255),  # لون غامق مناسب للخلفية البيج
            font=text_font,
            anchor="mm"  # تمركز أفقي وعمودي في منتصف المستطيل السفلي
        )

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
    check_assets()
    print(f"✅ [ON_READY] البوت متصل الآن باسم: {bot.user}", flush=True)
    print(f"🎯 [ON_READY] يراقب الروم ID: {TARGET_CHANNEL_ID}", flush=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == TARGET_CHANNEL_ID:
        if not message.content.strip():
            return

        text_content = message.content
        author_name = message.author.display_name
        avatar_url = message.author.display_avatar.with_format("png").url

        try:
            await message.delete()
        except Exception as e:
            print(f"⚠️ تعذر حذف الرسالة: {e}", flush=True)

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
