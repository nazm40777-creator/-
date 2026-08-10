import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from supabase import create_client, Client as SupabaseClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# قراءة المتغيرات
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DEV_ID = int(os.getenv("DEV_ID", "5126968608"))

supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

# تهيئة الجداول تلقائياً
def init_full_db():
    try:
        supabase.table("maker_users").select("user_id").limit(1).execute()
        supabase.table("enterprise_bots").select("id").limit(1).execute()
        supabase.table("maker_bans").select("user_id").limit(1).execute()
    except Exception as e:
        logger.warning(f"ملاحظة الجداول: {e}")

init_full_db()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_sessions = {}

def is_banned(user_id: int) -> bool:
    try:
        res = supabase.table("maker_bans").select("user_id").eq("user_id", user_id).execute()
        return len(res.data) > 0
    except Exception:
        return False

@dp.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return await message.answer("⛔ **عذراً، لقد تم حظرك من استخدام هذا الصانع نهائياً.**")

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
            "▫️ تحكم كامل، إحصائيات، وإدارة شاملة."
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 إحصائيات النظام", callback_data="dev_stats"), InlineKeyboardButton(text="📢 إذاعة عامة", callback_data="dev_broadcast")],
            [InlineKeyboardButton(text="🤖 إدارة كل البوتات", callback_data="dev_all_bots"), InlineKeyboardButton(text="🚫 إدارة الحظر", callback_data="dev_ban_menu")]
        ])
        await message.answer(text, reply_markup=markup)
    else:
        text = (
            "🚀 **مرحباً بك في أقوى صانع بوتات تواصل احترافي.**\n\n"
            "أنشئ بوتك الخاص الآن وتمتع بلوحة تحكم متكاملة!"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ إنشاء بوت تواصل جديد", callback_data="create_new_bot")],
            [InlineKeyboardButton(text="🤖 بوتاتي المصنوعة", callback_data="my_custom_bots")],
            [InlineKeyboardButton(text="ℹ️ معلومات وشروط الاستخدام", callback_data="bot_info")]
        ])
        await message.answer(text, reply_markup=markup)

