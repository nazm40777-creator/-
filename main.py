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
# إعداد التسجيل
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)


# =========================================================
# الإعدادات
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

DEV_ID = int(os.getenv("DEV_ID", "5126968608"))

MAKER_BOT_USERNAME = "fde7Bot"
DEV_USERNAME = "toe7e"


# =========================================================
# Supabase
# =========================================================

supabase: SupabaseClient = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
)


# =========================================================
# البوت الرئيسي
# =========================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================================================
# الجلسات
# =========================================================

user_sessions = {}


# =========================================================
# البوتات المصنوعة التي تعمل حالياً
# =========================================================

running_custom_bots = {}


# =========================================================
# ربط رسالة المالك بالمستخدم الحقيقي
#
# المفتاح:
# (bot_id, owner_id, owner_message_id)
#
# القيمة:
# user_id
#
# هذا هو النظام الجديد للرد المباشر.
# =========================================================

reply_targets = {}


# =========================================================
# فحص حظر مستخدم المنصة
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


# =========================================================
# لوحة صاحب البوت
# =========================================================

def get_owner_panel() -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🤖 إدارة البوت",
                    callback_data="cb_manage",
                ),
                InlineKeyboardButton(
                    text="📊 الإحصائيات",
                    callback_data="cb_stats",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="📨 إذاعة للمستخدمين",
                    callback_data="cb_broadcast",
                ),
                InlineKeyboardButton(
                    text="👥 إدارة المستخدمين",
                    callback_data="cb_users",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="👋 تغيير الترحيب",
                    callback_data="cb_welcome",
                ),
                InlineKeyboardButton(
                    text="💬 الرد التلقائي",
                    callback_data="cb_autoreply",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="🚷 الحظر وفك الحظر",
                    callback_data="cb_bans",
                ),
                InlineKeyboardButton(
                    text="⏸ إيقاف/تشغيل",
                    callback_data="cb_toggle",
                ),
            ],

            [
                InlineKeyboardButton(
                    text="🗑 حذف البوت نهائياً",
                    callback_data="cb_delete",
                )
            ],

            [
                InlineKeyboardButton(
                    text="✉️ التواصل مع المطور",
                    url=f"https://t.me/{DEV_USERNAME}",
                )
            ],
        ]
    )


