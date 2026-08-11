
import os
import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ForceReply,
)
from aiogram.enums import ChatType
from supabase import create_client, Client as SupabaseClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DEV_ID = int(os.getenv("DEV_ID", "5126968608"))
MAKER_BOT_USERNAME = "fde7Bot"
DEV_USERNAME = "toe7e"

supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_KEY)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_sessions = {}
running_custom_bots = {}

# آخر رسالة لكل مستخدم حتى زر «رد 💬» يفتح نفس الرسالة.
last_user_messages = {}

# يربط رسالة المالك التي تم فتح Reply عليها بالمستخدم الحقيقي.
reply_targets = {}


def is_banned(user_id: int) -> bool:
    try:
        res = (
            supabase.table("maker_bans")
            .select("user_id")
            .eq("user_id", user_id)
            .execute()
        )
        return len(res.data) > 0
    except Exception:
        return False


def get_owner_panel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🤖 إدارة البوت", callback_data="cb_manage"),
                InlineKeyboardButton(text="📊 الإحصائيات", callback_data="cb_stats"),
            ],
            [
                InlineKeyboardButton(text="📨 إذاعة للمستخدمين", callback_data="cb_broadcast"),
                InlineKeyboardButton(text="👥 إدارة المستخدمين", callback_data="cb_users"),
            ],
            [
                InlineKeyboardButton(text="👋 تغيير الترحيب", callback_data="cb_welcome"),
                InlineKeyboardButton(text="💬 الرد التلقائي", callback_data="cb_autoreply"),
            ],
            [
                InlineKeyboardButton(text="🚷 الحظر وفك الحظر", callback_data="cb_bans"),
                InlineKeyboardButton(text="⏸ إيقاف/تشغيل", callback_data="cb_toggle"),
            ],
            [InlineKeyboardButton(text="🗑 حذف البوت نهائياً", callback_data="cb_delete")],
            [
                InlineKeyboardButton(
                    text="✉️ التواصل مع المطور",
                    url=f"https://t.me/{DEV_USERNAME}",
                )
            ],
        ]
    )


