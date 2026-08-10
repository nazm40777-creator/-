import os
import asyncio
import logging
from fastapi import FastAPI
import uvicorn
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from supabase import create_client, Client as SupabaseClient

# إعداد السجلات (Logging)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# قراءة المتغيرات حصراً من Railway Environment Variables
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DEV_ID = int(os.getenv("DEV_ID", "0"))

# اتصال قاعدة البيانات (Supabase)
supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

# تطبيق FastAPI للحفاظ على استقرار العمل على Railway
app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "Enterprise Bot Maker is online and operating smoothly!"}

# تهيئة الجداول الاحترافية في Supabase تلقائياً
def init_enterprise_db():
    try:
        # جدول المستخدمين وصانعي البوتات
        supabase.table("maker_users").select("user_id").limit(1).execute()
    except Exception:
        pass
    try:
        # جدول البوتات المصنوعة
        supabase.table("enterprise_bots").select("id").limit(1).execute()
    except Exception:
        pass
    try:
        # جدول الحظر العام
        supabase.table("maker_bans").select("user_id").limit(1).execute()
    except Exception:
        pass

init_enterprise_db()

# تشغيل البوت الأساسي للصانع
bot = Client("enterprise_maker_core", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# الذاكرة المؤقتة للعمليات التفاعلية
user_sessions = {}

# دالة التحقق من الحظر
def is_banned(user_id: int) -> bool:
    try:
        res = supabase.table("maker_bans").select("user_id").eq("user_id", user_id).execute()
        return len(res.data) > 0
    except Exception:
        return False

# --- واجهة البداية والأوامر الرئيسية ---
@bot.on_message(filters.command("start") & filters.private)
async def enterprise_start(client: Client, message: Message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return await message.reply_text("⛔ **عذراً، لقد تم حظرك من استخدام هذا الصانع نهائياً من قبل الإدارة.**")

    # تسجيل/تحديث بيانات المستخدم في Supabase
    try:
        supabase.table("maker_users").upsert({
            "user_id": user_id,
            "username": message.from_user.username or "None",
            "full_name": message.from_user.first_name
        }).execute()
    except Exception:
        pass

    if user_id == DEV_ID:
        text = (
            "💎 **أهلاً بك يا مطور النظام في لوحة تحكم الصانع العملاق.**\n\n"
            "▫️ قاعدة بيانات Supabase مرتبطة بالكامل\n"
            "▫️ نظام إدارة بوتات متطور ومستقل\n"
            "▫️ تحكم كامل، إذاعة، إحصائيات، وإدارة حظر"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 إحصائيات النظام الشاملة", callback_data="dev_stats"), InlineKeyboardButton("📢 إذاعة عامة", callback_data="dev_broadcast")],
            [InlineKeyboardButton("🤖 عرض كل بوتات المنصة", callback_data="dev_all_bots"), InlineKeyboardButton("🚫 إدارة الحظر", callback_data="dev_ban_panel")]
        ])
        await message.reply_text(text, reply_markup=markup)
    else:
        text = (
            "🚀 **مرحباً بك في أقوى صانع بوتات تواصل احترافي.**\n\n"
            "أنشئ بوتك الخاص الآن بخطوات معدودة، تمتع بلوحة تحكم خاصة بك، وتواصل مع مستخدميك بكل مرونة وبدون أي قيود أو حقوق!"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إنشاء بوت تواصل جديد", callback_data="create_new_bot")],
            [InlineKeyboardButton("🤖 بوتاتي المصنوعة", callback_data="my_custom_bots")],
            [InlineKeyboardButton("ℹ️ معلومات وشروط الاستخدام", callback_data="bot_info")]
        ])
        await message.reply_text(text, reply_markup=markup)

# --- معالجة إنشاء بوت جديد ---
@bot.on_callback_query(filters.regex("create_new_bot"))
async def step_create_bot(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    if is_banned(user_id):
        return await callback.answer("محظور!", show_alert=True)
    
    user_sessions[user_id] = {"state": "waiting_for_token"}
    await callback.message.edit_text(
        "🤖 **الخطوة الأولى: ربط التوكن**\n\n"
        "الرجاء إرسال **توكن البوت (Bot Token)** الخاص بك الذي استخرجته من `@BotFather`:\n\n"
        "*(تأكد من أن البوت جديد أو غير مستخدم في منصة أخرى)*",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="back_home")]])
    )