# =========================================================
# تشغيل بوت المستخدم
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
        uname: str,
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
                on_conflict="bot_id,user_id",
            ).execute()

        except Exception:
            pass


    # =====================================================
    # فحص حظر مستخدم من بوت معين
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
    # START للبوت المصنوع
    # =====================================================

    @custom_dp.message(
        Command("start"),
        F.chat.type == ChatType.PRIVATE,
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


        # -------------------------------------------------
        # الحظر
        # -------------------------------------------------

        if is_user_banned(u_id) and u_id != owner_id:

            return await message.answer(
                "عذراً، تم حظرك من استخدام هذا البوت."
            )


        # -------------------------------------------------
        # تسجيل المستخدم
        # -------------------------------------------------

        register_custom_user(
            u_id,
            name,
            uname,
        )


        # -------------------------------------------------
        # المالك
        # -------------------------------------------------

        if u_id == owner_id:

            await message.answer(
                "⟡ أهلاً بك أيها المالك في لوحة التحكم الخاصة ببوتك 💜\n\n"
                "📩 ملاحظة مهمة:\n"
                "للرد على أي مشترك، اضغط Reply مباشرةً على "
                "رسالة المشترك وأرسل ردك.",
                reply_markup=get_owner_panel(),
            )

            return


        # -------------------------------------------------
        # جلب الترحيب
        # -------------------------------------------------

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
                    f"• اهلا بك ({user_display}) "
                    "في بوت السايت الخاص بي ❤️\n\n"
                    "• ارسل رسالتك بهوية مجهولة "
                    "وسوف يرد عليك بأقرب وقت 📢"
                )

        except Exception:

            welcome_msg = (
                f"• اهلا بك ({user_display}) "
                "في بوت السايت الخاص بي ❤️\n\n"
                "• ارسل رسالتك بهوية مجهولة "
                "وسوف يرد عليك بأقرب وقت 📢"
            )


        # -------------------------------------------------
        # زر صنع بوت
        # -------------------------------------------------

        promo_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🤖 صنع بوتك الخاص من هنا ⚡",
                        url=f"https://t.me/{MAKER_BOT_USERNAME}",
                    )
                ]
            ]
        )


        await message.answer(
            welcome_msg,
            reply_markup=promo_markup,
        )


    # =====================================================
    # لوحة التحكم - CALLBACKS
    # =====================================================

    @custom_dp.callback_query(
        F.data.startswith("cb_"),
        F.message.chat.type == ChatType.PRIVATE,
    )
    async def custom_callbacks(
        callback: CallbackQuery
    ):

        # -------------------------------------------------
        # المالك فقط
        # -------------------------------------------------

        if callback.from_user.id != owner_id:

            return await callback.answer(
                "عذراً، هذه اللوحة خاصة بمالك البوت فقط.",
                show_alert=True,
            )


        action = callback.data


        # -------------------------------------------------
        # زر الرجوع
        # -------------------------------------------------

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


        # =================================================
        # إدارة البوت
        # =================================================

        if action == "cb_manage":

            await callback.message.edit_text(

                f"🤖 معلومات وإدارة البوت\n\n"
                f"━━━━━━━━━━━━━━\n"
                f"🔹 المعرف: @{bot_username}\n"
                f"🟢 الحالة: يعمل بنجاح\n"
                f"━━━━━━━━━━━━━━\n\n"
                f"📩 الرد على المشتركين:\n"
                f"اضغط Reply مباشرةً على رسالة المشترك "
                f"ولا تحتاج إلى زر رد.",

                reply_markup=back_btn,
            )


        # =================================================
        # الإحصائيات
        # =================================================

        elif action == "cb_stats":

            try:

                users_data = (
                    supabase.table(
                        "custom_bot_users"
                    )
                    .select("user_id")
                    .eq("bot_id", bot_id)
                    .execute()
                    .data
                )

                subs = len(users_data)

            except Exception:

                subs = 0


            await callback.message.edit_text(

                f"📊 إحصائيات بوتك\n\n"
                f"━━━━━━━━━━━━━━\n"
                f"👥 عدد المشتركين: {subs}\n"
                f"🤖 البوت: @{bot_username}\n"
                f"🟢 الحالة: يعمل\n"
                f"━━━━━━━━━━━━━━",

                reply_markup=back_btn,
            )


        # =================================================
        # الإذاعة
        # =================================================

        elif action == "cb_broadcast":

            user_sessions[
                f"custom_broadcast_{owner_id}"
            ] = {
                "bot_id": bot_id,
                "custom_bot": custom_bot,
            }


            await callback.message.edit_text(

                "📨 إرسال إذاعة\n\n"
                "أرسل الآن الرسالة التي تريد إرسالها "
                "إلى جميع مشتركي بوتك.\n\n"
                "⚠️ حالياً الإذاعة النصية متاحة.",

                reply_markup=back_btn,
            )


        # =================================================
        # المستخدمين
        # =================================================

        elif action == "cb_users":

            try:

                users = (
                    supabase.table(
                        "custom_bot_users"
                    )
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

                u_text = (
                    "👥 إدارة المستخدمين\n\n"
                    "لا يوجد مشتركون مسجلون حالياً."
                )

            else:

                lines = [
                    "👥 إدارة المستخدمين",
                    "",
                    f"📊 العدد الكلي: {len(users)}",
                    "",
                    "━━━━━━━━━━━━━━",
                ]

                for index, u in enumerate(
                    users[:25],
                    start=1,
                ):

                    full_name = (
                        u.get("full_name")
                        or "بدون اسم"
                    )

                    username = (
                        u.get("username")
                        or "None"
                    )

                    user_id = u.get(
                        "user_id"
                    )

                    username_display = (
                        f"@{username}"
                        if username != "None"
                        else "لا يوجد معرف"
                    )

                    lines.append(
                        f"{index}. 👤 {full_name}\n"
                        f"   🔗 {username_display}\n"
                        f"   🆔 `{user_id}`"
                    )

                if len(users) > 25:

                    lines.append(
                        "\n… يتم عرض أول 25 مستخدم فقط."
                    )

                u_text = "\n".join(lines)


            await callback.message.edit_text(
                u_text,
                reply_markup=back_btn,
            )


        # =================================================
        # الترحيب
        # =================================================

        elif action == "cb_welcome":

            user_sessions[
                f"waiting_welcome_{owner_id}"
            ] = {
                "bot_id": bot_id
            }


            await callback.message.edit_text(

                "👋 إعداد رسالة الترحيب\n\n"
                "أرسل النص الجديد الآن.\n\n"
                "يمكنك استخدام:\n"
                "• `{name}` = اسم المستخدم\n"
                "• `{username}` = معرف المستخدم",

                reply_markup=back_btn,
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

                "💬 إعداد الرد التلقائي\n\n"
                "أرسل الآن النص الذي تريد أن يصل "
                "للمستخدم بعد إرسال رسالته.",

                reply_markup=back_btn,
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

                "🚷 إدارة الحظر\n\n"
                "أرسل آيدي المستخدم.\n\n"
                "إذا كان محظوراً سيتم فك الحظر، "
                "وإذا لم يكن محظوراً سيتم حظره.",

                reply_markup=back_btn,
            )


        # =================================================
        # إيقاف / تشغيل
        # =================================================

        elif action == "cb_toggle":

            try:

                res = (
                    supabase.table(
                        "enterprise_bots"
                    )
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

                supabase.table(
                    "enterprise_bots"
                ).update(
                    {
                        "is_active": new_state
                    }
                ).eq(
                    "id",
                    bot_id,
                ).execute()

                status = (
                    "🟢 يعمل"
                    if new_state
                    else "⏸ متوقف"
                )

            except Exception as e:

                status = f"❌ خطأ: {e}"


            await callback.message.edit_text(

                "⚙️ تم تحديث حالة البوت\n\n"
                f"الحالة الحالية: {status}",

                reply_markup=back_btn,
            )


        # =================================================
        # حذف البوت
        # =================================================

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

                "⚠️ تأكيد حذف البوت\n\n"
                "سيتم حذف البوت من قاعدة البيانات "
                "وإيقاف تشغيله.\n\n"
                "⚠️ العملية لا يمكن التراجع عنها.",

                reply_markup=markup_confirm,
            )


        # =================================================
        # رجوع
        # =================================================

        elif action == "cb_back":

            await callback.message.edit_text(
                "⟡ أهلاً بك أيها المالك في لوحة التحكم "
                "الخاصة ببوتك 💜",
                reply_markup=get_owner_panel(),
            )


        await callback.answer()


    # =====================================================
    # تأكيد حذف البوت
    # =====================================================

    @custom_dp.callback_query(
        F.data.startswith("confirm_del_"),
        F.message.chat.type == ChatType.PRIVATE,
    )
    async def confirm_delete_bot(
        callback: CallbackQuery
    ):

        if callback.from_user.id != owner_id:

            return await callback.answer(
                "للمالك فقط",
                show_alert=True,
            )


        b_id = int(
            callback.data.split("_")[2]
        )


        try:

            supabase.table(
                "enterprise_bots"
            ).delete().eq(
                "id",
                b_id,
            ).execute()


            if b_id in running_custom_bots:

                try:

                    await running_custom_bots[
                        b_id
                    ].session.close()

                except Exception:
                    pass

                del running_custom_bots[b_id]


            # تنظيف روابط الرد
            for key in list(reply_targets):

                if key[0] == b_id:

                    reply_targets.pop(
                        key,
                        None,
                    )


            await callback.message.edit_text(
                "🗑 تم حذف البوت نهائياً بنجاح."
            )


        except Exception as e:

            await callback.answer(
                f"خطأ: {e}",
                show_alert=True,
            )


    # =====================================================
    # حظر / فك حظر من رسالة المستخدم
    # =====================================================

    @custom_dp.callback_query(
        F.data.startswith("ban_user_"),
        F.message.chat.type == ChatType.PRIVATE,
    )
    async def inline_ban_action(
        callback: CallbackQuery
    ):

        if callback.from_user.id != owner_id:

            return await callback.answer(
                "للمالك فقط",
                show_alert=True,
            )


        target_id = int(
            callback.data.split("_")[2]
        )


        try:

            res = (
                supabase.table(
                    "custom_bot_bans"
                )
                .select("user_id")
                .eq("bot_id", bot_id)
                .eq("user_id", target_id)
                .execute()
            )


            # -------------------------------------------------
            # فك الحظر
            # -------------------------------------------------

            if len(res.data) > 0:

                supabase.table(
                    "custom_bot_bans"
                ).delete().eq(
                    "bot_id",
                    bot_id,
                ).eq(
                    "user_id",
                    target_id,
                ).execute()


                await callback.answer(
                    f"✅ تم فك الحظر عن المستخدم:\n{target_id}",
                    show_alert=True,
                )


            # -------------------------------------------------
            # حظر
            # -------------------------------------------------

            else:

                supabase.table(
                    "custom_bot_bans"
                ).insert(
                    {
                        "bot_id": bot_id,
                        "user_id": target_id,
                    }
                ).execute()


                await callback.answer(
                    f"🚷 تم حظر المستخدم:\n{target_id}",
                    show_alert=True,
                )


        except Exception as e:

            await callback.answer(
                f"خطأ: {e}",
                show_alert=True,
            )


    # =====================================================
    # جميع الرسائل الخاصة للبوت
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
            # الرد المباشر على رسالة المشترك
            #
            # المالك يضغط Reply على الرسالة الأصلية
            # والبوت يبحث عن صاحبها ويرسل الرد له.
            # =============================================

            if message.reply_to_message:

                target_id = reply_targets.get(
                    (
                        bot_id,
                        owner_id,
                        message.reply_to_message.message_id,
                    )
                )


                if target_id:

                    try:

                        await custom_bot.copy_message(
                            chat_id=target_id,
                            from_chat_id=owner_id,
                            message_id=message.message_id,
                        )


                        reply_targets.pop(
                            (
                                bot_id,
                                owner_id,
                                message.reply_to_message.message_id,
                            ),
                            None,
                        )


                        await message.answer(
                            "✅ تم إرسال الرد إلى المشترك بنجاح."
                        )


                    except Exception as e:

                        logger.exception(
                            "Failed to send owner reply"
                        )


                        await message.answer(
                            "❌ تعذر إرسال الرد إلى المشترك.\n\n"
                            f"الخطأ: {e}"
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
                    f"waiting_welcome_{owner_id}"
                )


                try:

                    supabase.table(
                        "custom_bot_settings"
                    ).upsert(
                        {
                            "bot_id": bot_id,
                            "welcome_text": message.text,
                        },
                        on_conflict="bot_id",
                    ).execute()


                    await message.answer(
                        "✅ تم تحديث وحفظ رسالة الترحيب بنجاح."
                    )


                except Exception as e:

                    await message.answer(
                        f"❌ خطأ:\n{e}"
                    )


                return


            # =============================================
            # تغيير الرد التلقائي
            # =============================================

            if (
                f"waiting_autoreply_{owner_id}"
                in user_sessions
                and message.text
            ):

                user_sessions.pop(
                    f"waiting_autoreply_{owner_id}"
                )


                try:

                    supabase.table(
                        "custom_bot_settings"
                    ).upsert(
                        {
                            "bot_id": bot_id,
                            "auto_reply": message.text,
                        },
                        on_conflict="bot_id",
                    ).execute()


                    await message.answer(
                        "✅ تم تحديث وحفظ الرد التلقائي بنجاح."
                    )


                except Exception as e:

                    await message.answer(
                        f"❌ خطأ:\n{e}"
                    )


                return


            # =============================================
            # الحظر من لوحة التحكم
            # =============================================

            if (
                f"waiting_ban_{owner_id}"
                in user_sessions
                and message.text
            ):

                user_sessions.pop(
                    f"waiting_ban_{owner_id}"
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

                        supabase.table(
                            "custom_bot_bans"
                        ).delete().eq(
                            "bot_id",
                            bot_id,
                        ).eq(
                            "user_id",
                            target_id,
                        ).execute()


                        await message.answer(
                            f"✅ تم فك الحظر عن المستخدم:\n"
                            f"`{target_id}`"
                        )


                    else:

                        supabase.table(
                            "custom_bot_bans"
                        ).insert(
                            {
                                "bot_id": bot_id,
                                "user_id": target_id,
                            }
                        ).execute()


                        await message.answer(
                            f"🚷 تم حظر المستخدم:\n"
                            f"`{target_id}`"
                        )


                except Exception as e:

                    await message.answer(
                        "❌ الآيدي غير صالح.\n\n"
                        f"الخطأ: {e}"
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
                    f"custom_broadcast_{owner_id}"
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
                    "📨 جاري إرسال الإذاعة "
                    "لمشتركي بوتك..."
                )


                for sub in subs:

                    try:

                        await custom_bot.send_message(
                            sub["user_id"],
                            b_text,
                        )

                        sent += 1

                        await asyncio.sleep(
                            0.03
                        )

                    except Exception:

                        pass


                await status_msg.edit_text(

                    "✅ تمت الإذاعة بنجاح!\n\n"
                    f"👥 عدد المستلمين: {sent} مشترك."

                )


                return


            # =============================================
            # رسالة المالك العادية
            # =============================================

            await message.answer(

                "👋 أنت مالك البوت.\n\n"
                "📩 عندما تصلك رسالة من مشترك:\n"
                "اضغط «Reply / رد» مباشرةً على "
                "رسالة المشترك وأرسل ردك.\n\n"
                "✅ سيتم توصيل الرد للمشترك تلقائياً."

            )

            return


        # =================================================
        # المستخدمون
        # =================================================

        if is_user_banned(u_id):

            return


        # =================================================
        # تسجيل المستخدم
        # =================================================

        register_custom_user(
            u_id,
            name,
            uname,
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
                or "اهلا حبيب، شوي و ارد 🌷"
            )


        except Exception:

            auto_reply = (
                "اهلا حبيب، شوي و ارد 🌷"
            )


        # =================================================
        # إرسال رسالة المستخدم للمالك
        #
        # لا يوجد زر «رد 💬» هنا.
        # =================================================

        try:

            copied_message = (
                await custom_bot.copy_message(
                    chat_id=owner_id,
                    from_chat_id=u_id,
                    message_id=message.message_id,
                )
            )


            # ------------------------------------------------
            # حفظ علاقة رسالة المالك بالمستخدم
            # ------------------------------------------------

            reply_targets[
                (
                    bot_id,
                    owner_id,
                    copied_message.message_id,
                )
            ] = u_id


        except Exception as e:

            logger.error(
                "Failed to copy user message "
                f"to owner "
                f"(bot={bot_id}, user={u_id}): {e}"
            )


        # =================================================
        # عرض معلومات المشترك
        # =================================================

        username_display = (
            f"@{uname}"
            if uname != "None"
            else "لا يوجد معرف"
        )


        info_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚷 حظر / فك الحظر",
                        callback_data=f"ban_user_{u_id}",
                    )
                ]
            ]
        )


        info_text = (

            "╭──────────────╮\n"
            "   👤 معلومات المشترك\n"
            "╰──────────────╯\n\n"

            f"👤 الاسم: {name}\n"
            f"🔗 المعرف: {username_display}\n"
            f"🆔 الآيدي: `{u_id}`\n\n"

            "━━━━━━━━━━━━━━━━\n"

            "💬 طريقة الرد:\n"
            "اضغط Reply / رد مباشرةً على "
            "رسالة المشترك بالأعلى وأرسل رسالتك.\n\n"

            "✅ سيتم إرسال الرد إليه تلقائياً."

        )


        await custom_bot.send_message(
            chat_id=owner_id,
            text=info_text,
            reply_markup=info_markup,
        )


        # =================================================
        # زر صنع بوت
        # =================================================

        promo_markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🤖 صنع بوتك الخاص من هنا ⚡",
                        url=f"https://t.me/{MAKER_BOT_USERNAME}",
                    )
                ]
            ]
        )


        # =================================================
        # الرد التلقائي للمستخدم
        # =================================================

        await message.answer(
            auto_reply,
            reply_markup=promo_markup,
        )


    # =====================================================
    # تشغيل البوت
    # =====================================================

    try:

        running_custom_bots[
            bot_id
        ] = custom_bot


        await custom_dp.start_polling(
            custom_bot,
            skip_updates=True,
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
            None,
        )


        # تنظيف روابط الرد الخاصة بهذا البوت

        for key in list(reply_targets):

            if key[0] == bot_id:

                reply_targets.pop(
                    key,
                    None,
                )


