import os
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DB_PATH = os.path.join(os.path.dirname(__file__), "files.db")

# المشرف الأساسي (المالك) الذي لا يمكن حذفه أبداً من البوت
PRIMARY_ADMIN = 7351394218


def is_admin(user_id: int) -> bool:
    if user_id == PRIMARY_ADMIN:
        return True
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM admins WHERE admin_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row is not None


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # جدول الملفات
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # جدول المشرفين
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info("✅ قاعدة البيانات جاهزة ومحدثة")


def get_files(subject_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT file_id, file_name FROM files WHERE subject_id = ? ORDER BY added_at", (subject_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def save_file(subject_id: str, file_id: str, file_name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO files (subject_id, file_id, file_name) VALUES (?, ?, ?)",
        (subject_id, file_id, file_name)
    )
    conn.commit()
    conn.close()


def count_files(subject_id: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM files WHERE subject_id = ?", (subject_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def get_all_files_with_ids(subject_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, file_id, file_name FROM files WHERE subject_id = ? ORDER BY added_at", (subject_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def delete_file_by_id(row_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM files WHERE id = ?", (row_id,))
    conn.commit()
    conn.close()


def update_file_name_in_db(row_id: int, new_name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE files SET file_name = ? WHERE id = ?", (new_name, row_id))
    conn.commit()
    conn.close()


def move_file_in_db(row_id: int, new_subject_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE files SET subject_id = ? WHERE id = ?", (new_subject_id, row_id))
    conn.commit()
    conn.close()


def search_files_by_name(query_text: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT file_id, file_name FROM files WHERE file_name LIKE ? LIMIT 10", (f"%{query_text}%",))
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_admins():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT admin_id FROM admins")
    rows = c.fetchall()
    conn.close()
    admins_list = [PRIMARY_ADMIN] + [row[0] for row in rows if row[0] != PRIMARY_ADMIN]
    return admins_list


def add_admin(admin_id: int) -> bool:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO admins (admin_id) VALUES (?)", (admin_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"خطأ أثناء إضافة مشرف: {e}")
        return False


def remove_admin(admin_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM admins WHERE admin_id = ?", (admin_id,))
    conn.commit()
    conn.close()


SUBJECTS = [
    ("1", "💊 Medical Terminology"),
    ("2", "🫀 Anatomy"),
    ("3", "🧪 Biochemistry"),
    ("4", "🔡 English"),
    ("5", "🔬 Physiology"),
    ("6", "🦠 Microbiology"),
    ("7", "📊 Biostatistics"),
    ("8", "🧬 Biological"),
]

INTRO_SUBJECT_ID = "0"
ALL_SECTIONS = [("0", "📚 القسم التمهيدي")] + list(SUBJECTS)


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📚 القسم التمهيدي", callback_data="intro")],
        [InlineKeyboardButton("📖 المواد الدراسية", callback_data="subjects")],
        [InlineKeyboardButton("🔍 بحث عن ملف", callback_data="user_search_click")],
    ]
    return InlineKeyboardMarkup(keyboard)


def subjects_keyboard():
    keyboard = []
    for sid, name in SUBJECTS:
        count = count_files(sid)
        label = f"{name}  ({count})" if count > 0 else name
        keyboard.append([InlineKeyboardButton(label, callback_data=f"subject_{sid}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_main")])
    return InlineKeyboardMarkup(keyboard)


def back_keyboard(back_target="subjects"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 رجوع", callback_data=f"back_{back_target}")]
    ])


def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ إضافة ملفات", callback_data="admin_add_info")],
        [InlineKeyboardButton("📝 إدارة وتعديل الملفات", callback_data="admin_edit_files_select")],
        [InlineKeyboardButton("🗑 حذف ملف", callback_data="admin_delete_select")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 إدارة المشرفين", callback_data="admin_manage_users")],
        [InlineKeyboardButton("🔙 رجوع للقائمة", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_sections_keyboard(prefix: str):
    keyboard = []
    for sid, name in ALL_SECTIONS:
        count = count_files(sid)
        label = f"{name} ({count})"
        keyboard.append([InlineKeyboardButton(label, callback_data=f"{prefix}_{sid}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    for key in list(context.user_data.keys()):
        context.user_data.pop(key, None)
    
    text = (
        f"👋 أهلاً {user.first_name}!\n\n"
        "🎓 *تمريض مكثف - مايو 2026*\n\n"
        "مرحباً بك في بوت المواد الدراسية.\n"
        "اختر من القائمة أدناه:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ هذا الأمر للمشرف فقط.")
        return
    for key in list(context.user_data.keys()):
        context.user_data.pop(key, None)
    await update.message.reply_text(
        "🔧 *لوحة المشرف*\n\nمرحباً بك يا مشرف! اختر ما تريد:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    # تنظيف مؤقت للحالات عند الضغط على أزرار أخرى
    if data != "admin_add_new_click":
        context.user_data.pop("waiting_for_admin_id", None)
    if data != "user_search_click":
        context.user_data.pop("waiting_for_search_query", None)

    if data == "intro":
        files = get_files(INTRO_SUBJECT_ID)
        if files:
            text = f"📚 *القسم التمهيدي*\n\n📂 يحتوي على {len(files)} ملف — يتم الإرسال..."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard("main"))
            for file_id, file_name in files:
                try:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=file_id)
                except Exception as e:
                    logger.error(f"خطأ في إرسال الملف: {e}")
        else:
            text = "📚 *القسم التمهيدي*\n\n⚠️ لم يتم رفع ملفات القسم التمهيدي بعد."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard("main"))

    elif data == "subjects":
        await query.edit_message_text(
            "📖 *المواد الدراسية*\n\nاختر المادة:",
            parse_mode="Markdown",
            reply_markup=subjects_keyboard()
        )

    elif data.startswith("subject_"):
        sid = data.split("_")[1]
        subject_name = next((name for s_id, name in SUBJECTS if s_id == sid), "غير معروف")
        files = get_files(sid)
        if files:
            text = f"📂 *{subject_name}*\n\n📎 يحتوي على {len(files)} ملف — يتم الإرسال..."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard("subjects"))
            for file_id, file_name in files:
                try:
                    await context.bot.send_document(chat_id=query.message.chat_id, document=file_id)
                except Exception as e:
                    logger.error(f"خطأ في إرسال الملف {file_name}: {e}")
        else:
            text = f"📂 *{subject_name}*\n\n⚠️ لا توجد ملفات في هذه المادة بعد."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_keyboard("subjects"))

    elif data == "back_main":
        await query.edit_message_text(
            "🎓 *تمريض مكثف - مايو 2026*\n\nاختر من القائمة:",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

    elif data == "back_subjects":
        await query.edit_message_text(
            "📖 *المواد الدراسية*\n\nاختر المادة:",
            parse_mode="Markdown",
            reply_markup=subjects_keyboard()
        )

    elif data == "user_search_click":
        context.user_data["waiting_for_search_query"] = True
        await query.edit_message_text(
            "🔍 *البحث الذكي عن الملفات*\n\nمن فضلك اكتب اسم الملف أو جزءاً منه وأرسله لي كرسالة نصية الآن.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء وعودة", callback_data="back_main")]])
        )

    elif data.startswith("send_file_"):
        file_id = data.replace("send_file_", "")
        try:
            await context.bot.send_document(chat_id=query.message.chat_id, document=file_id)
        except Exception as e:
            await query.message.reply_text("⚠️ عذراً، تعذر إرسال هذا الملف.")

    # --- إدارة المشرف ولوحة التحكم ---
    elif data == "admin_panel":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح لك.", show_alert=True)
            return
        await query.edit_message_text(
            "🔧 *لوحة المشرف*\n\nاختر ما تريد:",
            parse_mode="Markdown",
            reply_markup=admin_panel_keyboard()
        )

    elif data == "admin_add_info":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح لك.", show_alert=True)
            return
        await query.edit_message_text(
            "➕ *إضافة ملفات*\n\nأرسل أي ملف للمحادثة وسيطلب منك تحديد قسمه فوراً.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )

    elif data == "admin_stats":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح لك.", show_alert=True)
            return
        lines = ["📊 *إحصائيات الملفات*\n"]
        total = 0
        for sid, name in ALL_SECTIONS:
            c = count_files(sid)
            total += c
            lines.append(f"• {name}: {c} ملف")
        lines.append(f"\n📦 الإجمالي: {total} ملف")
        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]])
        )

    # --- نظام تعديل ونقل الملفات الجديد ---
    elif data == "admin_edit_files_select":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح لك.", show_alert=True)
            return
        await query.edit_message_text(
            "📝 *إدارة وتعديل الملفات*\n\nاختر القسم الذي يحتوي على الملفات لتعديلها أو نقلها:",
            parse_mode="Markdown",
            reply_markup=admin_sections_keyboard("admin_edsec")
        )

    elif data.startswith("admin_edsec_"):
        if not is_admin(user_id):
            return
        sid = data.replace("admin_edsec_", "")
        files = get_all_files_with_ids(sid)
        if not files:
            await query.answer("⚠️ لا توجد ملفات في هذا القسم لتعديلها.", show_alert=True)
            return
        keyboard = []
        for row_id, file_id, file_name in files:
            keyboard.append([InlineKeyboardButton(f"⚙️ {file_name}", callback_data=f"file_manage_{row_id}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_edit_files_select")])
        await query.edit_message_text("⚙️ اختر الملف المُراد تعديل اسمه أو نقله:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("file_manage_"):
        if not is_admin(user_id):
            return
        row_id = int(data.replace("file_manage_", ""))
        
        keyboard = [
            [InlineKeyboardButton("✏️ تعديل اسم الملف", callback_data=f"file_rename_req_{row_id}")],
            [InlineKeyboardButton("📦 نقل الملف لقسم آخر", callback_data=f"file_move_req_{row_id}")],
            [InlineKeyboardButton("🔙 رجوع للملفات", callback_data="admin_edit_files_select")]
        ]
        await query.edit_message_text("⚙️ *خيارات التحكم بالملف:*\n\nماذا تريد أن تفعل بالملف المحدد؟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("file_rename_req_"):
        if not is_admin(user_id):
            return
        row_id = int(data.replace("file_rename_req_", ""))
        context.user_data["edit_file_row_id"] = row_id
        context.user_data["waiting_for_new_filename"] = True
        await query.edit_message_text(
            "✏️ *تعديل اسم الملف*\n\nمن فضلك أرسل الاسم الجديد للملف الآن كرسالة نصية هنا.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]])
        )

    elif data.startswith("file_move_req_"):
        if not is_admin(user_id):
            return
        row_id = int(data.replace("file_move_req_", ""))
        keyboard = []
        for sid, name in ALL_SECTIONS:
            keyboard.append([InlineKeyboardButton(f"➡️ إلى: {name}", callback_data=f"file_move_to_{row_id}_{sid}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")])
        await query.edit_message_text("📦 *نقل الملف*\n\nاختر القسم الجديد الذي تود نقل الملف إليه فوراً:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("file_move_to_"):
        if not is_admin(user_id):
            return
        parts = data.replace("file_move_to_", "").split("_", 1)
        row_id = int(parts[0])
        new_sid = parts[1]
        move_file_in_db(row_id, new_sid)
        target_name = next((name for s_id, name in ALL_SECTIONS if s_id == new_sid), "غير معروف")
        await query.edit_message_text(f"✅ تم نقل الملف بنجاح إلى قسم: *{target_name}*.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للوحة المشرف", callback_data="admin_panel")]]))

    # --- نظام الحذف ---
    elif data == "admin_delete_select":
        if not is_admin(user_id):
            await query.answer("⛔ غير مصرح لك.", show_alert=True)
            return
        await query.edit_message_text(
            "🗑 *حذف ملف*\n\nاختر القسم أو المادة:",
            parse_mode="Markdown",
            reply_markup=admin_sections_keyboard("admin_delsec")
        )

    elif data.startswith("admin_delsec_"):
        if not is_admin(user_id):
            return
        sid = data.replace("admin_delsec_", "")
        section_name = next((name for s_id, name in ALL_SECTIONS if s_id == sid), "غير معروف")
        files = get_all_files_with_ids(sid)
        if not files:
            await query.answer("لا توجد ملفات في هذا القسم.", show_alert=True)
            return
        keyboard = []
        for row_id, file_id, file_name in files:
            keyboard.append([InlineKeyboardButton(f"🗑 {file_name or 'ملف'}", callback_data=f"admin_del_file_{row_id}_{sid}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_delete_select")])
        await query.edit_message_text(f"🗑 *حذف من: {section_name}*\n\nاختر الملف للحذف الدائم:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_del_file_"):
        if not is_admin(user_id):
            return
        parts = data.replace("admin_del_file_", "").split("_", 1)
        row_id = int(parts[0])
        sid = parts[1]
        delete_file_by_id(row_id)
        section_name = next((name for s_id, name in ALL_SECTIONS if s_id == sid), "غير معروف")
        remaining = count_files(sid)
        await query.edit_message_text(
            f"✅ تم حذف الملف بنجاح من *{section_name}*.\n📊 المتبقي: {remaining} ملف.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للوحة", callback_data="admin_panel")]])
        )

    # --- إدارة المشرفين عبر البوت ---
    elif data == "admin_manage_users":
        if not is_admin(user_id):
            return
        admins = get_all_admins()
        text = "👥 *إدارة مشرفي البوت*\n\nالمشرفون الحاليون:\n"
        for idx, adm_id in enumerate(admins, 1):
            tag = " [المالك الأساسي]" if adm_id == PRIMARY_ADMIN else ""
            text += f"{idx}. `{adm_id}`{tag}\n"
        keyboard = [
            [InlineKeyboardButton("➕ إضافة مشرف جديد", callback_data="admin_add_new_click")],
            [InlineKeyboardButton("🗑 حذف مشرف", callback_data="admin_remove_select")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_add_new_click":
        if not is_admin(user_id):
            return
        context.user_data["waiting_for_admin_id"] = True
        await query.edit_message_text(
            "📥 *إضافة مشرف جديد*\n\nمن فضلك أرسل الـ **ID** الخاص بالمشرف الجديد كرسالة نصية الآن.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_manage_users")]])
        )

    elif data == "admin_remove_select":
        if not is_admin(user_id):
            return
        admins = get_all_admins()
        sub_admins = [a for a in admins if a != PRIMARY_ADMIN]
        if not sub_admins:
            await query.answer("⚠️ لا يوجد مشرفون مضافون لحذفهم.", show_alert=True)
            return
        keyboard = []
        for adm_id in sub_admins:
            keyboard.append([InlineKeyboardButton(f"❌ حذف {adm_id}", callback_data=f"admin_confirm_del_{adm_id}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_users")])
        await query.edit_message_text("🗑 *اختر المشرف المراد حذفه من البوت:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_confirm_del_"):
        if not is_admin(user_id):
            return
        target_id = int(data.replace("admin_confirm_del_", ""))
        remove_admin(target_id)
        await query.edit_message_text(f"✅ تم إزالة المشرف بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_users")]]))


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ عذراً، رفع الملفات متاح للمشرف فقط.")
        return

    doc = update.message.document
    if not doc:
        return

    context.user_data["pending_file_id"] = doc.file_id
    context.user_data["pending_file_name"] = doc.file_name or "ملف"

    keyboard = []
    row = []
    for sid, name in ALL_SECTIONS:
        row.append(InlineKeyboardButton(name, callback_data=f"save_{sid}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="cancel_save")])

    await update.message.reply_text(
        f"📎 استلمت الملف: *{doc.file_name}*\n\nاختر القسم لحفظه فيه:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 1. حالة البحث للكل
    if context.user_data.get("waiting_for_search_query"):
        search_query = update.message.text.strip()
        context.user_data.pop("waiting_for_search_query", None)
        
        results = search_files_by_name(search_query)
        if not results:
            await update.message.reply_text(
                f"🔍 لم أجد أي ملف يحتوي على الاسم: *\"{search_query}\"* 😢",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
            return
        
        keyboard = []
        for file_id, file_name in results:
            keyboard.append([InlineKeyboardButton(f"📄 {file_name}", callback_data=f"send_file_{file_id}")])
        keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")])
        
        await update.message.reply_text(
            f"🔍 *نتائج البحث عن:* \"{search_query}\"\n\nاضغط على اسم الملف للتحميل المباشر:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # 2. حالات المشرفين الخاصة بالتعديل والإضافة
    if is_admin(user_id):
        # ميزة تعديل اسم الملف
        if context.user_data.get("waiting_for_new_filename"):
            new_name = update.message.text.strip()
            row_id = context.user_data.get("edit_file_row_id")
            
            update_file_name_in_db(row_id, new_name)
            
            context.user_data.pop("waiting_for_new_filename", None)
            context.user_data.pop("edit_file_row_id", None)
            
            await update.message.reply_text(
                f"✅ تم تعديل اسم الملف بنجاح إلى:\n*\"{new_name}\"*",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_panel")]])
            )
            return

        # ميزة إضافة مشرف جديد
        if context.user_data.get("waiting_for_admin_id"):
            text = update.message.text.strip()
            if not text.isdigit():
                await update.message.reply_text("⚠️ يرجى إرسال الـ ID كأرقام فقط.")
                return
            new_admin_id = int(text)
            if add_admin(new_admin_id):
                context.user_data.pop("waiting_for_admin_id", None)
                await update.message.reply_text(f"✅ تم إضافة المشرف `{new_admin_id}` بنجاح.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_users")]]))


async def save_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel_save":
        context.user_data.pop("pending_file_id", None)
        context.user_data.pop("pending_file_name", None)
        await query.edit_message_text("❌ تم إلغاء عملية الحفظ.")
        return

    if data.startswith("save_"):
        sid = data.split("_", 1)[1]
        section_name = next((name for s_id, name in ALL_SECTIONS if s_id == sid), "غير معروف")
        file_id = context.user_data.get("pending_file_id")
        file_name = context.user_data.get("pending_file_name", "ملف")

        if not file_id:
            await query.edit_message_text("⚠️ انتهت صلاحية الجلسة، يرجى إعادة إرسال الملف.")
            return

        save_file(sid, file_id, file_name)
        context.user_data.pop("pending_file_id", None)
        context.user_data.pop("pending_file_name", None)
        total = count_files(sid)
        await query.edit_message_text(f"✅ تم حفظ *{file_name}* في قسم *{section_name}* بنجاح.\n📊 الإجمالي: {total} ملف.", parse_mode="Markdown")


def main():
    if not TOKEN:
        logger.error("لم يتم العثور على TELEGRAM_BOT_TOKEN!")
        return

    init_db()

    async def post_init(application: Application):
        from telegram import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat
        public_commands = [BotCommand("start", "🏠 القائمة الرئيسية")]
        await application.bot.set_my_commands(public_commands, scope=BotCommandScopeAllPrivateChats())

        admin_commands = [
            BotCommand("start", "🏠 القائمة الرئيسية"),
            BotCommand("admin", "🔧 لوحة المشرف"),
        ]
        admins = get_all_admins()
        for admin_id in admins:
            try:
                await application.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception as e:
                pass

    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(save_file_handler, pattern=r"^save_|^cancel_save$"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    logger.info("🤖 البوت يعمل مع كامل الميزات والتنظيف التام...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
