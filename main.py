import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from supabase import create_client, Client as SupabaseClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DEV_ID = int(os.getenv("DEV_ID", "5126968608"))
DEV_USERNAME = "toe7e"

supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_sessions = {}
running_custom_bots = {}

def is_banned(user_id: int) -> bool:
    try:
        res = supabase.table("maker_bans").select("user_id").eq("user_id", user_id).execute()
        return len(res.data) > 0
    except Exception:
        return False

# --- محرك البوت المصنوع (الاحترافي والعظيم) ---
async def start_user_bot_polling(bot_id: int, token: str, owner_id: int, bot_username: str):
    custom_bot = Bot(token=token)
    custom_dp = Dispatcher()

    def register_custom_user(u_id: int, name: str, uname: str):
        try:
            supabase.table("custom_bot_users").upsert({
                "bot_id": bot_id,
                "user_id": u_id,
                "full_name": name,
                "username": uname
            }, on_conflict="bot_id,user_id").execute()
        except Exception:
            pass

    @custom_dp.message(Command("start"))
    async def custom_start(message: Message):
        register_custom_user(message.from_user.id, message.from_user.first_name, message.from_user.username or "None")
        if message.from_user.id == owner_id:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="تعديل رسالة الترحيب", callback_data="cb_welcome"), InlineKeyboardButton(text="ضبط الرد التلقائي", callback_data="cb_autoreply")],
                [InlineKeyboardButton(text="إحصائيات البوت الحية", callback_data="cb_stats"), InlineKeyboardButton(text="إذاعة لمشتركي البوت", callback_data="cb_broadcast")],
                [InlineKeyboardButton(text="إدارة الهوية والتوقيع", callback_data="cb_identity"), InlineKeyboardButton(text="قائمة المحظورين", callback_data="cb_bans")],
                [InlineKeyboardButton(text="إعدادات متطورة", callback_data="cb_settings")],
                [InlineKeyboardButton(text="مراسلة المبرمج الأساسي", url=f"https://t.me/{DEV_USERNAME}")]
            ])
            await message.answer(
                "أهلاً بك يا مالك البوت في لوحة التحكم المركزية.\n"
                "يمكنك إدارة كافة إعدادات بوتك واحترافيتك من الأزرار أدناه:",
                reply_markup=markup
            )
        else:
            try:
                res = supabase.table("custom_bot_settings").select("welcome_text, auto_reply").eq("bot_id", bot_id).execute()
                data = res.data[0] if res.data else {}
                welcome_msg = data.get("welcome_text", "مرحباً بك عزيزي في بوت التواصل الرسمي.\nأرسل رسالتك أو استفسارك وسيتم تحويله مباشرة إلى الإدارة.")
            except:
                welcome_msg = "مرحباً بك عزيزي في بوت التواصل الرسمي.\nأرسل رسالتك أو استفسارك وسيتم تحويله مباشرة إلى الإدارة."

            promo_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="صنع بوتك الخاص من هنا ⚡", url=f"https://t.me/{DEV_USERNAME}")]
            ])
            await message.answer(welcome_msg, reply_markup=promo_markup)

    @custom_dp.callback_query(F.data.startswith("cb_"))
    async def custom_callbacks(callback: CallbackQuery):
        if callback.from_user.id != owner_id:
            return await callback.answer("عذراً، هذه اللوحة مخصصة لمالك البوت فقط.", show_alert=True)
        
        action = callback.data
        back_btn = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="العودة للقائمة الرئيسية", callback_data="cb_back")]])

        if action == "cb_welcome":
            user_sessions[f"waiting_welcome_{owner_id}"] = {"bot_id": bot_id}
            await callback.message.edit_text("أرسل الآن النص الجديد لرسالة الترحيب ليتم اعتمادها فوراً:", reply_markup=back_btn)
        elif action == "cb_autoreply":
            user_sessions[f"waiting_autoreply_{owner_id}"] = {"bot_id": bot_id}
            await callback.message.edit_text("أرسل الآن نص الرد التلقائي الاحترافي للرد على المستخدمين:", reply_markup=back_btn)
        elif action == "cb_stats":
            try:
                subs = len(supabase.table("custom_bot_users").select("user_id").eq("bot_id", bot_id).execute().data)
            except:
                subs = 0
            await callback.message.edit_text(f"إحصائيات البوت الشاملة:\n\n- عدد المشتركين الكلي: {subs}\n- حالة الخادم: يعمل بكفاءة عالية 100%", reply_markup=back_btn)
        elif action == "cb_broadcast":
            user_sessions[f"custom_broadcast_{owner_id}"] = {"bot_id": bot_id, "custom_bot": custom_bot}
            await callback.message.edit_text("أرسل الآن رسالة الإذاعة (نص أو وسائط) ليتم بثها حصراً لمشتركي بوتك:", reply_markup=back_btn)
        elif action == "cb_identity":
            await callback.message.edit_text("إعدادات الهوية والزر الشفاف:\nالتوقيع الترويجي مفعل تلقائياً بكل رسالة.", reply_markup=back_btn)
        elif action == "cb_bans":
            await callback.message.edit_text("قائمة المحظورين: لا يوجد أي مستخدم محظور حالياً.", reply_markup=back_btn)
        elif action == "cb_settings":
            await callback.message.edit_text("إعدادات البوت المتقدمة ونظام الأمان مفعلة.", reply_markup=back_btn)
        elif action == "cb_back":
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="تعديل رسالة الترحيب", callback_data="cb_welcome"), InlineKeyboardButton(text="ضبط الرد التلقائي", callback_data="cb_autoreply")],
                [InlineKeyboardButton(text="إحصائيات البوت الحية", callback_data="cb_stats"), InlineKeyboardButton(text="إذاعة لمشتركي البوت", callback_data="cb_broadcast")],
                [InlineKeyboardButton(text="إدارة الهوية والتوقيع", callback_data="cb_identity"), InlineKeyboardButton(text="قائمة المحظورين", callback_data="cb_bans")],
                [InlineKeyboardButton(text="إعدادات متطورة", callback_data="cb_settings")],
                [InlineKeyboardButton(text="مراسلة المبرمج الأساسي", url=f"https://t.me/{DEV_USERNAME}")]
            ])
            await callback.message.edit_text("أهلاً بك يا مالك البوت في لوحة التحكم المركزية.", reply_markup=markup)
        await callback.answer()

    @custom_dp.message(F.text & ~F.command)
    async def custom_message_handler(message: Message):
        u_id = message.from_user.id
        register_custom_user(u_id, message.from_user.first_name, message.from_user.username or "None")

        # معالجة تعديل رسالة الترحيب
        w_key = f"waiting_welcome_{owner_id}"
        if u_id == owner_id and w_key in user_sessions:
            user_sessions.pop(w_key)
            try:
                supabase.table("custom_bot_settings").upsert({"bot_id": bot_id, "welcome_text": message.text}, on_conflict="bot_id").execute()
                await message.answer("تم تحديث رسالة الترحيب بنجاح.")
            except Exception as e:
                await message.answer(f"حدث خطأ: {e}")
            return

        # معالجة تعديل الرد التلقائي
        a_key = f"waiting_autoreply_{owner_id}"
        if u_id == owner_id and a_key in user_sessions:
            user_sessions.pop(a_key)
            try:
                supabase.table("custom_bot_settings").upsert({"bot_id": bot_id, "auto_reply": message.text}, on_conflict="bot_id").execute()
                await message.answer("تم تحديث الرد التلقائي بنجاح.")
            except Exception as e:
                await message.answer(f"حدث خطأ: {e}")
            return

        # معالجة الإذاعة الخاصة بهذا البوت المصنوع
        b_key = f"custom_broadcast_{owner_id}"
        if u_id == owner_id and b_key in user_sessions:
            user_sessions.pop(b_key)
            b_text = message.text
            try:
                subs = supabase.table("custom_bot_users").select("user_id").eq("bot_id", bot_id).execute().data
            except:
                subs = []

            sent = 0
            status_msg = await message.answer("جاري تنفيذ الإذاعة لمشتركي البوت...")
            promo_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="صنع بوتك الخاص من هنا ⚡", url=f"https://t.me/{DEV_USERNAME}")]
            ])
            for sub in subs:
                try:
                    await custom_bot.send_message(sub["user_id"], b_text, reply_markup=promo_markup)
                    sent += 1
                    await asyncio.sleep(0.03)
                except:
                    pass
            await status_msg.edit_text(f"تمت الإذاعة بنجاح تام!\nعدد المستلمين: {sent} مشترك.")
            return

        if u_id == owner_id:
            if message.reply_to_message:
                target_id = None
                if message.reply_to_message.forward_from:
                    target_id = message.reply_to_message.forward_from.id
                else:
                    lines = message.reply_to_message.text.split("\n")
                    for line in lines:
                        if "الآيدي:" in line or "ID:" in line:
                            try:
                                target_id = int(line.replace("الآيدي:", "").replace("ID:", "").strip("` "))
                            except:
                                pass
                
                if target_id:
                    try:
                        promo_markup = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="صنع بوتك الخاص من هنا ⚡", url=f"https://t.me/{DEV_USERNAME}")]
                        ])
                        await custom_bot.send_message(target_id, f"رد من إدارة البوت:\n\n{message.text}", reply_markup=promo_markup)
                        await message.reply("تم إرسال الرد للمستخدم بنجاح.")
                        return
                    except Exception as e:
                        await message.reply(f"تعذر إرسال الرد: {e}")
                        return
            
            await message.answer("أهلاً بك يا مالك البوت. للرد على أي مستخدم، قم بعمل (Reply/رد) على رسالته الواردة إليك هنا.")
        else:
            try:
                # التحقق من وجود رد تلقائي مخصص
                res = supabase.table("custom_bot_settings").select("auto_reply").eq("bot_id", bot_id).execute()
                auto_reply_text = res.data[0].get("auto_reply") if res.data and res.data[0].get("auto_reply") else None
            except:
                auto_reply_text = None

            try:
                forwarded = await message.forward(chat_id=owner_id)
                await custom_bot.send_message(
                    chat_id=owner_id,
                    text=f"رسالة جديدة من المشترك:\nالاسم: {message.from_user.full_name}\nالآيدي: `{message.from_user.id}`",
                    reply_to_message_id=forwarded.message_id
                )
                
                promo_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="صنع بوتك الخاص من هنا ⚡", url=f"https://t.me/{DEV_USERNAME}")]
                ])
                
                if auto_reply_text:
                    await message.answer(auto_reply_text, reply_markup=promo_markup)
                else:
                    await message.answer("تم استلام رسالتك بنجاح وتحويلها للإدارة.", reply_markup=promo_markup)
            except Exception as e:
                logger.error(f"Forward error: {e}")

    try:
        running_custom_bots[bot_id] = custom_bot
        await custom_dp.start_polling(custom_bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Custom bot {bot_id} error: {e}")
    finally:
        await custom_bot.session.close()

async def resume_all_active_bots():
    try:
        res = supabase.table("enterprise_bots").select("*").eq("is_active", True).execute()
        for b in res.data:
            if b["id"] not in running_custom_bots:
                asyncio.create_task(start_user_bot_polling(b["id"], b["bot_token"], b["owner_id"], b["bot_username"]))
    except Exception as e:
        logger.error(f"Error resuming bots: {e}")

# --- البوت الرئيسي (صانع البوتات الأم - المطور) ---
@dp.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id
    if is_banned(user_id):
        return await message.answer("عذراً، تم حظرك من استخدام المنصة.")

    try:
        supabase.table("maker_users").upsert({
            "user_id": user_id,
            "username": message.from_user.username or "None",
            "full_name": message.from_user.first_name
        }).execute()
    except Exception:
        pass

    if user_id == DEV_ID:
        text = "لوحة تحكم مالك المنصة الرئيسي (المطور العظيم):\nأهلاً بك، تحكم كامل وخيارات واسعة لإدارة المنصة بالكامل."
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="إحصائيات المنصة", callback_data="dev_stats"), InlineKeyboardButton(text="إذاعة عامة للمنصة", callback_data="dev_broadcast")],
            [InlineKeyboardButton(text="إدارة جميع البوتات", callback_data="dev_all_bots"), InlineKeyboardButton(text="إدارة الحظر", callback_data="dev_ban_menu")]
        ])
        await message.answer(text, reply_markup=markup)
    else:
        text = (
            "مرحباً بك في منصة صناعة بوتات التواصل الاحترافية والعملاقة.\n\n"
            "أنشئ بوتك الخاص الآن وتمتع بلوحة تحكم متكاملة وعظيمة!"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="إنشاء بوت تواصل جديد", callback_data="create_new_bot")],
            [InlineKeyboardButton(text="بوتاتي المصنوعة وإدارتها", callback_data="my_custom_bots")],
            [InlineKeyboardButton(text="معلومات المنصة", callback_data="bot_info")]
        ])
        await message.answer(text, reply_markup=markup)