async def start_user_bot_polling(
    bot_id: int,
    token: str,
    owner_id: int,
    bot_username: str,
):
    custom_bot = Bot(token=token)
    custom_dp = Dispatcher()

    last_user_messages.setdefault(bot_id, {})

    def register_custom_user(u_id: int, name: str, uname: str):
        try:
            supabase.table("custom_bot_users").upsert(
                {
                    "bot_id": bot_id,
                    "user_id": u_id,
                    "full_name": name,
                    "username": uname,
                },
                on_conflict="bot_id,user_id",
            ).execute()
        except Exception:
            pass

    def is_user_banned(u_id: int) -> bool:
        try:
            res = (
                supabase.table("custom_bot_bans")
                .select("user_id")
                .eq("bot_id", bot_id)
                .eq("user_id", u_id)
                .execute()
            )
            return len(res.data) > 0
        except Exception:
            return False

    @custom_dp.message(Command("start"), F.chat.type == ChatType.PRIVATE)
    async def custom_start(message: Message):
        u_id = message.from_user.id
        uname = message.from_user.username or "None"
        name = message.from_user.first_name or "المستخدم"
        user_display = f"@{uname}" if uname != "None" else name

        if is_user_banned(u_id) and u_id != owner_id:
            return await message.answer("عذراً، تم حظرك من استخدام هذا البوت.")

        register_custom_user(u_id, name, uname)

        if u_id == owner_id:
            await message.answer(
                "⟡ : أهلاً بك أيها المالك في لوحة التحكم الخاصة بوتك . 💜",
                reply_markup=get_owner_panel(),
            )
            return

        try:
            res = (
                supabase.table("custom_bot_settings")
                .select("welcome_text")
                .eq("bot_id", bot_id)
                .execute()
            )
            data = res.data[0] if res.data else {}
            custom_welcome = data.get("welcome_text")

            if custom_welcome:
                welcome_msg = custom_welcome.replace("{name}", name).replace(
                    "{username}", user_display
                )
            else:
                welcome_msg = (
                    f"• اهلا بك ({user_display}) في بوت السايت الخاص بي ❤️\n\n"
                    "- ارسل رسالتك بهويه مجهوله وسوف يرد عليك باقرب وقت 📢"
                )
        except Exception:
            welcome_msg = (
                f"• اهلا بك ({user_display}) في بوت السايت الخاص بي ❤️\n\n"
                "- ارسل رسالتك بهويه مجهوله وسوف يرد عليك باقرب وقت 📢"
            )

        promo_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="صنع بوتك الخاص من هنا ⚡",
                        url=f"https://t.me/{MAKER_BOT_USERNAME}",
                    )
                ]
            ]
        )
        await message.answer(welcome_msg, reply_markup=promo_markup)

    @custom_dp.callback_query(
        F.data.startswith("cb_"),
        F.message.chat.type == ChatType.PRIVATE,
    )
    async def custom_callbacks(callback: CallbackQuery):
        if callback.from_user.id != owner_id:
            return await callback.answer(
                "عذراً، هذه اللوحة خاصة بمالك البوت فقط.",
                show_alert=True,
            )

        action = callback.data
        back_btn = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="العودة للقائمة الرئيسية 🔙",
                        callback_data="cb_back",
                    )
                ]
            ]
        )

        if action == "cb_manage":
            await callback.message.edit_text(
                f"🤖 معلومات وإدارة البوت:\n\n"
                f"- المعرف: @{bot_username}\n"
                f"- الحالة: يعمل بنجاح تامة",
                reply_markup=back_btn,
            )

        elif action == "cb_stats":
            try:
                subs = len(
                    supabase.table("custom_bot_users")
                    .select("user_id")
                    .eq("bot_id", bot_id)
                    .execute()
                    .data
                )
            except Exception:
                subs = 0

            await callback.message.edit_text(
                f"📊 إحصائيات البوت:\n\n- عدد المشتركين: {subs} مشترك",
                reply_markup=back_btn,
            )

        elif action == "cb_broadcast":
            user_sessions[f"custom_broadcast_{owner_id}"] = {
                "bot_id": bot_id,
                "custom_bot": custom_bot,
            }
            await callback.message.edit_text(
                "📨 أرسل الآن رسالة الإذاعة لجميع مشتركي بوتك:",
                reply_markup=back_btn,
            )

        elif action == "cb_users":
            try:
                users = (
                    supabase.table("custom_bot_users")
                    .select("full_name, username, user_id")
                    .eq("bot_id", bot_id)
                    .execute()
                    .data
                )
                u_text = "👥 قائمة المستخدمين:\n\n" + "\n".join(
                    [
                        f"- {u['full_name']} (@{u['username']}) | `{u['user_id']}`"
                        for u in users[:25]
                    ]
                )
            except Exception:
                u_text = "👥 قائمة المستخدمين فارغة."

            await callback.message.edit_text(u_text, reply_markup=back_btn)

        elif action == "cb_welcome":
            user_sessions[f"waiting_welcome_{owner_id}"] = {"bot_id": bot_id}
            await callback.message.edit_text(
                "👋 أرسل النص الجديد لرسالة الترحيب:\n"
                "(ملاحظة: يمكنك استخدام `{name}` لاسم المستخدم أو `{username}` لمعرفه)",
                reply_markup=back_btn,
            )

        elif action == "cb_autoreply":
            user_sessions[f"waiting_autoreply_{owner_id}"] = {"bot_id": bot_id}
            await callback.message.edit_text(
                "💬 أرسل الآن نص الرد التلقائي الجديد للمشتركين:",
                reply_markup=back_btn,
            )

        elif action == "cb_bans":
            user_sessions[f"waiting_ban_{owner_id}"] = {"bot_id": bot_id}
            await callback.message.edit_text(
                "🚷 أرسل (آيدي) المستخدم المراد حظره أو فك حظره:",
                reply_markup=back_btn,
            )

        elif action == "cb_toggle":
            try:
                res = (
                    supabase.table("enterprise_bots")
                    .select("is_active")
                    .eq("id", bot_id)
                    .execute()
                )
                current_state = res.data[0]["is_active"] if res.data else True
                new_state = not current_state
                supabase.table("enterprise_bots").update(
                    {"is_active": new_state}
                ).eq("id", bot_id).execute()
            except Exception:
                pass

            await callback.message.edit_text(
                "حالة البوت الحالية تم تحديثها بنجاح.",
                reply_markup=back_btn,
            )

        elif action == "cb_delete":
            markup_confirm = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="تأكيد الحذف نهائياً 🗑",
                            callback_data=f"confirm_del_{bot_id}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="إلغاء 🔙",
                            callback_data="cb_back",
                        )
                    ],
                ]
            )
            await callback.message.edit_text(
                "⚠️ هل أنت متأكد من رغبتك في حذف البوت نهائياً من قاعدة البيانات؟",
                reply_markup=markup_confirm,
            )

        elif action == "cb_back":
            await callback.message.edit_text(
                "⟡ : أهلاً بك أيها المالك في لوحة التحكم الخاصة بوتك . 💜",
                reply_markup=get_owner_panel(),
            )

        await callback.answer()

    @custom_dp.callback_query(
        F.data.startswith("confirm_del_"),
        F.message.chat.type == ChatType.PRIVATE,
    )
    async def confirm_delete_bot(callback: CallbackQuery):
        if callback.from_user.id != owner_id:
            return await callback.answer("للمالك فقط", show_alert=True)

        b_id = int(callback.data.split("_")[2])

        try:
            supabase.table("enterprise_bots").delete().eq("id", b_id).execute()

            if b_id in running_custom_bots:
                try:
                    await running_custom_bots[b_id].session.close()
                except Exception:
                    pass
                del running_custom_bots[b_id]

            last_user_messages.pop(b_id, None)

            for key in list(reply_targets):
                if key[0] == b_id:
                    reply_targets.pop(key, None)

            await callback.message.edit_text("🗑 تم حذف البوت نهائياً بنجاح.")
        except Exception as e:
            await callback.answer(f"خطأ: {e}", show_alert=True)

    @custom_dp.callback_query(
        F.data.startswith("reply_user_"),
        F.message.chat.type == ChatType.PRIVATE,
    )
    async def inline_reply_prompt(callback: CallbackQuery):
        if callback.from_user.id != owner_id:
            return await callback.answer("للمالك فقط", show_alert=True)

        target_id = int(callback.data.split("_")[2])
        original_message_id = last_user_messages.get(bot_id, {}).get(target_id)

        if not original_message_id:
            return await callback.answer(
                "تعذر العثور على رسالة المستخدم الأخيرة.",
                show_alert=True,
            )

        try:
            copied = await custom_bot.copy_message(
                chat_id=owner_id,
                from_chat_id=target_id,
                message_id=original_message_id,
                reply_markup=ForceReply(
                    force_reply=True,
                    selective=True,
                ),
            )

            reply_targets[(bot_id, owner_id, copied.message_id)] = target_id

            await callback.answer(
                "✍️ اكتب ردك الآن، وسيتم إرساله للمستخدم.",
                show_alert=False,
            )
        except Exception as e:
            logger.exception("Failed to prepare native reply")
            await callback.answer(
                f"تعذر فتح الرد: {e}",
                show_alert=True,
            )

    @custom_dp.callback_query(
        F.data.startswith("ban_user_"),
        F.message.chat.type == ChatType.PRIVATE,
    )
    async def inline_ban_action(callback: CallbackQuery):
        if callback.from_user.id != owner_id:
            return await callback.answer("للمالك فقط", show_alert=True)

        target_id = int(callback.data.split("_")[2])

        try:
            res = (
                supabase.table("custom_bot_bans")
                .select("user_id")
                .eq("bot_id", bot_id)
                .eq("user_id", target_id)
                .execute()
            )

            if len(res.data) > 0:
                supabase.table("custom_bot_bans").delete().eq(
                    "bot_id", bot_id
                ).eq("user_id", target_id).execute()

                await callback.answer(
                    f"✅ تم فك الحظر عن المستخدم: {target_id}",
                    show_alert=True,
                )
            else:
                supabase.table("custom_bot_bans").insert(
                    {"bot_id": bot_id, "user_id": target_id}
                ).execute()

                await callback.answer(
                    f"🚷 تم حظر المستخدم بنجاح: {target_id}",
                    show_alert=True,
                )
        except Exception as e:
            await callback.answer(f"خطأ: {e}", show_alert=True)

    @custom_dp.message(F.chat.type == ChatType.PRIVATE)
    async def custom_message_handler(message: Message):
        u_id = message.from_user.id
        uname = message.from_user.username or "None"
        name = message.from_user.first_name or "المستخدم"

        # =========================
        # المالك: لا نعتبر رسالته رسالة مشترك.
        # =========================
        if u_id == owner_id:
            # الرد من شريط Telegram Reply على الرسالة التي فتحها زر «رد 💬».
            if message.reply_to_message:
                target_id = reply_targets.get(
                    (bot_id, owner_id, message.reply_to_message.message_id)
                )

                if target_id:
                    try:
                        await custom_bot.copy_message(
                            chat_id=target_id,
                            from_chat_id=owner_id,
                            message_id=message.message_id,
                        )

                        reply_targets.pop(
                            (bot_id, owner_id, message.reply_to_message.message_id),
                            None,
                        )

                        await message.answer("✅ تم إرسال الرد للمستخدم بنجاح.")
                        return
                    except Exception as e:
                        await message.answer(
                            f"❌ تعذر إرسال الرد للمستخدم:\n{e}"
                        )
                        return

            if f"waiting_welcome_{owner_id}" in user_sessions and message.text:
                user_sessions.pop(f"waiting_welcome_{owner_id}")
                try:
                    supabase.table("custom_bot_settings").upsert(
                        {"bot_id": bot_id, "welcome_text": message.text},
                        on_conflict="bot_id",
                    ).execute()
                    await message.answer("✅ تم تحديث وحفظ رسالة الترحيب بنجاح.")
                except Exception as e:
                    await message.answer(f"خطأ: {e}")
                return

            if f"waiting_autoreply_{owner_id}" in user_sessions and message.text:
                user_sessions.pop(f"waiting_autoreply_{owner_id}")
                try:
                    supabase.table("custom_bot_settings").upsert(
                        {"bot_id": bot_id, "auto_reply": message.text},
                        on_conflict="bot_id",
                    ).execute()
                    await message.answer("✅ تم تحديث وحفظ الرد التلقائي بنجاح.")
                except Exception as e:
                    await message.answer(f"خطأ: {e}")
                return

            if f"waiting_ban_{owner_id}" in user_sessions and message.text:
                user_sessions.pop(f"waiting_ban_{owner_id}")
                try:
                    target_id = int(message.text.strip())
                    res = (
                        supabase.table("custom_bot_bans")
                        .select("user_id")
                        .eq("bot_id", bot_id)
                        .eq("user_id", target_id)
                        .execute()
                    )

                    if len(res.data) > 0:
                        supabase.table("custom_bot_bans").delete().eq(
                            "bot_id", bot_id
                        ).eq("user_id", target_id).execute()
                        await message.answer(
                            f"✅ تم فك الحظر عن المستخدم: `{target_id}`"
                        )
                    else:
                        supabase.table("custom_bot_bans").insert(
                            {"bot_id": bot_id, "user_id": target_id}
                        ).execute()
                        await message.answer(
                            f"🚷 تم حظر المستخدم بنجاح: `{target_id}`"
                        )
                except Exception as e:
                    await message.answer(f"خطأ في الآيدي المدخل: {e}")
                return

            if f"custom_broadcast_{owner_id}" in user_sessions:
                if not message.text:
                    return await message.answer(
                        "📨 الإذاعة الحالية تقبل النص فقط."
                    )

                user_sessions.pop(f"custom_broadcast_{owner_id}")
                b_text = message.text

                try:
                    subs = (
                        supabase.table("custom_bot_users")
                        .select("user_id")
                        .eq("bot_id", bot_id)
                        .execute()
                        .data
                    )
                except Exception:
                    subs = []

                sent = 0
                status_msg = await message.answer(
                    "📨 جاري إرسال الإذاعة لمشتركي بوتك..."
                )

                for sub in subs:
                    try:
                        await custom_bot.send_message(sub["user_id"], b_text)
                        sent += 1
                        await asyncio.sleep(0.03)
                    except Exception:
                        pass

                await status_msg.edit_text(
                    f"✅ تمت الإذاعة بنجاح!\nعدد المستلمين: {sent} مشترك."
                )
                return

            await message.answer(
                "👋 أنت مالك البوت.\n\n"
                "للرد على المشترك: اضغط زر «رد 💬» أسفل رسالته، "
                "ثم اكتب الرد من شريط Reply."
            )
            return

        # =========================
        # المستخدمون: الخاص فقط.
        # =========================
        if is_user_banned(u_id):
            return

        register_custom_user(u_id, name, uname)

        # نحفظ آخر رسالة حتى زر «رد 💬» يفتحها نفسها.
        last_user_messages[bot_id][u_id] = message.message_id

        try:
            res_s = (
                supabase.table("custom_bot_settings")
                .select("auto_reply")
                .eq("bot_id", bot_id)
                .execute()
            )
            data_s = res_s.data[0] if res_s.data else {}
            auto_reply = data_s.get("auto_reply") or "اهلا حبيب شوي و ارد 🌷."
        except Exception:
            auto_reply = "اهلا حبيب شوي و ارد 🌷."

        # نسخة من رسالة المستخدم إلى المالك.
        try:
            await custom_bot.copy_message(
                chat_id=owner_id,
                from_chat_id=u_id,
                message_id=message.message_id,
            )
        except Exception as e:
            logger.error(
                f"Failed to copy user message to owner "
                f"(bot={bot_id}, user={u_id}): {e}"
            )

        info_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="رد 💬",
                        callback_data=f"reply_user_{u_id}",
                    ),
                    InlineKeyboardButton(
                        text="حظر 🚷",
                        callback_data=f"ban_user_{u_id}",
                    ),
                ]
            ]
        )

        await custom_bot.send_message(
            chat_id=owner_id,
            text=(
                f"👤 معلومات المشترك:\n"
                f"- الاسم: {name}\n"
                f"- المعرف: @{uname}\n"
                f"- الآيدي: `{u_id}`"
            ),
            reply_markup=info_markup,
        )

        promo_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="صنع بوتك الخاص من هنا ⚡",
                        url=f"https://t.me/{MAKER_BOT_USERNAME}",
                    )
                ]
            ]
        )

        await message.answer(auto_reply, reply_markup=promo_markup)

    try:
        running_custom_bots[bot_id] = custom_bot
        await custom_dp.start_polling(custom_bot, skip_updates=True)
    except Exception as e:
        logger.error(f"Custom bot {bot_id} error: {e}")
    finally:
        await custom_bot.session.close()
        running_custom_bots.pop(bot_id, None)