# =========================================================
# إعادة تشغيل جميع البوتات الفعالة
# =========================================================

async def resume_all_active_bots():

    try:

        res = (
            supabase.table(
                "enterprise_bots"
            )
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

        logger.error(
            f"Error resuming bots: {e}"
        )


# =========================================================
# START للبوت الرئيسي
# =========================================================

@dp.message(Command("start"))
async def start_handler(
    message: Message
):

    user_id = message.from_user.id


    # =====================================================
    # حظر
    # =====================================================

    if is_banned(user_id):

        return await message.answer(
            "عذراً، تم حظرك من استخدام المنصة."
        )


    # =====================================================
    # تسجيل مستخدم المنصة
    # =====================================================

    try:

        supabase.table(
            "maker_users"
        ).upsert(
            {
                "user_id": user_id,
                "username": (
                    message.from_user.username
                    or "None"
                ),
                "full_name": (
                    message.from_user.first_name
                ),
            }
        ).execute()

    except Exception:

        pass


    # =====================================================
    # المطور
    # =====================================================

    if user_id == DEV_ID:

        text = (

            "⚙️ لوحة تحكم مالك المنصة الرئيسي\n\n"
            "👑 أهلاً بك.\n"
            "تحكم كامل وخيارات واسعة لإدارة المنصة."

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


        await message.answer(
            text,
            reply_markup=markup,
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

        f"• اهلا بك ({name}) .\n"
        "• في البوت الرسمي لصنع بوتات السايت 📌\n"
        "• يحتوي البوت الذي يتم صنعه على "
        "مميزات متميزة وسرعة عالية\n"
        "• ويتميز بالاستقرار وعدم التوقف 📢\n\n"

        "━━━━━━━━━━━━━━━━━━\n\n"

        f"🤖 عجبك البوت؟\n"
        f"اصنع بوتك الخاص مجاناً!\n"
        f"@{MAKER_BOT_USERNAME}"

    )


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
                    text="📋 قائمة بوتاتك",
                    callback_data="my_custom_bots",
                )
            ],

            [
                InlineKeyboardButton(
                    text="❓ كيف اصنع بوت؟",
                    callback_data="bot_info",
                )
            ],

            [
                InlineKeyboardButton(
                    text="🌐 تغيير اللغة",
                    callback_data="change_lang",
                )
            ],

        ]
    )


    await message.answer(
        text,
        reply_markup=markup,
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
                    callback_data="back_home",
                )
            ]
        ]
    )


    await callback.message.edit_text(

        "🤖 إنشاء بوت تواصل جديد\n\n"
        "أرسل الآن توكن البوت Bot Token "
        "الخاص بك من @BotFather:",

        reply_markup=markup,
    )


    await callback.answer()