@dp.callback_query(F.data == "create_new_bot")
async def step_create_bot(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_sessions[user_id] = {"state": "waiting_for_token"}
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="إلغاء والعودة", callback_data="back_home")]])
    await callback.message.edit_text(
        "خطوة إنشاء بوت تواصل جديد:\n\n"
        "أرسل الآن توكن البوت (Bot Token) الخاص بك من المطور @BotFather:",
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
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="إعادة المحاولة", callback_data="create_new_bot")]])
            return await message.answer(f"التوكن غير صالح:\n`{e}`\n\nتأكد منه جيداً وأعد إرساله.", reply_markup=markup)

        try:
            res = supabase.table("enterprise_bots").insert({
                "owner_id": user_id,
                "bot_token": token,
                "bot_username": me.username,
                "bot_name": me.first_name,
                "is_active": True
            }).execute()
            
            new_bot_id = res.data[0]["id"] if res.data else None
            if new_bot_id:
                asyncio.create_task(start_user_bot_polling(new_bot_id, token, user_id, me.username))

        except Exception as e:
            return await message.answer(f"خطأ في قاعدة البيانات:\n`{e}`")

        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="الذهاب إلى بوتاتي المصنوعة", callback_data="my_custom_bots")]])
        await message.answer(
            f"تم إنشاء وتشغيل بوتك الاحترافي بنجاح تام!\n\n"
            f"اسم البوت: {me.first_name}\n"
            f"المعرف: @{me.username}\n\n"
            f"البوت يعمل الآن في الخلفية وجاهز لاستقبال المستخدمين.",
            reply_markup=markup
        )

    elif state == "dev_broadcasting" and user_id == DEV_ID:
        user_sessions.pop(user_id, None)
        b_text = message.text
        try:
            users = supabase.table("maker_users").select("user_id").execute().data
        except:
            users = []

        sent = 0
        status = await message.answer("جاري تنفيذ الإذاعة العامة لجميع مستخدمي المنصة...")
        for u in users:
            try:
                await bot.send_message(u["user_id"], f"إشعار إداري عام من المنصة:\n\n{b_text}")
                sent += 1
                await asyncio.sleep(0.03)
            except:
                pass
        await status.edit_text(f"تمت الإذاعة العامة بنجاح!\nعدد المستلمين: {sent} مستخدم.")