async def resume_all_active_bots():
    try:
        res = (
            supabase.table("enterprise_bots")
            .select("*")
            .eq("is_active", True)
            .execute()
        )
        for b in res.data:
            if b["id"] not in running_custom_bots:
                asyncio.create_task(
                    start_user_bot_polling(
                        b["id"],
                        b["bot_token"],
                        b["owner_id"],
                        b["bot_username"],
                    )
                )
    except Exception as e:
        logger.error(f"Error resuming bots: {e}")


@dp.message(Command("start"))
async def start_handler(message: Message):
    user_id = message.from_user.id

    if is_banned(user_id):
        return await message.answer("عذراً، تم حظرك من استخدام المنصة.")

    try:
        supabase.table("maker_users").upsert(
            {
                "user_id": user_id,
                "username": message.from_user.username or "None",
                "full_name": message.from_user.first_name,
            }
        ).execute()
    except Exception:
        pass

    if user_id == DEV_ID:
        text = (
            "⚙️ لوحة تحكم مالك المنصة الرئيسي (المطور):\n"
            "أهلاً بك، تحكم كامل وخيارات واسعة لإدارة المنصة."
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 إحصائيات المنصة",
                        callback_data="dev_stats",
                    ),
                    InlineKeyboardButton(
                        text="📨 إذاعة عامة",
                        callback_data="dev_broadcast",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🤖 إدارة البوتات",
                        callback_data="dev_all_bots",
                    ),
                    InlineKeyboardButton(
                        text="🚷 إدارة الحظر",
                        callback_data="dev_ban_menu",
                    ),
                ],
            ]
        )
        await message.answer(text, reply_markup=markup)
    else:
        name = message.from_user.first_name
        text = (
            f"• اهلا بك ({name}) .\n"
            "• في البوت الرسمي لصنع بوتات السايت ، 📌\n"
            "• يحتوي البوت الذي يتم صنعه على مميزات متميزة وسرعة عاليةه "
            "ويتميز بعدم توقف البوت مدى الحياة ، 📢\n\n"
            "---------------------------------\n\n"
            f"🤖 عجبك البوت؟ اصنع بوتك الخاص مجاناً!\n@{MAKER_BOT_USERNAME}"
        )
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🤖 صنع بوت جديد", callback_data="create_new_bot")],
                [InlineKeyboardButton(text="📋 قائمة بوتاتك", callback_data="my_custom_bots")],
                [InlineKeyboardButton(text="❓ كيف اصنع بوت؟", callback_data="bot_info")],
                [InlineKeyboardButton(text="🌐 Change Language | تغيير اللغة", callback_data="change_lang")],
            ]
        )
        await message.answer(text, reply_markup=markup)