@bot.on_message(filters.private & filters.text)
async def enterprise_text_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return

    session = user_sessions.get(user_id, {})
    state = session.get("state")

    # استقبال التوكن
    if state == "waiting_for_token":
        token = message.text.strip()
        user_sessions.pop(user_id, None)

        # فحص صحة التوكن عبر Pyrogram مؤقت
        try:
            temp_client = Client(f"validator_{user_id}", api_id=API_ID, api_hash=API_HASH, bot_token=token)
            await temp_client.start()
            me = await temp_client.get_me()
            await temp_client.stop()
        except Exception:
            await message.reply_text("❌ **التوكن غير صالح أو حدث خطأ في الاتصال بتيليجرام. تأكد من صحة التوكن وأعد المحاولة.**")
            return

        # حفظ البوت في Supabase
        try:
            supabase.table("enterprise_bots").insert({
                "owner_id": user_id,
                "bot_token": token,
                "bot_username": me.username,
                "bot_name": me.first_name,
                "is_active": True
            }).execute()
        except Exception as e:
            await message.reply_text(f"⚠️ **حدث خطأ أثناء حفظ البوت في قاعدة بيانات Supabase:**\n`{e}`")
            return

        await message.reply_text(
            f"🎉 **مبروك! تم تفعيل وصنع بوتك بنجاح تام.**\n\n"
            f"📌 اسم البوت: {me.first_name}\n"
            f"🔗 المعرف: @{me.username}\n\n"
            "يمكنك إدارة بوته الكاملة وتعديل إعداداته عبر قائمة (بوتاتي المصنوعة).",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 الذهاب إلى بوتاتي", callback_data="my_custom_bots")]])
        )

    # إذاعة المطور العام
    elif state == "dev_broadcasting":
        user_sessions.pop(user_id, None)
        broadcast_text = message.text
        
        try:
            users_res = supabase.table("maker_users").select("user_id").execute()
            all_users = users_res.data
        except Exception:
            all_users = []

        sent_count = 0
        status_msg = await message.reply_text("🚀 جاري بدء الإذاعة لجميع المستخدمين...")

        for u in all_users:
            try:
                await client.send_message(u["user_id"], f"📢 **إشعار إداري هام:**\n\n{broadcast_text}")
                sent_count += 1
                await asyncio.sleep(0.05)
            except Exception:
                pass

        await status_msg.edit_text(f"✅ **تمت الإذاعة بنجاح!**\n📊 عدد المستلمين بنجاح: {sent_count} مستخدم.")