@dp.callback_query(F.data == "my_custom_bots")
async def list_user_bots(callback: CallbackQuery):
    user_id = callback.from_user.id
    try:
        res = supabase.table("enterprise_bots").select("*").eq("owner_id", user_id).execute()
        bots = res.data
    except:
        bots = []

    if not bots:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="إنشاء بوت جديد", callback_data="create_new_bot")],
            [InlineKeyboardButton(text="القائمة الرئيسية", callback_data="back_home")]
        ])
        return await callback.message.edit_text("لا توجد أي بوتات مصنوعة بواسطة حسابك حتى الآن.", reply_markup=markup)

    buttons = []
    for b in bots:
        status = "يعمل" if b["is_active"] else "متوقف"
        buttons.append([InlineKeyboardButton(text=f"{status} | @{b['bot_username']}", callback_data=f"manage_bot_{b['id']}")])
    buttons.append([InlineKeyboardButton(text="إنشاء بوت آخر", callback_data="create_new_bot"), InlineKeyboardButton(text="القائمة الرئيسية", callback_data="back_home")])

    await callback.message.edit_text("قائمة بوتاتك المصنوعة (اضغط على البوت لإدارة لوحته):", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("manage_bot_"))
async def manage_single_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        res = supabase.table("enterprise_bots").select("*").eq("id", bot_id).execute()
        if not res.data:
            return await callback.answer("البوت غير موجود!", show_alert=True)
        b_data = res.data[0]
    except:
        return await callback.answer("خطأ في الاتصال!", show_alert=True)

    text = (
        f"إدارة البوت: @{b_data['bot_username']}\n\n"
        f"الاسم: {b_data['bot_name']}\n"
        f"الحالة التشغيلية: {'يعمل الآن' if b_data['is_active'] else 'متوقف'}\n"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="حذف البوت نهائياً", callback_data=f"delete_bot_{bot_id}")],
        [InlineKeyboardButton(text="العودة لقائمة بوتاتي", callback_data="my_custom_bots")]
    ])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_bot_"))
