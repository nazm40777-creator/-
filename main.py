import os
import asyncio
import logging
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from supabase import create_client, Client as SupabaseClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# قراءة المتغيرات والتأكد من تحويل api_id و dev_id إلى أرقام صحيحة تفادياً لأخطاء المصادقة والصلاحيات
API_ID = int(os.getenv("API_ID", "33363072"))
API_HASH = os.getenv("API_HASH", "6822a1b168bfc677c717d0173c28cf1d")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DEV_ID = int(os.getenv("DEV_ID", "5126968608"))

supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

# تهيئة الجداول في Supabase تلقائياً لضمان عمل كل المميزات
def init_full_db():
    try:
        supabase.table("maker_users").select("user_id").limit(1).execute()
        supabase.table("enterprise_bots").select("id").limit(1).execute()
        supabase.table("maker_bans").select("user_id").limit(1).execute()
        supabase.table("bot_messages").select("id").limit(1).execute()
    except Exception as e:
        logger.warning(f"ملاحظة أثناء التحقق من الجداول: {e}")

init_full_db()

bot = Client("full_enterprise_maker", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_sessions = {}

def is_banned(user_id: int) -> bool:
    try:
        res = supabase.table("maker_bans").select("user_id").eq("user_id", user_id).execute()
        return len(res.data) > 0
    except Exception:
        return False

# --- البداية ولوحات التحكم الرئيسية ---
@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return await message.reply_text("⛔ **عذراً، لقد تم حظرك من استخدام هذا الصانع نهائياً.**")

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
            "💎 **أهلاً بك يا مطور النظام في لوحة تحكم الصانع العملاق والشامل.**\n\n"
            "▫️ تحكم كامل، إذاعة عامة، إدارة الحظر، وإحصائيات حية.\n"
            "▫️ جميع مميزات الصانع مفعلة وجاهزة!"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 إحصائيات النظام", callback_data="dev_stats"), InlineKeyboardButton("📢 إذاعة عامة", callback_data="dev_broadcast")],
            [InlineKeyboardButton("🤖 إدارة كل البوتات", callback_data="dev_all_bots"), InlineKeyboardButton("🚫 إدارة الحظر", callback_data="dev_ban_menu")]
        ])
        await message.reply_text(text, reply_markup=markup)
    else:
        text = (
            "🚀 **مرحباً بك في أقوى صانع بوتات تواصل احترافي.**\n\n"
            "أنشئ بوتك الخاص الآن، تمتع بلوحة تحكم متكاملة، ونظام تواصل مرن وبدون أي قيود أو حقوق!"
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إنشاء بوت تواصل جديد", callback_data="create_new_bot")],
            [InlineKeyboardButton("🤖 بوتاتي المصنوعة", callback_data="my_custom_bots")],
            [InlineKeyboardButton("ℹ️ معلومات وشروط الاستخدام", callback_data="bot_info")]
        ])
        await message.reply_text(text, reply_markup=markup)

# --- إنشاء بوت جديد ---
@bot.on_callback_query(filters.regex("create_new_bot"))
async def step_create_bot(client: Client, callback: CallbackQuery):
    user_id = callback.from_user.id
    user_sessions[user_id] = {"state": "waiting_for_token"}
    await callback.message.edit_text(
        "🤖 **خطوة إنشاء بوت تواصل جديد:**\n\n"
        "الرجاء إرسال **توكن البوت (Bot Token)** الخاص بك من `@BotFather`:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء والعودة", callback_data="back_home")]])
    )