# =========================================================
# معالجة النصوص للبوت الرئيسي
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
    # إنشاء بوت
    # =====================================================

    if state == "waiting_for_token":

        token = message.text.strip()


        user_sessions.pop(
            user_id,
            None,
        )


        # -------------------------------------------------
        # التحقق من التوكن
        # -------------------------------------------------

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
                            text="إعادة المحاولة 🔄",
                            callback_data="create_new_bot",
                        )
                    ]
                ]
            )


            return await message.answer(

                "❌ التوكن غير صالح.\n\n"
                f"الخطأ:\n`{e}`\n\n"
                "تأكد من التوكن وأرسله مرة أخرى.",

                reply_markup=markup,
            )


        # -------------------------------------------------
        # حفظ البوت
        # -------------------------------------------------

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
                        me.username,
                    )
                )


        except Exception as e:

            return await message.answer(
                "❌ خطأ في قاعدة البيانات:\n"
                f"`{e}`"
            )


        # -------------------------------------------------
        # نجاح الإنشاء
        # -------------------------------------------------

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📋 الذهاب إلى قائمة بوتاتك",
                        callback_data="my_custom_bots",
                    )
                ]
            ]
        )


        await message.answer(

            "✅ تم إنشاء وتشغيل بوتك بنجاح!\n\n"

            f"🤖 اسم البوت: {me.first_name}\n"
            f"🔗 المعرف: @{me.username}\n\n"

            "📩 يمكنك الآن استقبال رسائل "
            "المشتركين والرد عليهم مباشرةً "
            "باستخدام Reply.",

            reply_markup=markup,
        )


    # =====================================================
    # إذاعة المطور
    # =====================================================

    elif (
        state == "dev_broadcasting"
        and user_id == DEV_ID
    ):

        user_sessions.pop(
            user_id,
            None,
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
                    "📢 إشعار إداري عام من المنصة:\n\n"
                    f"{b_text}",
                )


                sent += 1


                await asyncio.sleep(
                    0.03
                )


            except Exception:

                pass


        await status.edit_text(

            "✅ تمت الإذاعة العامة بنجاح!\n\n"
            f"👥 عدد المستلمين: {sent} مستخدم."

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

            "📋 بوتاتك\n\n"
            "لا توجد أي بوتات مصنوعة "
            "بواسطة حسابك حتى الآن.",

            reply_markup=markup,
        )


    # =====================================================
    # البوتات
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
                    text=(
                        f"{status} | "
                        f"@{b['bot_username']}"
                    ),
                    callback_data=(
                        f"manage_bot_{b['id']}"
                    ),
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
                text="🔙 الرئيسية",
                callback_data="back_home",
            ),
        ]

    )


    await callback.message.edit_text(

        "📋 بوتاتك المصنوعة\n\n"
        "اختر البوت الذي تريد إدارته:",

        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
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
            .execute()
        )


        if not res.data:

            return await callback.answer(
                "البوت غير موجود!",
                show_alert=True,
            )


        b_data = res.data[0]


    except Exception:

        return await callback.answer(
            "خطأ في الاتصال!",
            show_alert=True,
        )


    text = (

        f"🤖 إدارة البوت\n\n"

        f"━━━━━━━━━━━━━━\n"
        f"🔗 المعرف: @{b_data['bot_username']}\n"
        f"👤 الاسم: {b_data['bot_name']}\n"
        f"📊 الحالة: "
        f"{'🟢 يعمل' if b_data['is_active'] else '⏸ متوقف'}\n"
        f"━━━━━━━━━━━━━━\n\n"

        "📩 نظام الرد:\n"
        "الرد يتم مباشرة من خلال Reply "
        "على رسالة المشترك."

    )


    markup = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text="🗑 حذف البوت نهائياً",
                    callback_data=(
                        f"delete_bot_{bot_id}"
                    ),
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


    await callback.message.edit_text(
        text,
        reply_markup=markup,
    )


    await callback.answer()