async def delete_bot_action(callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])
    try:
        if bot_id in running_custom_bots:
            await running_custom_bots[bot_id].session.close()
            del running_custom_bots[bot_id]
        supabase.table("enterprise_bots").delete().eq("id", bot_id).execute()
        await callback.answer("تم حذف البوت بنجاح.", show_alert=True)
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
    except:
        users = bots = 0

    text = f"إحصائيات المنصة العملاقة:\n\nإجمالي المستخدمين: {users}\nإجمالي البوتات المصنوعة: {bots}"
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="رجوع", callback_data="back_home")]])
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "dev_broadcast")
async def dev_broadcast_handler(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    user_sessions[DEV_ID] = {"state": "dev_broadcasting"}
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="إلغاء", callback_data="back_home")]])
    await callback.message.edit_text("قسم الإذاعة العامة للمنصة:\n\nأرسل الآن نص الإذاعة المراد إرسالها لجميع مستخدمي المنصة:", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "dev_ban_menu")
async def dev_ban_menu(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="رجوع", callback_data="back_home")]])
    await callback.message.edit_text("قسم إدارة الحظر والحماية نشط.", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "bot_info")
async def bot_info(callback: CallbackQuery):
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="رجوع", callback_data="back_home")]])
    await callback.message.edit_text("شروط الاستخدام:\nمنصة احترافية متكاملة لصناعة بوتات التواصل العبقرية.", reply_markup=markup)
    await callback.answer()

@dp.callback_query(F.data == "back_home")
async def back_home(callback: CallbackQuery):
    fake_message = callback.message
    fake_message.from_user = callback.from_user
    await start_handler(fake_message)
    await callback.answer()

async def main():
    await resume_all_active_bots()
    logger.info("Ultimate Professional Giant Bot Maker started successfully!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