@dp.callback_query(F.data == "create_new_bot")
async def step_create_bot(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_sessions[user_id] = {"state": "waiting_for_token"}

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="إلغاء والعودة 🔙",
                    callback_data="back_home",
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "خطوة إنشاء بوت تواصل جديد:\n\n"
        "أرسل الآن توكن البوت (Bot Token) الخاص بك من المطور @BotFather:",
        reply_markup=markup,
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
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="إعادة المحاولة",
                            callback_data="create_new_bot",
                        )
                    ]
                ]
            )
            return await message.answer(
                f"التوكن غير صالح:\n`{e}`\n\nتأكد منه جيداً وأعد إرساله.",
                reply_markup=markup,
            )

        try:
            res = (
                supabase.table("enterprise_bots")
                .insert(
                    {
                        "owner_id": user_id,
                        "bot_token": token,
                        "bot_username": me.username,
                        "bot_name": me.first_name,
                        "is_active": True,
                    }
                )
                .execute()
            )

            new_bot_id = res.data[0]["id"] if res.data else None
            if new_bot_id:
                asyncio.create_task(
                    start_user_bot_polling(
                        new_bot_id,
                        token,
                        user_id,
                        me.username,
                    )
                )
        except Exception as e:
            return await message.answer(
                f"خطأ في قاعدة البيانات:\n`{e}`"
            )

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="الذهاب إلى قائمة بوتاتك 📋",
                        callback_data="my_custom_bots",
                    )
                ]
            ]
        )

        await message.answer(
            f"تم إنشاء وتشغيل بوتك الاحترافي بنجاح تام!\n\n"
            f"اسم البوت: {me.first_name}\n"
            f"المعرف: @{me.username}",
            reply_markup=markup,
        )

    elif state == "dev_broadcasting" and user_id == DEV_ID:
        user_sessions.pop(user_id, None)
        b_text = message.text

        try:
            users = supabase.table("maker_users").select("user_id").execute().data
        except Exception:
            users = []

        sent = 0
        status = await message.answer(
            "جاري تنفيذ الإذاعة العامة لجميع مستخدمي المنصة..."
        )

        for u in users:
            try:
                await bot.send_message(
                    u["user_id"],
                    f"إشعار إداري عام من المنصة:\n\n{b_text}",
                )
                sent += 1
                await asyncio.sleep(0.03)
            except Exception:
                pass

        await status.edit_text(
            f"تمت الإذاعة العامة بنجاح!\nعدد المستلمين: {sent} مستخدم."
        )