@dp.callback_query(F.data == "create_new_bot")
async def step_create_bot(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_sessions[user_id] = {"state": "waiting_for_token"}
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء والعودة", callback_data="back_home")]])
    await callback.message.edit_text(
        "🤖 **خطوة إنشاء بوت تواصل جديد:**\n\nالرجاء إرسال **توكن البوت (Bot Token)** الخاص بك من `@BotFather`:",
        reply_markup=markup
    )
    await callback.answer()

@dp.message(F.text)
async def text_processor(message: Message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return

    session = user_sessions.get(user_id, {})
    state = session.get("state")

    if state == "waiting_for_token":
        token = message.text.strip()
        user_sessions.pop(user_id, None)

        try:
            temp_bot = Bot(token=token)
            me = await temp_bot.get_me()
            await temp_bot.session.close()
        except Exception as e:
            return await message.answer(f"❌ **التوكن غير صالح أو حدث خطأ:**\n`{e}`\n\nتأكد من صحة التوكن وأعد المحاولة.")

        try:
            supabase.table("enterprise_bots").insert({
                "owner_id": user_id,
                "bot_token": token,
                "bot_username": me.username,
                "bot_name": me.first_name,
                "is_active": True
            }).execute()
        except Exception as e:
            return await message.answer(f"⚠️ **خطأ أثناء الحفظ في Supabase:**\n`{e}`")

        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🤖 الذهاب إلى بوتاتي", callback_data="my_custom_bots")]])
        await message.answer(
            f"🎉 **مبروك! تم تفعيل وصنع بوتك بنجاح تام.**\n\n"
            f"📌 اسم البوت: {me.first_name}\n"
            f"🔗 المعرف: @{me.username}",
            reply_markup=markup
        )

    elif state == "dev_broadcasting" and user_id == DEV_ID:
        user_sessions.pop(user_id, None)
        b_text = message.text
        try:
            users = supabase.table("maker_users").select("user_id").execute().data
        except Exception:
            users = []

        sent = 0
        status = await message.answer("🚀 جاري بدء الإذاعة لجميع المستخدمين...")
        for u in users:
            try:
                await bot.send_message(u["user_id"], f"📢 **إشعار إداري هام:**\n\n{b_text}")
                sent += 1
                await asyncio.sleep(0.04)
            except Exception:
                pass
        await status.edit_text(f"✅ **تمت الإذاعة بنجاح!**\n📊 عدد المستلمين: {sent} مستخدم.")

    elif state == "dev_waiting_ban" and user_id == DEV_ID:
        user_sessions.pop(user_id, None)
        try:
            target_id = int(message.text.strip())
            supabase.table("maker_bans").upsert({"user_id": target_id}).execute()
            await message.answer(f"🚫 **تم حظر المستخدم (`{target_id}`) بنجاح.**")
        except Exception:
            await message.answer("❌ **حدث خطأ، تأكد من كتابة الآيدي بشكل صحيح (أرقام فقط).**")

@dp.callback_query(F.data == "my_custom_bots")
async def list_user_bots(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        res = supabase.table("enterprise_bots").select("*").eq("owner_id", user_id).execute()
        bots = res.data
    except Exception:
        bots = []

    if not bots:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ إنشاء بوت جديد", callback_data="create_new_bot")],
            [InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_home")]
        ])
        return await callback.message.edit_text("📂 **لا توجد أي بوتات مصنوعة بواسطة حسابك حتى الآن.**", reply_markup=markup)

    buttons = []
    for b in bots:
        status = "🟢" if b["is_active"] else "🔴"
        buttons.append([InlineKeyboardButton(text=f"{status} @{b['bot_username']}", callback_data=f"manage_bot_{b['id']}")])
    buttons.append([InlineKeyboardButton(text="➕ إنشاء بوت آخر", callback_data="create_new_bot"), InlineKeyboardButton(text="🔙 القائمة الرئيسية", callback_data="back_home")])

    await callback.message.edit_text("📂 **قائمة بوتاتك المصنوعة:**\nاختر البوت لإدارة إعداداته:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("manage_bot_"))
async def manage_single_bot(callback: CallbackQuery):
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
        f"🟢 الحالة: {'مفعل ويعمل' if b_data['is_active'] else 'متوقف'}\n"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ حذف البوت", callback_data=f"delete_bot_{bot_id}"), InlineKeyboardButton(text="🔄 تشغيل/إيقاف", callback_data=f"toggle_bot_{bot_id}")],
        [InlineKeyboardButton(text="🔙 العودة", callback_data="my_custom_bots")]
    ])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_bot_"))
async def delete_bot_action(callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        supabase.table("enterprise_bots").delete().eq("id", bot_id).execute()
        await callback.answer("🗑️ تم حذف البوت بنجاح.", show_alert=True)
        await list_user_bots(callback)
    except Exception as e:
        await callback.answer(f"خطأ: {e}", show_alert=True)

@dp.callback_query(F.data == "dev_stats")
async def dev_stats_handler(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    try:
        users = len(supabase.table("maker_users").select("user_id").execute().data)
        bots = len(supabase.table("enterprise_bots").select("id").execute().data)
        bans = len(supabase.table("maker_bans").select("user_id").execute().data)
    except Exception:
        users = bots = bans = 0

    text = f"📊 **إحصائيات النظام:**\n\n👥 المستخدمين: {users}\n🤖 البوتات: {bots}\n🚫 المحظورين: {bans}"
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")]])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "dev_broadcast")
async def dev_broadcast_handler(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    user_sessions[DEV_ID] = {"state": "dev_broadcasting"}
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_home")]])
    await callback.message.edit_text("📢 **قسم الإذاعة:**\n\nأرسل الآن نص الإذاعة لجميع المستخدمين:", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "dev_ban_menu")
async def dev_ban_menu(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 حظر مستخدم", callback_data="do_ban")],
        [InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")]
    ])
    await callback.message.edit_text("🚫 **إدارة الحظر:**", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "do_ban")
async def do_ban(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    user_sessions[DEV_ID] = {"state": "dev_waiting_ban"}
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 إلغاء", callback_data="back_home")]])
    await callback.message.edit_text("أرسل الآن **آيدي المستخدم** المراد حظره:", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "bot_info")
async def bot_info(callback: CallbackQuery):
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 رجوع", callback_data="back_home")]])
    await callback.message.edit_text("ℹ️ النظام يعمل بكفاءة عالية على Railway وقاعدة بيانات Supabase.", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "back_home")
async def back_home(callback: CallbackQuery):
    # إعادة توجيه القائمة الرئيسية
    fake_message = callback.message
    fake_message.from_user = callback.from_user
    await start_handler(fake_message)
    await callback.answer()

async def main():
    logger.info("🚀 Aiogram Enterprise Bot Maker started successfully!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