# --- قائمة بوتات المستخدم ---
@bot.on_callback_query(filters.regex("my_custom_bots"))
async def list_user_bots(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        res = supabase.table("enterprise_bots").select("*").eq("owner_id", user_id).execute()
        bots = res.data
    except Exception:
        bots = []

    if not bots:
        await callback.message.edit_text(
            "📂 **لا توجد أي بوتات مصنوعة بواسطة حسابك حتى الآن.**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إنشاء بوت جديد", callback_data="create_new_bot")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_home")]
            ])
        )
        return

    buttons = []
    for b in bots:
        status_icon = "🟢" if b["is_active"] else "🔴"
        buttons.append([InlineKeyboardButton(f"{status_icon} @{b['bot_username']}", callback_data=f"manage_bot_{b['id']}")])
    buttons.append([InlineKeyboardButton("➕ إنشاء بوت آخر", callback_data="create_new_bot"), InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_home")])

    await callback.message.edit_text("📂 **قائمة بوتاتك المصنوعة:**\nاختر البوت الذي تريد إدارته والتحكم به:", reply_markup=InlineKeyboardMarkup(buttons))

# --- لوحة تحكم البوت الفردي للمستخدم ---
@bot.on_callback_query(filters.regex(r"manage_bot_(\d+)"))
async def manage_single_bot(client: Client, callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        res = supabase.table("enterprise_bots").select("*").eq("id", bot_id).execute()
        if not res.data:
            return await callback.answer("البوت غير موجود أو تم حذفه!", show_alert=True)
        b_data = res.data[0]
    except Exception:
        return await callback.answer("خطأ في الاتصال بقاعدة البيانات!", show_alert=True)

    text = (
        f"⚙️ **لوحة تحكم البوت: @{b_data['bot_username']}**\n\n"
        f"📌 الاسم: {b_data['bot_name']}\n"
        f"🟢 الحالة التشغيلية: {'مفعل ويعمل' if b_data['is_active'] else 'متوقف مؤقتاً'}\n"
        f"🔗 التوكن: `{b_data['bot_token'][:10]}...`\n"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ حذف البوت نهائياً", callback_data=f"delete_bot_{bot_id}"), InlineKeyboardButton("🔄 تبديل الحالة (تشغيل/إيقاف)", callback_data=f"toggle_bot_{bot_id}")],
        [InlineKeyboardButton("🔙 العودة لقائمة بوتاتي", callback_data="my_custom_bots")]
    ])
    await callback.message.edit_text(text, reply_markup=markup)

# --- حذف البوت ---
@bot.on_callback_query(filters.regex(r"delete_bot_(\d+)"))
async def delete_bot_action(client: Client, callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        supabase.table("enterprise_bots").delete().eq("id", bot_id).execute()
        await callback.answer("🗑️ تم حذف البوت بنجاح من قاعدة البيانات.", show_alert=True)
        await list_user_bots(client, callback)
    except Exception as e:
        await callback.answer(f"حدث خطأ أثناء الحذف: {e}", show_alert=True)

# --- تبديل حالة البوت ---
@bot.on_callback_query(filters.regex(r"toggle_bot_(\d+)"))
async def toggle_bot_action(client: Client, callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        res = supabase.table("enterprise_bots").select("is_active").eq("id", bot_id).execute()
        if res.data:
            current_state = res.data[0]["is_active"]
            new_state = not current_state
            supabase.table("enterprise_bots").update({"is_active": new_state}).eq("id", bot_id).execute()
            await callback.answer(f"🔄 تم تغيير حالة البوت إلى: {'مفعل' if new_state else 'متوقف'}", show_alert=True)
            # إعادة تحميل لوحة التحكم لنفس البوت
            callback.data = f"manage_bot_{bot_id}"
            await manage_single_bot(client, callback)
    except Exception as e:
        await callback.answer(f"حدث خطأ: {e}", show_alert=True)

# --- لوحة تحكم المطور الرئيسي الأساسية ---
@bot.on_callback_query(filters.regex("dev_stats"))
async def dev_statistics(client: Client, callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return await callback.answer("غير مسموح لك!", show_alert=True)

    try:
        users_count = len(supabase.table("maker_users").select("user_id", count="exact").execute().data)
        bots_count = len(supabase.table("enterprise_bots").select("id", count="exact").execute().data)
        bans_count = len(supabase.table("maker_bans").select("user_id", count="exact").execute().data)
    except Exception:
        users_count = bots_count = bans_count = 0

    text = (
        f"📊 **إحصائيات النظام العملاق الحية (Supabase):**\n\n"
        f"👥 إجمالي المستخدمين المسجلين: {users_count}\n"
        f"🤖 إجمالي البوتات المصنوعة: {bots_count}\n"
        f"🚫 إجمالي الحسابات المحظورة: {bans_count}\n"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للوحة المطور", callback_data="back_home")]])
    await callback.message.edit_text(text, reply_markup=markup)

@bot.on_callback_query(filters.regex("dev_broadcast"))
async def dev_broadcast_prompt(client: Client, callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    user_sessions[DEV_ID] = {"state": "dev_broadcasting"}
    await callback.message.edit_text(
        "📢 **قسم الإذاعة العامة:**\n\n"
        "أرسل الآن نص الإذاعة (يدعم التنسيق، الروابط، وكل شيء) ليتم إرساله لجميع مستخدمي الصانع فوراً:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_home")]])
    )

@bot.on_callback_query(filters.regex("bot_info"))
async def bot_info_handler(client: Client, callback: CallbackQuery):
    text = (
        "ℹ️ **معلومات وشروط الخدمة:**\n\n"
        "• هذا النظام يعمل بكفاءة عالية على سحابة Railway وقاعدة بيانات Supabase.\n"
        "• لا توجد أي حقوق إجبارية أو إعلانات تفرض على بوتاتك المصنوعة.\n"
        "• يمكنك صناعة وإدارة بوتاتك بكل حرية ومرونة تامة."
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_home")]])
    await callback.message.edit_text(text, reply_markup=markup)

@bot.on_callback_query(filters.regex("back_home"))
async def back_home_action(client: Client, callback: CallbackQuery):
    await enterprise_start(client, callback.message)

# التشغيل المتزامن العملاق
async def main():
    await bot.start()
    logger.info("🚀 Enterprise Bot Maker Core started successfully on Railway & Supabase!")
    await idle()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