@dp.callback_query(F.data == "my_custom_bots")
async def list_user_bots(callback: CallbackQuery):
    user_id = callback.from_user.id

    try:
        res = (
            supabase.table("enterprise_bots")
            .select("*")
            .eq("owner_id", user_id)
            .execute()
        )
        bots = res.data
    except Exception:
        bots = []

    if not bots:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🤖 صنع بوت جديد",
                        callback_data="create_new_bot",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="القائمة الرئيسية 🔙",
                        callback_data="back_home",
                    )
                ],
            ]
        )
        return await callback.message.edit_text(
            "لا توجد أي بوتات مصنوعة بواسطة حسابك حتى الآن.",
            reply_markup=markup,
        )

    buttons = []
    for b in bots:
        status = "يعمل 🟢" if b["is_active"] else "متوقف ⏸"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{status} | @{b['bot_username']}",
                    callback_data=f"manage_bot_{b['id']}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🤖 صنع بوت آخر",
                callback_data="create_new_bot",
            ),
            InlineKeyboardButton(
                text="القائمة الرئيسية 🔙",
                callback_data="back_home",
            ),
        ]
    )

    await callback.message.edit_text(
        "📋 قائمة بوتاتك المصنوعة والإدارة الكاملة:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("manage_bot_"))
async def manage_single_bot(callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])

    try:
        res = (
            supabase.table("enterprise_bots")
            .select("*")
            .eq("id", bot_id)
            .execute()
        )
        if not res.data:
            return await callback.answer("البوت غير موجود!", show_alert=True)
        b_data = res.data[0]
    except Exception:
        return await callback.answer("خطأ في الاتصال!", show_alert=True)

    text = (
        f"🤖 إدارة البوت: @{b_data['bot_username']}\n\n"
        f"الاسم: {b_data['bot_name']}\n"
        f"الحالة: {'يعمل 🟢' if b_data['is_active'] else 'متوقف ⏸'}\n"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 حذف البوت نهائياً",
                    callback_data=f"delete_bot_{bot_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="العودة لقائمة بوتاتي 🔙",
                    callback_data="my_custom_bots",
                )
            ],
        ]
    )

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data.startswith("delete_bot_"))
async def delete_bot_action(callback: CallbackQuery):
    bot_id = int(callback.data.split("_")[2])

    try:
        if bot_id in running_custom_bots:
            try:
                await running_custom_bots[bot_id].session.close()
            except Exception:
                pass
            del running_custom_bots[bot_id]

        supabase.table("enterprise_bots").delete().eq("id", bot_id).execute()
        last_user_messages.pop(bot_id, None)

        for key in list(reply_targets):
            if key[0] == bot_id:
                reply_targets.pop(key, None)

        await callback.answer("تم حذف البوت بنجاح.", show_alert=True)
        await list_user_bots(callback)
    except Exception as e:
        await callback.answer(f"خطأ: {e}", show_alert=True)