# --- معالجة المدخلات النصية (التوكن، الإذاعة، الحظر) ---
@bot.on_message(filters.private & filters.text)
async def text_processor(client: Client, message: Message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return

    session = user_sessions.get(user_id, {})
    state = session.get("state")

    # 1. استقبال التوكن وإنشاء البوت
    if state == "waiting_for_token":
        token = message.text.strip()
        user_sessions.pop(user_id, None)

        try:
            temp_client = Client(f"val_{user_id}_{message.id}", api_id=API_ID, api_hash=API_HASH, bot_token=token)
            await temp_client.start()
            me = await temp_client.get_me()
            await temp_client.stop()
        except Exception as e:
            return await message.reply_text(f"❌ **التوكن غير صالح أو حدث خطأ:**\n`{e}`\n\nتأكد من صحة التوكن وأعد المحاولة.")

        try:
            supabase.table("enterprise_bots").insert({
                "owner_id": user_id,
                "bot_token": token,
                "bot_username": me.username,
                "bot_name": me.first_name,
                "is_active": True
            }).execute()
        except Exception as e:
            return await message.reply_text(f"⚠️ **خطأ أثناء الحفظ في Supabase:**\n`{e}`")

        await message.reply_text(
            f"🎉 **مبروك! تم تفعيل وصنع بوتك بنجاح تام.**\n\n"
            f"📌 اسم البوت: {me.first_name}\n"
            f"🔗 المعرف: @{me.username}\n\n"
            "يمكنك إدارته بالكامل من قائمة (بوتاتي المصنوعة).",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🤖 الذهاب إلى بوتاتي", callback_data="my_custom_bots")]])
        )

    # 2. الإذاعة العامة (للمطور الرئيسي)
    elif state == "dev_broadcasting" and user_id == DEV_ID:
        user_sessions.pop(user_id, None)
        b_text = message.text
        try:
            users = supabase.table("maker_users").select("user_id").execute().data
        except Exception:
            users = []

        sent = 0
        status = await message.reply_text("🚀 جاري بدء الإذاعة لجميع المستخدمين...")
        for u in users:
            try:
                await client.send_message(u["user_id"], f"📢 **إشعار إداري هام:**\n\n{b_text}")
                sent += 1
                await asyncio.sleep(0.04)
            except Exception:
                pass
        await status.edit_text(f"✅ **تمت الإذاعة بنجاح!**\n📊 عدد المستلمين: {sent} مستخدم.")

    # 3. حظر مستخدم (للمطور الرئيسي)
    elif state == "dev_waiting_ban" and user_id == DEV_ID:
        user_sessions.pop(user_id, None)
        try:
            target_id = int(message.text.strip())
            supabase.table("maker_bans").upsert({"user_id": target_id}).execute()
            await message.reply_text(f"🚫 **تم حظر المستخدم (`{target_id}`) بنجاح من الصانع.**")
        except Exception:
            await message.reply_text("❌ **حدث خطأ، تأكد من كتابة الآيدي بشكل صحيح (أرقام فقط).**")

    # 4. إلغاء حظر مستخدم (للمطور الرئيسي)
    elif state == "dev_waiting_unban" and user_id == DEV_ID:
        user_sessions.pop(user_id, None)
        try:
            target_id = int(message.text.strip())
            supabase.table("maker_bans").delete().eq("user_id", target_id).execute()
            await message.reply_text(f"✅ **تم إلغاء حظر المستخدم (`{target_id}`) بنجاح.**")
        except Exception:
            await message.reply_text("❌ **حدث خطأ، تأكد من الآيدي.**")

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
        return await callback.message.edit_text(
            "📂 **لا توجد أي بوتات مصنوعة بواسطة حسابك حتى الآن.**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إنشاء بوت جديد", callback_data="create_new_bot")],
                [InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_home")]
            ])
        )

    buttons = []
    for b in bots:
        status = "🟢" if b["is_active"] else "🔴"
        buttons.append([InlineKeyboardButton(f"{status} @{b['bot_username']}", callback_data=f"manage_bot_{b['id']}")])
    buttons.append([InlineKeyboardButton("➕ إنشاء بوت آخر", callback_data="create_new_bot"), InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_home")])

    await callback.message.edit_text("📂 **قائمة بوتاتك المصنوعة:**\nاختر البوت لإدارة إعداداته:", reply_markup=InlineKeyboardMarkup(buttons))

# --- لوحة تحكم البوت المفرد ---
@bot.on_callback_query(filters.regex(r"manage_bot_(\d+)"))
async def manage_single_bot(client: Client, callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        res = supabase.table("enterprise_bots").select("*").eq("id", bot_id).execute()
        if not res.data:
            return await callback.answer("البوت غير موجود!", show_alert=True)
        b_data = res.data[0]
    except Exception:
        return await callback.answer("خطأ في الاتصال بقاعدة البيانات!", show_alert=True)

    text = (
        f"⚙️ **لوحة تحكم البوت: @{b_data['bot_username']}**\n\n"
        f"📌 الاسم: {b_data['bot_name']}\n"
        f"🟢 الحالة التشغيلية: {'مفعل ويعمل' if b_data['is_active'] else 'متوقف'}\n"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ حذف البوت نهائياً", callback_data=f"delete_bot_{bot_id}"), InlineKeyboardButton("🔄 تشغيل/إيقاف", callback_data=f"toggle_bot_{bot_id}")],
        [InlineKeyboardButton("🔙 العودة لقائمة بوتاتي", callback_data="my_custom_bots")]
    ])
    await callback.message.edit_text(text, reply_markup=markup)

# --- حذف البوت ---
@bot.on_callback_query(filters.regex(r"delete_bot_(\d+)"))
async def delete_bot_action(client: Client, callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        supabase.table("enterprise_bots").delete().eq("id", bot_id).execute()
        await callback.answer("🗑️ تم حذف البوت بنجاح.", show_alert=True)
        await list_user_bots(client, callback)
    except Exception as e:
        await callback.answer(f"خطأ: {e}", show_alert=True)

# --- تبديل حالة البوت ---
@bot.on_callback_query(filters.regex(r"toggle_bot_(\d+)"))
async def toggle_bot_action(client: Client, callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        res = supabase.table("enterprise_bots").select("is_active").eq("id", bot_id).execute()
        if res.data:
            new_state = not res.data[0]["is_active"]
            supabase.table("enterprise_bots").update({"is_active": new_state}).eq("id", bot_id).execute()
            await callback.answer(f"🔄 الحالة الجديدة: {'مفعل' if new_state else 'متوقف'}", show_alert=True)
            callback.data = f"manage_bot_{bot_id}"
            await manage_single_bot(client, callback)
    except Exception as e:
        await callback.answer(f"خطأ: {e}", show_alert=True)

# --- لوحات تحكم المطور الرئيسي الشاملة ---
@bot.on_callback_query(filters.regex("dev_stats"))
async def dev_stats_handler(client: Client, callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    try:
        users = len(supabase.table("maker_users").select("user_id", count="exact").execute().data)
        bots = len(supabase.table("enterprise_bots").select("id", count="exact").execute().data)
        bans = len(supabase.table("maker_bans").select("user_id", count="exact").execute().data)
    except Exception:
        users = bots = bans = 0

    text = (
        f"📊 **إحصائيات النظام العملاق الحية:**\n\n"
        f"👥 إجمالي المستخدمين: {users}\n"
        f"🤖 إجمالي البوتات المصنوعة: {bots}\n"
        f"🚫 إجمالي المحظورين: {bans}\n"
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع لوحة المطور", callback_data="back_home")]])
    await callback.message.edit_text(text, reply_markup=markup)

@bot.on_callback_query(filters.regex("dev_broadcast"))
async def dev_broadcast_handler(client: Client, callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    user_sessions[DEV_ID] = {"state": "dev_broadcasting"}
    await callback.message.edit_text(
        "📢 **قسم الإذاعة العامة:**\n\nأرسل الآن نص الإذاعة لجميع مستخدمي المنصة:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_home")]])
    )

@bot.on_callback_query(filters.regex("dev_ban_menu"))
async def dev_ban_menu(client: Client, callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="do_ban"), InlineKeyboardButton("✅ إلغاء حظر مستخدم", callback_data="do_unban")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back_home")]
    ])
    await callback.message.edit_text("🚫 **إدارة الحظر والحماية:**\nاختر الإجراء المطلوب:", reply_markup=markup)

@bot.on_callback_query(filters.regex("do_ban"))
async def do_ban(client: Client, callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    user_sessions[DEV_ID] = {"state": "dev_waiting_ban"}
    await callback.message.edit_text("أرسل الآن **آيدي المستخدم** المراد حظره:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_home")]]))