# =========================================================
# حذف بوت المستخدم
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


        supabase.table(
            "enterprise_bots"
        ).delete().eq(
            "id",
            bot_id,
        ).execute()


        # تنظيف روابط الرد

        for key in list(reply_targets):

            if key[0] == bot_id:

                reply_targets.pop(
                    key,
                    None,
                )


        await callback.answer(
            "✅ تم حذف البوت بنجاح.",
            show_alert=True,
        )


        await list_user_bots(
            callback
        )


    except Exception as e:

        await callback.answer(
            f"خطأ: {e}",
            show_alert=True,
        )


# =========================================================
# إدارة جميع البوتات للمطور
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

        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="رجوع 🔙",
                        callback_data="back_home",
                    )
                ]
            ]
        )


        return await callback.message.edit_text(

            "لا توجد بوتات مسجلة في المنصة حالياً.",

            reply_markup=markup,
        )


    buttons = []


    for b in bots[:20]:

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
                        f"(Owner: {b['owner_id']})"
                    ),
                    callback_data=(
                        f"dev_del_bot_{b['id']}"
                    ),
                )
            ]

        )


    buttons.append(

        [
            InlineKeyboardButton(
                text="رجوع 🔙",
                callback_data="back_home",
            )
        ]

    )


    await callback.message.edit_text(

        "🤖 إدارة جميع بوتات المنصة\n\n"
        "اضغط على البوت لحذفه كأدمن:",

        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        ),
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


        supabase.table(
            "enterprise_bots"
        ).delete().eq(
            "id",
            bot_id,
        ).execute()


        # تنظيف روابط الرد

        for key in list(reply_targets):

            if key[0] == bot_id:

                reply_targets.pop(
                    key,
                    None,
                )


        await callback.answer(
            "✅ تم حذف البوت من المنصة بنجاح.",
            show_alert=True,
        )


        await dev_all_bots_handler(
            callback
        )


    except Exception as e:

        await callback.answer(
            f"خطأ: {e}",
            show_alert=True,
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

        "━━━━━━━━━━━━━━\n"
        f"👥 إجمالي المستخدمين: {users}\n"
        f"🤖 إجمالي البوتات: {bots}\n"
        "━━━━━━━━━━━━━━"

    )


    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="رجوع 🔙",
                    callback_data="back_home",
                )
            ]
        ]
    )


    await callback.message.edit_text(
        text,
        reply_markup=markup,
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


    user_sessions[DEV_ID] = {
        "state": "dev_broadcasting"
    }


    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="إلغاء 🔙",
                    callback_data="back_home",
                )
            ]
        ]
    )


    await callback.message.edit_text(

        "📨 الإذاعة العامة\n\n"
        "أرسل الآن نص الإذاعة "
        "لجميع مستخدمي المنصة:",

        reply_markup=markup,
    )


    await callback.answer()