@dp.callback_query(F.data == "dev_all_bots")
async def dev_all_bots_handler(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return

    try:
        res = supabase.table("enterprise_bots").select("*").execute()
        bots = res.data
    except Exception:
        bots = []

    if not bots:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="رجوع 🔙", callback_data="back_home")]
            ]
        )
        return await callback.message.edit_text(
            "لا توجد بوتات مسجلة في المنصة حالياً.",
            reply_markup=markup,
        )

    buttons = []
    for b in bots[:20]:
        status = "🟢" if b["is_active"] else "⏸"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{status} @{b['bot_username']} (Owner: {b['owner_id']})",
                    callback_data=f"dev_del_bot_{b['id']}",
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(text="رجوع 🔙", callback_data="back_home")]
    )

    await callback.message.edit_text(
        "🤖 إدارات جميع بوتات المنصة (اضغط لحذف البوت كأدمن):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("dev_del_bot_"))
async def dev_del_bot_action(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return

    bot_id = int(callback.data.split("_")[3])

    try:
        if bot_id in running_custom_bots:
            try:
                await running_custom_bots[bot_id].session.close()
            except Exception:
                pass
            del running_custom_bots[bot_id]

        supabase.table("enterprise_bots").delete().eq("id", bot_id).execute()
        last_user_messages.pop(bot_id, None)

        for key in list(reply_targets):
            if key[0] == bot_id:
                reply_targets.pop(key, None)

        await callback.answer(
            "تم حذف البوت من المنصة بنجاح.",
            show_alert=True,
        )
        await dev_all_bots_handler(callback)
    except Exception as e:
        await callback.answer(f"خطأ: {e}", show_alert=True)


@dp.callback_query(F.data == "dev_stats")
async def dev_stats_handler(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return

    try:
        users = len(
            supabase.table("maker_users").select("user_id").execute().data
        )
        bots = len(
            supabase.table("enterprise_bots").select("id").execute().data
        )
    except Exception:
        users = bots = 0

    text = (
        f"📊 إحصائيات المنصة الشاملة:\n\n"
        f"- إجمالي المستخدمين: {users}\n"
        f"- إجمالي البوتات المصنوعة: {bots}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="رجوع 🔙", callback_data="back_home")]
        ]
    )

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@dp.callback_query(F.data == "dev_broadcast")
async def dev_broadcast_handler(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return

    user_sessions[DEV_ID] = {"state": "dev_broadcasting"}

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="إلغاء 🔙", callback_data="back_home")]
        ]
    )

    await callback.message.edit_text(
        "📨 أرسل الآن نص الإذاعة العامة لجميع مستخدمي المنصة:",
        reply_markup=markup,
    )
    await callback.answer()