@bot.on_callback_query(filters.regex("do_unban"))
async def do_unban(client: Client, callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    user_sessions[DEV_ID] = {"state": "dev_waiting_unban"}
    await callback.message.edit_text("أرسل الآن **آيدي المستخدم** المراد إلغاء حظره:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 إلغاء", callback_data="back_home")]]))

@bot.on_callback_query(filters.regex("dev_all_bots"))
async def dev_all_bots(client: Client, callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    try:
        res = supabase.table("enterprise_bots").select("bot_username, owner_id").execute().data
    except Exception:
        res = []

    text = "🤖 **جميع بوتات المنصة المصنوعة:**\n\n"
    if not res:
        text += "لا توجد بوتات حالياً."
    else:
        for idx, b in enumerate(res, 1):
            text += f"{idx}. @{b['bot_username']} (المشترك: `{b['owner_id']}`)\n"

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_home")]])
    await callback.message.edit_text(text, reply_markup=markup)

@bot.on_callback_query(filters.regex("bot_info"))
async def bot_info(client: Client, callback: CallbackQuery):
    text = (
        "ℹ️ **معلومات وشروط الخدمة:**\n\n"
        "• النظام يعمل بكفاءة على سحابة Railway وقاعدة بيانات Supabase.\n"
        "• بدون أي حقوق إجبارية أو قيود على بوتاتك المصنوعة."
    )
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_home")]])
    await callback.message.edit_text(text, reply_markup=markup)

@bot.on_callback_query(filters.regex("back_home"))
async def back_home(client: Client, callback: CallbackQuery):
    await start_handler(client, callback.message)

# التشغيل النهائي
async def main():
    await bot.start()
    logger.info("🚀 Full Enterprise Bot Maker started successfully!")
    await idle()

if __name__ == "__main__":
    asyncio.run(main())
