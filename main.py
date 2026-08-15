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
)
from aiogram.enums import ChatType

from supabase import create_client, Client as SupabaseClient


# =========================================================
# الإعدادات
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

DEV_ID = int(os.getenv("DEV_ID", "5126968608"))

MAKER_BOT_USERNAME = "fde7Bot"
DEV_USERNAME = "toe7e"


# =========================================================
# الاتصال
# =========================================================

supabase: SupabaseClient = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# التخزين المؤقت
# =========================================================

user_sessions = {}

# البوتات التي تعمل حالياً
running_custom_bots = {}

# ربط رسالة المستخدم المنسوخة عند المالك بالمستخدم الحقيقي
#
# المفتاح:
# (bot_id, owner_id, owner_message_id)
#
# القيمة:
# user_id
#
# بهذه الطريقة عندما يضغط المالك Reply على رسالة المشترك
# نعرف إلى أي مستخدم يجب إرسال الرد.
reply_targets = {}


# =========================================================
# أدوات عامة
# =========================================================

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
    """
    لوحة تحكم صاحب البوت.
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤖 إدارة البوت",
                    callback_data="cb_manage"
                ),
                InlineKeyboardButton(
                    text="📊 الإحصائيات",
                    callback_data="cb_stats"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📨 إذاعة للمستخدمين",
                    callback_data="cb_broadcast"
                ),
                InlineKeyboardButton(
                    text="👥 إدارة المستخدمين",
                    callback_data="cb_users"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👋 تغيير الترحيب",
                    callback_data="cb_welcome"
                ),
                InlineKeyboardButton(
                    text="💬 الرد التلقائي",
                    callback_data="cb_autoreply"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🚷 الحظر وفك الحظر",
                    callback_data="cb_bans"
                ),
                InlineKeyboardButton(
                    text="⏸ إيقاف/تشغيل",
                    callback_data="cb_toggle"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 حذف البوت نهائياً",
                    callback_data="cb_delete"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✉️ التواصل مع المطور",
                    url=f"https://t.me/{DEV_USERNAME}"
                )
            ],
        ]
    )


def get_back_button(callback_data="cb_back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="العودة للقائمة الرئيسية 🔙",
                    callback_data=callback_data
                )
            ]
        ]
    )


def get_main_menu(user_id: int) -> InlineKeyboardMarkup:

    if user_id == DEV_ID:

        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 إحصائيات المنصة",
                        callback_data="dev_stats"
                    ),
                    InlineKeyboardButton(
                        text="📨 إذاعة عامة",
                        callback_data="dev_broadcast"
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text="🤖 إدارة البوتات",
                        callback_data="dev_all_bots"
                    ),
                    InlineKeyboardButton(
                        text="🚷 إدارة الحظر",
                        callback_data="dev_ban_menu"
                    ),
                ],
            ]
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤖 صنع بوت جديد",
                    callback_data="create_new_bot"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📋 قائمة بوتاتك",
                    callback_data="my_custom_bots"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ كيفية صنع بوت",
                    callback_data="bot_info"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Change Language | تغيير اللغة",
                    callback_data="change_lang"
                )
            ],
        ]
    )


# =========================================================
# تشغيل البوت المصنوع
# =========================================================

async def start_user_bot_polling(
    bot_id: int,
    token: str,
    owner_id: int,
    bot_username: str,
):

    custom_bot = Bot(token=token)
    custom_dp = Dispatcher()

    # =====================================================
    # تسجيل المستخدم
    # =====================================================

    def register_custom_user(
        u_id: int,
        name: str,
        uname: str
    ):

        try:

            supabase.table(
                "custom_bot_users"
            ).upsert(
                {
                    "bot_id": bot_id,
                    "user_id": u_id,
                    "full_name": name,
                    "username": uname,
                },
                on_conflict="bot_id,user_id"
            ).execute()

        except Exception:
            pass

    # =====================================================
    # فحص حظر مستخدم داخل البوت
    # =====================================================

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

    # =====================================================
    # /start للبوت المصنوع
    # =====================================================

    @custom_dp.message(
        Command("start"),
        F.chat.type == ChatType.PRIVATE
    )
    async def custom_start(message: Message):

        u_id = message.from_user.id

        uname = (
            message.from_user.username
            or "None"
        )

        name = (
            message.from_user.first_name
            or "المستخدم"
        )

        user_display = (
            f"@{uname}"
            if uname != "None"
            else name
        )

        # فحص الحظر
        if is_user_banned(u_id) and u_id != owner_id:
            return await message.answer(
                "عذراً، تم حظرك من استخدام هذا البوت."
            )

        # تسجيل المستخدم
        register_custom_user(
            u_id,
            name,
            uname
        )

        # =================================================
        # إذا كان صاحب البوت
        # =================================================

        if u_id == owner_id:

            await message.answer(
                "⟡ أهلاً بك أيها المالك في لوحة التحكم الخاصة ببوتك 💜",
                reply_markup=get_owner_panel()
            )

            return

        # =================================================
        # جلب الترحيب
        # =================================================

        try:

            res = (
                supabase.table(
                    "custom_bot_settings"
                )
                .select("welcome_text")
                .eq("bot_id", bot_id)
                .execute()
            )

            data = (
                res.data[0]
                if res.data
                else {}
            )

            custom_welcome = data.get(
                "welcome_text"
            )

            if custom_welcome:

                welcome_msg = (
                    custom_welcome
                    .replace("{name}", name)
                    .replace("{username}", user_display)
                )

            else:

                welcome_msg = (
                    f"• اهلا بك ({user_display}) في بوت السايت الخاص بي ❤️\n\n"
                    "• ارسل رسالتك بهوية مجهولة وسوف يرد عليك بأقرب وقت 📢"
                )

        except Exception:

            welcome_msg = (
                f"• اهلا بك ({user_display}) في بوت السايت الخاص بي ❤️\n\n"
                "• ارسل رسالتك بهوية مجهولة وسوف يرد عليك بأقرب وقت 📢"
            )

        # =================================================
        # زر الصانع
        # =================================================

        promo_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🤖 صنع بوتك الخاص من هنا ⚡",
                        url=f"https://t.me/{MAKER_BOT_USERNAME}"
                    )
                ]
            ]
        )

        await message.answer(
            welcome_msg,
            reply_markup=promo_markup
        )

    # =====================================================
    # لوحة تحكم صاحب البوت
    # =====================================================

    @custom_dp.callback_query(
        F.data.startswith("cb_"),
        F.message.chat.type == ChatType.PRIVATE
    )
    async def custom_callbacks(
        callback: CallbackQuery
    ):

        # المالك فقط
        if callback.from_user.id != owner_id:

            return await callback.answer(
                "عذراً، هذه اللوحة خاصة بمالك البوت فقط.",
                show_alert=True
            )

        action = callback.data

        back_btn = get_back_button()

        # =================================================
        # إدارة البوت
        # =================================================

        if action == "cb_manage":

            try:

                res = (
                    supabase.table("enterprise_bots")
                    .select("is_active")
                    .eq("id", bot_id)
                    .execute()
                )

                active = (
                    res.data[0]["is_active"]
                    if res.data
                    else True
                )

            except Exception:
                active = True

            await callback.message.edit_text(
                "🤖 إدارة البوت\n\n"
                f"• المعرف: @{bot_username}\n"
                f"• الحالة: {'🟢 يعمل' if active else '⏸ متوقف'}\n\n"
                "يمكنك التحكم بالترحيب والرد التلقائي "
                "والمستخدمين والإذاعة من القائمة الرئيسية.",
                reply_markup=back_btn
            )

        # =================================================
        # الإحصائيات
        # =================================================

        elif action == "cb_stats":

            try:

                users = (
                    supabase.table("custom_bot_users")
                    .select("user_id")
                    .eq("bot_id", bot_id)
                    .execute()
                    .data
                )

                subscribers = len(users)

            except Exception:

                subscribers = 0

            await callback.message.edit_text(
                "📊 إحصائيات البوت\n\n"
                f"👥 عدد المشتركين: {subscribers}\n"
                f"🤖 البوت: @{bot_username}\n"
                "🟢 النظام: يعمل",
                reply_markup=back_btn
            )

        # =================================================
        # الإذاعة
        # =================================================

        elif action == "cb_broadcast":

            user_sessions[
                f"custom_broadcast_{owner_id}"
            ] = {
                "bot_id": bot_id,
                "custom_bot": custom_bot
            }

            await callback.message.edit_text(
                "📨 إذاعة للمستخدمين\n\n"
                "أرسل الآن الرسالة التي تريد إرسالها "
                "إلى مشتركي بوتك.",
                reply_markup=back_btn
            )

        # =================================================
        # إدارة المستخدمين
        # =================================================

        elif action == "cb_users":

            try:

                users = (
                    supabase.table("custom_bot_users")
                    .select(
                        "full_name, username, user_id"
                    )
                    .eq("bot_id", bot_id)
                    .execute()
                    .data
                )

            except Exception:

                users = []

            if not users:

                text = (
                    "👥 إدارة المستخدمين\n\n"
                    "لا يوجد مستخدمون مسجلون حالياً."
                )

            else:

                lines = [
                    "👥 إدارة المستخدمين\n"
                ]

                for index, user in enumerate(
                    users[:25],
                    start=1
                ):

                    name = user.get(
                        "full_name"
                    ) or "غير معروف"

                    username = user.get(
                        "username"
                    ) or "None"

                    uid = user.get(
                        "user_id"
                    )

                    if username != "None":

                        lines.append(
                            f"{index}. {name} | @{username}\n"
                            f"   ID: {uid}"
                        )

                    else:

                        lines.append(
                            f"{index}. {name}\n"
                            f"   ID: {uid}"
                        )

                if len(users) > 25:

                    lines.append(
                        "\n... يتم عرض أول 25 مستخدم فقط."
                    )

                text = "\n".join(lines)

            await callback.message.edit_text(
                text,
                reply_markup=back_btn
            )

        # =================================================
        # تغيير الترحيب
        # =================================================

        elif action == "cb_welcome":

            user_sessions[
                f"waiting_welcome_{owner_id}"
            ] = {
                "bot_id": bot_id
            }

            await callback.message.edit_text(
                "👋 تغيير الترحيب\n\n"
                "أرسل الآن رسالة الترحيب الجديدة.\n\n"
                "يمكنك استخدام:\n"
                "{name} = اسم المستخدم\n"
                "{username} = معرف المستخدم",
                reply_markup=back_btn
            )

        # =================================================
        # الرد التلقائي
        # =================================================

        elif action == "cb_autoreply":

            user_sessions[
                f"waiting_autoreply_{owner_id}"
            ] = {
                "bot_id": bot_id
            }

            await callback.message.edit_text(
                "💬 الرد التلقائي\n\n"
                "أرسل الآن نص الرد التلقائي "
                "الذي سيظهر للمستخدم بعد إرسال رسالته.",
                reply_markup=back_btn
            )

        # =================================================
        # الحظر
        # =================================================

        elif action == "cb_bans":

            user_sessions[
                f"waiting_ban_{owner_id}"
            ] = {
                "bot_id": bot_id
            }

            await callback.message.edit_text(
                "🚷 الحظر وفك الحظر\n\n"
                "أرسل آيدي المستخدم.\n\n"
                "إذا كان محظوراً سيتم فك الحظر عنه، "
                "وإذا لم يكن محظوراً سيتم حظره.",
                reply_markup=back_btn
            )

        # =================================================
        # تشغيل / إيقاف
        # =================================================

        elif action == "cb_toggle":

            try:

                res = (
                    supabase.table("enterprise_bots")
                    .select("is_active")
                    .eq("id", bot_id)
                    .execute()
                )

                current_state = (
                    res.data[0]["is_active"]
                    if res.data
                    else True
                )

                new_state = not current_state

                (
                    supabase.table("enterprise_bots")
                    .update(
                        {
                            "is_active": new_state
                        }
                    )
                    .eq("id", bot_id)
                    .execute()
                )

                status = (
                    "🟢 يعمل"
                    if new_state
                    else "⏸ متوقف"
                )

            except Exception:

                status = "تعذر تحديث الحالة."

            await callback.message.edit_text(
                "⏸ تشغيل / إيقاف البوت\n\n"
                f"الحالة الحالية: {status}",
                reply_markup=back_btn
            )

        # =================================================
        # حذف البوت
        # =================================================

        elif action == "cb_delete":

            markup_confirm = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🗑 تأكيد الحذف نهائياً",
                            callback_data=f"confirm_del_{bot_id}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="إلغاء 🔙",
                            callback_data="cb_back"
                        )
                    ]
                ]
            )

            await callback.message.edit_text(
                "⚠️ حذف البوت\n\n"
                "هل أنت متأكد من حذف البوت نهائياً؟\n\n"
                "سيتم حذف تسجيله من المنصة.",
                reply_markup=markup_confirm
            )

        # =================================================
        # رجوع
        # =================================================

        elif action == "cb_back":

            await callback.message.edit_text(
                "⟡ أهلاً بك أيها المالك في لوحة التحكم الخاصة ببوتك 💜",
                reply_markup=get_owner_panel()
            )

        await callback.answer()

    # =====================================================
    # تأكيد حذف البوت
    # =====================================================

    @custom_dp.callback_query(
        F.data.startswith("confirm_del_"),
        F.message.chat.type == ChatType.PRIVATE
    )
    async def confirm_delete_bot(
        callback: CallbackQuery
    ):

        if callback.from_user.id != owner_id:

            return await callback.answer(
                "للمالك فقط",
                show_alert=True
            )

        b_id = int(
            callback.data.split("_")[2]
        )

        try:

            (
                supabase.table("enterprise_bots")
                .delete()
                .eq("id", b_id)
                .execute()
            )

            if b_id in running_custom_bots:

                try:
                    await running_custom_bots[
                        b_id
                    ].session.close()

                except Exception:
                    pass

                del running_custom_bots[b_id]

            # حذف روابط الرد
            for key in list(reply_targets):

                if key[0] == b_id:

                    reply_targets.pop(
                        key,
                        None
                    )

            await callback.message.edit_text(
                "🗑 تم حذف البوت نهائياً بنجاح."
            )

        except Exception as e:

            await callback.answer(
                f"خطأ: {e}",
                show_alert=True
            )

    # =====================================================
    # حظر / فك حظر من زر المعلومات
    # =====================================================

    @custom_dp.callback_query(
        F.data.startswith("ban_user_"),
        F.message.chat.type == ChatType.PRIVATE
    )
    async def inline_ban_action(
        callback: CallbackQuery
    ):

        if callback.from_user.id != owner_id:

            return await callback.answer(
                "للمالك فقط",
                show_alert=True
            )

        target_id = int(
            callback.data.split("_")[2]
        )

        try:

            res = (
                supabase.table("custom_bot_bans")
                .select("user_id")
                .eq("bot_id", bot_id)
                .eq("user_id", target_id)
                .execute()
            )

            # =============================================
            # فك الحظر
            # =============================================

            if len(res.data) > 0:

                (
                    supabase.table("custom_bot_bans")
                    .delete()
                    .eq("bot_id", bot_id)
                    .eq("user_id", target_id)
                    .execute()
                )

                await callback.answer(
                    f"✅ تم فك الحظر عن المستخدم {target_id}",
                    show_alert=True
                )

            # =============================================
            # حظر
            # =============================================

            else:

                (
                    supabase.table("custom_bot_bans")
                    .insert(
                        {
                            "bot_id": bot_id,
                            "user_id": target_id
                        }
                    )
                    .execute()
                )

                await callback.answer(
                    f"🚷 تم حظر المستخدم {target_id}",
                    show_alert=True
                )

        except Exception as e:

            await callback.answer(
                f"خطأ: {e}",
                show_alert=True
            )

    # =====================================================
    # الرسائل الخاصة داخل البوت المصنوع
    # =====================================================

    @custom_dp.message(
        F.chat.type == ChatType.PRIVATE
    )
    async def custom_message_handler(
        message: Message
    ):

        u_id = message.from_user.id

        uname = (
            message.from_user.username
            or "None"
        )

        name = (
            message.from_user.first_name
            or "المستخدم"
        )

        # =================================================
        # المالك
        # =================================================

        if u_id == owner_id:

            # =============================================
            # الرد الطبيعي باستخدام Telegram Reply
            #
            # لا يوجد زر رد.
            # المالك فقط يضغط Reply على الرسالة التي
            # وصلت إليه من المشترك.
            # =============================================

            if message.reply_to_message:

                target_id = reply_targets.get(
                    (
                        bot_id,
                        owner_id,
                        message.reply_to_message.message_id
                    )
                )

                if target_id:

                    try:

                        # إرسال نفس رسالة المالك إلى المشترك
                        await custom_bot.copy_message(
                            chat_id=target_id,
                            from_chat_id=owner_id,
                            message_id=message.message_id
                        )

                        # حذف الربط بعد نجاح الإرسال
                        reply_targets.pop(
                            (
                                bot_id,
                                owner_id,
                                message.reply_to_message.message_id
                            ),
                            None
                        )

                        await message.answer(
                            "✅ تم إرسال الرد للمستخدم بنجاح."
                        )

                        return

                    except Exception as e:

                        logger.exception(
                            "Failed to send owner reply"
                        )

                        await message.answer(
                            f"❌ تعذر إرسال الرد للمستخدم:\n{e}"
                        )

                        return

            # =============================================
            # تغيير الترحيب
            # =============================================

            if (
                f"waiting_welcome_{owner_id}"
                in user_sessions
                and message.text
            ):

                user_sessions.pop(
                    f"waiting_welcome_{owner_id}",
                    None
                )

                try:

                    (
                        supabase.table(
                            "custom_bot_settings"
                        )
                        .upsert(
                            {
                                "bot_id": bot_id,
                                "welcome_text": message.text
                            },
                            on_conflict="bot_id"
                        )
                        .execute()
                    )

                    await message.answer(
                        "✅ تم تحديث وحفظ رسالة الترحيب بنجاح."
                    )

                except Exception as e:

                    await message.answer(
                        f"❌ خطأ:\n{e}"
                    )

                return

            # =============================================
            # الرد التلقائي
            # =============================================

            if (
                f"waiting_autoreply_{owner_id}"
                in user_sessions
                and message.text
            ):

                user_sessions.pop(
                    f"waiting_autoreply_{owner_id}",
                    None
                )

                try:

                    (
                        supabase.table(
                            "custom_bot_settings"
                        )
                        .upsert(
                            {
                                "bot_id": bot_id,
                                "auto_reply": message.text
                            },
                            on_conflict="bot_id"
                        )
                        .execute()
                    )

                    await message.answer(
                        "✅ تم تحديث وحفظ الرد التلقائي بنجاح."
                    )

                except Exception as e:

                    await message.answer(
                        f"❌ خطأ:\n{e}"
                    )

                return

            # =============================================
            # الحظر عن طريق الآيدي
            # =============================================

            if (
                f"waiting_ban_{owner_id}"
                in user_sessions
                and message.text
            ):

                user_sessions.pop(
                    f"waiting_ban_{owner_id}",
                    None
                )

                try:

                    target_id = int(
                        message.text.strip()
                    )

                    res = (
                        supabase.table(
                            "custom_bot_bans"
                        )
                        .select("user_id")
                        .eq("bot_id", bot_id)
                        .eq("user_id", target_id)
                        .execute()
                    )

                    if len(res.data) > 0:

                        (
                            supabase.table(
                                "custom_bot_bans"
                            )
                            .delete()
                            .eq("bot_id", bot_id)
                            .eq("user_id", target_id)
                            .execute()
                        )

                        await message.answer(
                            f"✅ تم فك الحظر عن المستخدم:\n{target_id}"
                        )

                    else:

                        (
                            supabase.table(
                                "custom_bot_bans"
                            )
                            .insert(
                                {
                                    "bot_id": bot_id,
                                    "user_id": target_id
                                }
                            )
                            .execute()
                        )

                        await message.answer(
                            f"🚷 تم حظر المستخدم:\n{target_id}"
                        )

                except Exception as e:

                    await message.answer(
                        f"❌ الآيدي غير صحيح:\n{e}"
                    )

                return

            # =============================================
            # الإذاعة
            # =============================================

            if (
                f"custom_broadcast_{owner_id}"
                in user_sessions
            ):

                if not message.text:

                    return await message.answer(
                        "📨 الإذاعة الحالية تقبل النص فقط."
                    )

                user_sessions.pop(
                    f"custom_broadcast_{owner_id}",
                    None
                )

                b_text = message.text

                try:

                    subs = (
                        supabase.table(
                            "custom_bot_users"
                        )
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

                        await custom_bot.send_message(
                            sub["user_id"],
                            b_text
                        )

                        sent += 1

                        await asyncio.sleep(
                            0.03
                        )

                    except Exception:

                        pass

                await status_msg.edit_text(
                    "✅ تمت الإذاعة بنجاح!\n\n"
                    f"👥 عدد المستلمين: {sent}"
                )

                return

            # =============================================
            # لا نرسل أي تعليمات عن الرد
            # =============================================

            await message.answer(
                "👋 أنت مالك البوت.\n\n"
                "استخدم لوحة التحكم الموجودة في الأعلى لإدارة بوتك."
            )

            return

        # =================================================
        # المستخدم العادي
        # =================================================

        if is_user_banned(u_id):
            return

        # تسجيل المستخدم
        register_custom_user(
            u_id,
            name,
            uname
        )

        # =================================================
        # الرد التلقائي
        # =================================================

        try:

            res_s = (
                supabase.table(
                    "custom_bot_settings"
                )
                .select("auto_reply")
                .eq("bot_id", bot_id)
                .execute()
            )

            data_s = (
                res_s.data[0]
                if res_s.data
                else {}
            )

            auto_reply = (
                data_s.get("auto_reply")
                or "اهلا حبيب شوي و ارد 🌷."
            )

        except Exception:

            auto_reply = (
                "اهلا حبيب شوي و ارد 🌷."
            )

        # =================================================
        # إرسال رسالة المستخدم للمالك
        # =================================================

        try:

            copied = await custom_bot.copy_message(
                chat_id=owner_id,
                from_chat_id=u_id,
                message_id=message.message_id
            )

            # =================================================
            # أهم جزء:
            #
            # نخزن ID الرسالة التي وصلت للمالك.
            #
            # عندما المالك يسوي Reply عليها مباشرة،
            # نعرف المستخدم الذي أرسلها.
            #
            # لا يوجد زر «رد».
            # لا يوجد ForceReply.
            # لا يوجد نسخ جديد للرسالة.
            # =================================================

            reply_targets[
                (
                    bot_id,
                    owner_id,
                    copied.message_id
                )
            ] = u_id

        except Exception as e:

            logger.error(
                "Failed to copy user message to owner "
                f"(bot={bot_id}, user={u_id}): {e}"
            )

        # =================================================
        # معلومات المشترك
        #
        # بسيطة ومرتبة مثل النسخة القديمة
        # بدون شرح طريقة الرد
        # وبدون زر رد
        # =================================================

        if uname != "None":

            info_text = (
                "👤 معلومات المشترك:\n\n"
                f"• الاسم: {name}\n"
                f"• المعرف: @{uname}\n"
                f"• الآيدي: {u_id}"
            )

        else:

            info_text = (
                "👤 معلومات المشترك:\n\n"
                f"• الاسم: {name}\n"
                "• المعرف: لا يوجد\n"
                f"• الآيدي: {u_id}"
            )

        # =================================================
        # زر الحظر فقط
        # =================================================

        info_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚷 حظر / فك الحظر",
                        callback_data=f"ban_user_{u_id}"
                    )
                ]
            ]
        )

        await custom_bot.send_message(
            chat_id=owner_id,
            text=info_text,
            reply_markup=info_markup
        )

        # =================================================
        # زر الصانع للمستخدم
        # =================================================

        promo_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🤖 صنع بوتك الخاص من هنا ⚡",
                        url=f"https://t.me/{MAKER_BOT_USERNAME}"
                    )
                ]
            ]
        )

        await message.answer(
            auto_reply,
            reply_markup=promo_markup
        )

    # =====================================================
    # تشغيل البوت
    # =====================================================

    try:

        running_custom_bots[
            bot_id
        ] = custom_bot

        logger.info(
            f"Starting custom bot @{bot_username} "
            f"(ID: {bot_id})"
        )

        await custom_dp.start_polling(
            custom_bot,
            skip_updates=True
        )

    except Exception as e:

        logger.error(
            f"Custom bot {bot_id} error: {e}"
        )

    finally:

        try:
            await custom_bot.session.close()
        except Exception:
            pass

        running_custom_bots.pop(
            bot_id,
            None
        )


# =========================================================
# استئناف البوتات بعد إعادة تشغيل الصانع
# =========================================================

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
                        b["bot_username"]
                    )
                )

    except Exception as e:

        logger.error(
            f"Error resuming bots: {e}"
        )


# =========================================================
# القائمة الرئيسية للصانع
# =========================================================

async def send_home(
    message: Message,
    user_id: int
):

    if user_id == DEV_ID:

        text = (
            "⚙️ لوحة تحكم مالك المنصة الرئيسي\n\n"
            "أهلاً بك، لديك تحكم كامل بالمنصة."
        )

    else:

        name = (
            message.from_user.first_name
            or "المستخدم"
        )

        text = (
            f"• اهلا بك ({name}) 👋\n\n"
            "• في البوت الرسمي لصنع بوتات السايت والتواصل 📌\n\n"
            "• أنشئ بوتك بسهولة، واستقبل رسائل المستخدمين "
            "بهوية مجهولة، وتحكم بالبوت من لوحة الإدارة ⚡\n\n"
            "• البوتات تعمل بشكل مستمر حسب حالة البوت في المنصة.\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🤖 ابدأ الآن وأنشئ بوتك الخاص مجاناً."
        )

    await message.answer(
        text,
        reply_markup=get_main_menu(user_id)
    )


# =========================================================
# /start للصانع
# =========================================================

@dp.message(Command("start"))
async def start_handler(
    message: Message
):

    user_id = message.from_user.id

    # فحص الحظر
    if is_banned(user_id):

        return await message.answer(
            "عذراً، تم حظرك من استخدام المنصة."
        )

    # تسجيل المستخدم
    try:

        (
            supabase.table("maker_users")
            .upsert(
                {
                    "user_id": user_id,
                    "username": (
                        message.from_user.username
                        or "None"
                    ),
                    "full_name": (
                        message.from_user.first_name
                        or "المستخدم"
                    ),
                }
            )
            .execute()
        )

    except Exception:
        pass

    # =====================================================
    # المطور
    # =====================================================

    if user_id == DEV_ID:

        text = (
            "⚙️ لوحة تحكم مالك المنصة الرئيسي\n\n"
            "أهلاً بك، تحكم كامل وخيارات واسعة لإدارة المنصة."
        )

        await message.answer(
            text,
            reply_markup=get_main_menu(user_id)
        )

        return

    # =====================================================
    # المستخدم العادي
    # =====================================================

    name = (
        message.from_user.first_name
        or "المستخدم"
    )

    text = (
        f"• اهلا بك ({name}) 👋\n\n"
        "• في البوت الرسمي لصنع بوتات السايت والتواصل 📌\n\n"
        "• أنشئ بوتك بسهولة، واستقبل رسائل المستخدمين "
        "بهوية مجهولة، وتحكم بالبوت من لوحة الإدارة ⚡\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🤖 ابدأ الآن وأنشئ بوتك الخاص مجاناً."
    )

    await message.answer(
        text,
        reply_markup=get_main_menu(user_id)
    )


# =========================================================
# إنشاء بوت جديد
# =========================================================

@dp.callback_query(
    F.data == "create_new_bot"
)
async def step_create_bot(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    user_sessions[user_id] = {
        "state": "waiting_for_token"
    }

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="إلغاء والعودة 🔙",
                    callback_data="back_home"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "🤖 إنشاء بوت جديد\n\n"
        "أرسل الآن توكن البوت Bot Token الخاص بك "
        "من @BotFather.\n\n"
        "مثال:\n"
        "123456789:AAxxxxxxxxxxxxxxxxxxxx",
        reply_markup=markup
    )

    await callback.answer()


# =========================================================
# معالجة الرسائل النصية للصانع
# =========================================================

@dp.message(F.text)
async def text_processor(
    message: Message
):

    user_id = message.from_user.id

    if is_banned(user_id):
        return

    session = user_sessions.get(
        user_id,
        {}
    )

    state = session.get(
        "state"
    )

    # =====================================================
    # إنشاء بوت بواسطة Token
    # =====================================================

    if state == "waiting_for_token":

        token = message.text.strip()

        user_sessions.pop(
            user_id,
            None
        )

        # =================================================
        # فحص التوكن
        # =================================================

        try:

            temp_bot = Bot(
                token=token
            )

            me = await temp_bot.get_me()

            await temp_bot.session.close()

        except Exception as e:

            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🔄 إعادة المحاولة",
                            callback_data="create_new_bot"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="رجوع 🔙",
                            callback_data="back_home"
                        )
                    ]
                ]
            )

            return await message.answer(
                "❌ التوكن غير صالح.\n\n"
                f"التفاصيل:\n{e}\n\n"
                "تأكد من التوكن وأرسله مرة أخرى.",
                reply_markup=markup
            )

        # =================================================
        # إضافة البوت إلى Supabase
        # =================================================

        try:

            res = (
                supabase.table(
                    "enterprise_bots"
                )
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

            new_bot_id = (
                res.data[0]["id"]
                if res.data
                else None
            )

            if new_bot_id:

                asyncio.create_task(
                    start_user_bot_polling(
                        new_bot_id,
                        token,
                        user_id,
                        me.username
                    )
                )

        except Exception as e:

            return await message.answer(
                "❌ حدث خطأ أثناء حفظ البوت:\n\n"
                f"{e}"
            )

        # =================================================
        # نجاح الإنشاء
        # =================================================

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 الذهاب إلى بوتاتي",
                        callback_data="my_custom_bots"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 القائمة الرئيسية",
                        callback_data="back_home"
                    )
                ]
            ]
        )

        await message.answer(
            "✅ تم إنشاء وتشغيل بوتك بنجاح!\n\n"
            f"🤖 الاسم: {me.first_name}\n"
            f"🔗 المعرف: @{me.username}\n\n"
            "يمكنك الآن الدخول إلى بوتك وإرسال رسائل تجريبية.",
            reply_markup=markup
        )

        return

    # =====================================================
    # إذاعة المطور
    # =====================================================

    elif (
        state == "dev_broadcasting"
        and user_id == DEV_ID
    ):

        user_sessions.pop(
            user_id,
            None
        )

        b_text = message.text

        try:

            users = (
                supabase.table(
                    "maker_users"
                )
                .select("user_id")
                .execute()
                .data
            )

        except Exception:

            users = []

        sent = 0

        status = await message.answer(
            "📨 جاري تنفيذ الإذاعة العامة..."
        )

        for u in users:

            try:

                await bot.send_message(
                    u["user_id"],
                    "📢 إشعار إداري من المنصة:\n\n"
                    f"{b_text}"
                )

                sent += 1

                await asyncio.sleep(
                    0.03
                )

            except Exception:

                pass

        await status.edit_text(
            "✅ تمت الإذاعة العامة بنجاح!\n\n"
            f"👥 عدد المستلمين: {sent}"
        )


# =========================================================
# قائمة بوتات المستخدم
# =========================================================

@dp.callback_query(
    F.data == "my_custom_bots"
)
async def list_user_bots(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    try:

        res = (
            supabase.table(
                "enterprise_bots"
            )
            .select("*")
            .eq("owner_id", user_id)
            .execute()
        )

        bots = res.data

    except Exception:

        bots = []

    # =====================================================
    # لا توجد بوتات
    # =====================================================

    if not bots:

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🤖 صنع بوت جديد",
                        callback_data="create_new_bot"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🏠 القائمة الرئيسية",
                        callback_data="back_home"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            "📋 بوتاتك\n\n"
            "لا توجد أي بوتات مصنوعة بواسطة حسابك حتى الآن.",
            reply_markup=markup
        )

        await callback.answer()

        return

    # =====================================================
    # عرض البوتات
    # =====================================================

    buttons = []

    for b in bots:

        status = (
            "🟢 يعمل"
            if b["is_active"]
            else "⏸ متوقف"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{status} | @{b['bot_username']}",
                    callback_data=f"manage_bot_{b['id']}"
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🤖 صنع بوت آخر",
                callback_data="create_new_bot"
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                text="🏠 القائمة الرئيسية",
                callback_data="back_home"
            )
        ]
    )

    await callback.message.edit_text(
        "📋 بوتاتك\n\n"
        "اختر البوت الذي تريد إدارته:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# إدارة بوت واحد
# =========================================================

@dp.callback_query(
    F.data.startswith("manage_bot_")
)
async def manage_single_bot(
    callback: CallbackQuery
):

    bot_id = int(
        callback.data.split("_")[2]
    )

    try:

        res = (
            supabase.table(
                "enterprise_bots"
            )
            .select("*")
            .eq("id", bot_id)
            .eq("owner_id", callback.from_user.id)
            .execute()
        )

        if not res.data:

            return await callback.answer(
                "البوت غير موجود!",
                show_alert=True
            )

        b_data = res.data[0]

    except Exception:

        return await callback.answer(
            "خطأ في الاتصال بقاعدة البيانات!",
            show_alert=True
        )

    text = (
        f"🤖 إدارة البوت\n\n"
        f"• الاسم: {b_data['bot_name']}\n"
        f"• المعرف: @{b_data['bot_username']}\n"
        f"• الحالة: "
        f"{'🟢 يعمل' if b_data['is_active'] else '⏸ متوقف'}"
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 حذف البوت نهائياً",
                    callback_data=f"delete_bot_{bot_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="العودة لقائمة بوتاتي 🔙",
                    callback_data="my_custom_bots"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=markup
    )

    await callback.answer()


# =========================================================
# حذف بوت من قائمة المستخدم
# =========================================================

@dp.callback_query(
    F.data.startswith("delete_bot_")
)
async def delete_bot_action(
    callback: CallbackQuery
):

    bot_id = int(
        callback.data.split("_")[2]
    )

    try:

        # التأكد أن البوت يعود لنفس المستخدم
        check = (
            supabase.table(
                "enterprise_bots"
            )
            .select("id")
            .eq("id", bot_id)
            .eq("owner_id", callback.from_user.id)
            .execute()
        )

        if not check.data:

            return await callback.answer(
                "هذا البوت غير تابع لك.",
                show_alert=True
            )

        # إيقاف البوت
        if bot_id in running_custom_bots:

            try:

                await running_custom_bots[
                    bot_id
                ].session.close()

            except Exception:
                pass

            del running_custom_bots[
                bot_id
            ]

        # حذف من قاعدة البيانات
        (
            supabase.table(
                "enterprise_bots"
            )
            .delete()
            .eq("id", bot_id)
            .execute()
        )

        # حذف روابط الرد
        for key in list(reply_targets):

            if key[0] == bot_id:

                reply_targets.pop(
                    key,
                    None
                )

        await callback.answer(
            "🗑 تم حذف البوت بنجاح.",
            show_alert=True
        )

        await list_user_bots(
            callback
        )

    except Exception as e:

        await callback.answer(
            f"خطأ: {e}",
            show_alert=True
        )


# =========================================================
# إدارة جميع بوتات المنصة للمطور
# =========================================================

@dp.callback_query(
    F.data == "dev_all_bots"
)
async def dev_all_bots_handler(
    callback: CallbackQuery
):

    if callback.from_user.id != DEV_ID:
        return

    try:

        res = (
            supabase.table(
                "enterprise_bots"
            )
            .select("*")
            .execute()
        )

        bots = res.data

    except Exception:

        bots = []

    if not bots:

        await callback.message.edit_text(
            "🤖 إدارة البوتات\n\n"
            "لا توجد بوتات مسجلة في المنصة حالياً.",
            reply_markup=get_back_button(
                "back_home"
            )
        )

        await callback.answer()

        return

    buttons = []

    for b in bots[:30]:

        status = (
            "🟢"
            if b["is_active"]
            else "⏸"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{status} "
                        f"@{b['bot_username']} "
                        f"| {b['owner_id']}"
                    ),
                    callback_data=(
                        f"dev_del_bot_{b['id']}"
                    )
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="رجوع 🔙",
                callback_data="back_home"
            )
        ]
    )

    await callback.message.edit_text(
        "🤖 إدارة جميع بوتات المنصة\n\n"
        "اضغط على البوت لحذفه من المنصة:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()


# =========================================================
# حذف بوت من المطور
# =========================================================

@dp.callback_query(
    F.data.startswith("dev_del_bot_")
)
async def dev_del_bot_action(
    callback: CallbackQuery
):

    if callback.from_user.id != DEV_ID:
        return

    bot_id = int(
        callback.data.split("_")[3]
    )

    try:

        if bot_id in running_custom_bots:

            try:

                await running_custom_bots[
                    bot_id
                ].session.close()

            except Exception:
                pass

            del running_custom_bots[
                bot_id
            ]

        (
            supabase.table(
                "enterprise_bots"
            )
            .delete()
            .eq("id", bot_id)
            .execute()
        )

        for key in list(reply_targets):

            if key[0] == bot_id:

                reply_targets.pop(
                    key,
                    None
                )

        await callback.answer(
            "🗑 تم حذف البوت من المنصة بنجاح.",
            show_alert=True
        )

        await dev_all_bots_handler(
            callback
        )

    except Exception as e:

        await callback.answer(
            f"خطأ: {e}",
            show_alert=True
        )


# =========================================================
# إحصائيات المنصة
# =========================================================

@dp.callback_query(
    F.data == "dev_stats"
)
async def dev_stats_handler(
    callback: CallbackQuery
):

    if callback.from_user.id != DEV_ID:
        return

    try:

        users = len(
            supabase.table(
                "maker_users"
            )
            .select("user_id")
            .execute()
            .data
        )

        bots = len(
            supabase.table(
                "enterprise_bots"
            )
            .select("id")
            .execute()
            .data
        )

    except Exception:

        users = 0
        bots = 0

    text = (
        "📊 إحصائيات المنصة\n\n"
        f"👥 إجمالي المستخدمين: {users}\n"
        f"🤖 إجمالي البوتات: {bots}\n"
        f"🟢 البوتات العاملة حالياً: "
        f"{len(running_custom_bots)}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_back_button(
            "back_home"
        )
    )

    await callback.answer()


# =========================================================
# إذاعة المطور
# =========================================================

@dp.callback_query(
    F.data == "dev_broadcast"
)
async def dev_broadcast_handler(
    callback: CallbackQuery
):

    if callback.from_user.id != DEV_ID:
        return

    user_sessions[
        DEV_ID
    ] = {
        "state": "dev_broadcasting"
    }

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="إلغاء 🔙",
                    callback_data="back_home"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        "📨 الإذاعة العامة\n\n"
        "أرسل الآن النص الذي تريد إرساله "
        "إلى مستخدمي المنصة.",
        reply_markup=markup
    )

    await callback.answer()


# =========================================================
# حظر المنصة
# =========================================================

@dp.callback_query(
    F.data == "dev_ban_menu"
)
async def dev_ban_menu(
    callback: CallbackQuery
):

    if callback.from_user.id != DEV_ID:
        return

    await callback.message.edit_text(
        "🚷 إدارة حظر المنصة\n\n"
        "نظام الحظر العام للمنصة متاح للمطور.",
        reply_markup=get_back_button(
            "back_home"
        )
    )

    await callback.answer()


# =========================================================
# كيفية صنع بوت
# =========================================================

@dp.callback_query(
    F.data == "bot_info"
)
async def bot_info(
    callback: CallbackQuery
):

    text = (
        "❓ كيفية صنع بوت السايت\n\n"

        "اتبع الخطوات التالية 👇\n\n"

        "1️⃣ افتح بوت BotFather الرسمي.\n\n"

        "2️⃣ اضغط Start أو أرسل:\n"
        "/newbot\n\n"

        "3️⃣ اكتب اسم البوت الذي تريده.\n"
        "مثال:\n"
        "Mustafa Site\n\n"

        "4️⃣ بعد ذلك سيطلب منك Username للبوت.\n"
        "يجب أن ينتهي بـ bot.\n"
        "مثال:\n"
        "MustafaSiteBot\n\n"

        "5️⃣ سيعطيك BotFather توكن البوت.\n"
        "انسخ التوكن بالكامل.\n\n"

        "6️⃣ ارجع إلى هذا الصانع واضغط:\n"
        "🤖 صنع بوت جديد\n\n"

        "7️⃣ الصق التوكن هنا وأرسله.\n\n"

        "8️⃣ سيتم فحص التوكن وتشغيل البوت تلقائياً.\n\n"

        "✅ بعد نجاح الإنشاء، ادخل إلى البوت "
        "وأرسل /start وابدأ باستخدام السايت.\n\n"

        "⚠️ مهم جداً:\n"
        "لا ترسل توكن البوت لأي شخص، لأنه يعتبر مفتاح التحكم الكامل بالبوت."
    )

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🤖 فتح BotFather",
                    url="https://t.me/BotFather"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🤖 صنع بوت الآن",
                    callback_data="create_new_bot"
                )
            ],
            [
                InlineKeyboardButton(
                    text="رجوع 🔙",
                    callback_data="back_home"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=markup
    )

    await callback.answer()


# =========================================================
# تغيير اللغة
# =========================================================

@dp.callback_query(
    F.data == "change_lang"
)
async def change_lang(
    callback: CallbackQuery
):

    await callback.answer(
        "🇮🇶 اللغة الحالية: العربية",
        show_alert=True
    )


# =========================================================
# الرجوع للقائمة الرئيسية
# =========================================================

@dp.callback_query(
    F.data == "back_home"
)
async def back_home(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    if user_id == DEV_ID:

        text = (
            "⚙️ لوحة تحكم مالك المنصة الرئيسي\n\n"
            "أهلاً بك، تحكم كامل وخيارات واسعة لإدارة المنصة."
        )

    else:

        name = (
            callback.from_user.first_name
            or "المستخدم"
        )

        text = (
            f"• اهلا بك ({name}) 👋\n\n"
            "• في البوت الرسمي لصنع بوتات السايت والتواصل 📌\n\n"
            "• أنشئ بوتك بسهولة، واستقبل رسائل المستخدمين "
            "بهوية مجهولة، وتحكم بالبوت من لوحة الإدارة ⚡\n\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "🤖 ابدأ الآن وأنشئ بوتك الخاص مجاناً."
        )

    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu(
            user_id
        )
    )

    await callback.answer()


# =========================================================
# التشغيل الرئيسي
# =========================================================

async def main():

    await resume_all_active_bots()

    logger.info(
        "Ultimate Production Bot Maker started successfully!"
    )

    await dp.start_polling(
        bot
    )


# =========================================================
# Start
# =========================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