@dp.callback_query(F.data == "dev_ban_menu")
async def dev_ban_menu(callback: CallbackQuery):
    if callback.from_user.id != DEV_ID:
        return

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="رجوع 🔙", callback_data="back_home")]
        ]
    )

    await callback.message.edit_text(
        "🚷 إدارة الحظر العامة للمنصة نشطة ومؤمنة.",
        reply_markup=markup,
    )
    await callback.answer()


@dp.callback_query(F.data == "bot_info")
async def bot_info(callback: CallbackQuery):
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="رجوع 🔙", callback_data="back_home")]
        ]
    )

    await callback.message.edit_text(
        "• هذه المنصة مخصصة لصناعة بوتات التواصل الاحترافية والسايت "
        "بسرعة عالية واستقرار تام مدى الحياة ⚡",
        reply_markup=markup,
    )
    await callback.answer()


@dp.callback_query(F.data == "change_lang")
async def change_lang(callback: CallbackQuery):
    await callback.answer(
        "اللغة الحالية هي العربية 🇮🇶",
        show_alert=True,
    )


@dp.callback_query(F.data == "back_home")
async def back_home(callback: CallbackQuery):
    fake_message = callback.message
    fake_message.from_user = callback.from_user
    await start_handler(fake_message)
    await callback.answer()


async def main():
    await resume_all_active_bots()
    logger.info("Ultimate Production Bot Maker started successfully!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