# =========================================================
# إدارة الحظر للمطور
# =========================================================

@dp.callback_query(
    F.data == "dev_ban_menu"
)
async def dev_ban_menu(
    callback: CallbackQuery
):

    if callback.from_user.id != DEV_ID:

        return


    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="رجوع 🔙",
                    callback_data="back_home",
                )
            ]
        ]
    )


    await callback.message.edit_text(

        "🚷 إدارة الحظر العامة\n\n"
        "نظام الحظر العام للمنصة نشط ومؤمن.",

        reply_markup=markup,
    )


    await callback.answer()


# =========================================================
# معلومات البوت
# =========================================================

@dp.callback_query(
    F.data == "bot_info"
)
async def bot_info(
    callback: CallbackQuery
):

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="رجوع 🔙",
                    callback_data="back_home",
                )
            ]
        ]
    )


    await callback.message.edit_text(

        "🤖 عن المنصة\n\n"

        "هذه المنصة مخصصة لصناعة "
        "بوتات التواصل والسايت الاحترافية.\n\n"

        "⚡ سرعة عالية\n"
        "🟢 استقرار\n"
        "📩 نظام رد مباشر باستخدام Reply\n"
        "👥 إدارة المشتركين\n"
        "🚷 نظام حظر\n"
        "📨 إذاعة\n"
        "👋 رسالة ترحيب\n"
        "💬 رد تلقائي",

        reply_markup=markup,
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
        "🇮🇶 اللغة الحالية هي العربية",
        show_alert=True,
    )


# =========================================================
# العودة للرئيسية
# =========================================================

@dp.callback_query(
    F.data == "back_home"
)
async def back_home(
    callback: CallbackQuery
):

    fake_message = callback.message

    fake_message.from_user = (
        callback.from_user
    )


    await start_handler(
        fake_message
    )


    await callback.answer()


# =========================================================
# MAIN
# =========================================================

async def main():

    await resume_all_active_bots()


    logger.info(
        "Ultimate Production Bot Maker "
        "started successfully!"
    )


    await dp.start_polling(
        bot
    )


# =========================================================
# التشغيل
# =========================================================

if __name__ == "__main__":

    asyncio.run(
        main()
    )
