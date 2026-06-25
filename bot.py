import os
import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
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
    c.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id TEXT NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            admin_id INTEGER PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


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


def update_file_in_db(row_id: int, new_name: str, new_file_id: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE files SET file_name = ?, file_id = ? WHERE id = ?", (new_name, new_file_id, row_id))
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
    c.execute("SELECT id, file_name FROM files WHERE file_name LIKE ? LIMIT 15", (f"%{query_text}%",))
    rows = c.fetchall()
    conn.close()
    return rows


def get_file_info_by_row_id(row_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT file_id, file_name FROM files WHERE id = ?", (row_id,))
    row = c.fetchone()
    conn.close()
    return row


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
        logger.error(f"خطأ: {e}")
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
ALL_SECTIONS = list(SUBJECTS)


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📖 المواد الدراسية", callback_data="subjects")],
        [InlineKeyboardButton("🔍 بحث عن ملف أو رابط", callback_data="user_search_click")],
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


def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ إضافة ملف، صورة أو رابط", callback_data="admin_add_info")],
        [InlineKeyboardButton("📝 إدارة وتعديل المحتوى", callback_data="admin_edit_files_select")],
        [InlineKeyboardButton("🗑 حذف محتوى", callback_data="admin_delete_select")],
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


# دالة ذكية لإرسال أي نوع من المحتوى (ملف، صورة، فيديو، رابط)
async def send_stored_file(context, chat_id, file_id, file_name=None):
    if file_id.startswith("http"):
        name_part = f"🔗 *{file_name}*\n" if file_name and file_name != "رابط مفيد" else "🔗 "
        await context.bot.send_message(chat_id=chat_id, text=f"{name_part}{file_id}", parse_mode="Markdown")
    else:
        try:
            await context.bot.send_document(chat_id=chat_id, document=file_id)
        except Exception:
            try:
                await context.bot.send_photo(chat_id=chat_id, photo=file_id)
            except Exception:
                try:
                    await context.bot.send_video(chat_id=chat_id, video=file_id)
                except Exception as e:
                    logger.error(f"Error sending file/media: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    context.user_data.clear()
    
    temp_msg = await update.message.reply_text("🔄 جاري التحديث...", reply_markup=ReplyKeyboardRemove())
    await temp_msg.delete()
    
    text = (
        f"👋 أهلاً {user.first_name}!\n\n"
        "🎓 *تمريض مكثف - مايو 2026*\n\n"
        "مرحباً بك في بوت المواد الدراسية.\n"
        "اختر من القائمة أدناه، أو ببساطة **اكتب اسم أي ملف/رابط للبحث عنه فوراً**:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not is_admin(user.id):
        await update.message.reply_text("⛔ هذا الأمر للمشرف فقط.")
        return
    context.user_data.clear()
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

    if data == "subjects":
        await query.edit_message_text("📖 *المواد الدراسية*\n\nاختر المادة:", parse_mode="Markdown", reply_markup=subjects_keyboard())

    elif data.startswith("subject_"):
        sid = data.split("_")[1]
        subject_name = next((name for s_id, name in SUBJECTS if s_id == sid), "غير معروف")
        files = get_files(sid)
        if files:
            text = f"📂 *{subject_name}*\n\n📎 يحتوي على {len(files)} ملف/محتوى — يتم الإرسال..."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="subjects")]]))
            for file_id, file_name in files:
                await send_stored_file(context, query.message.chat_id, file_id, file_name)
        else:
            text = f"📂 *{subject_name}*\n\n⚠️ لا توجد ملفات في هذه المادة بعد."
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="subjects")]]))

    elif data == "back_main":
        await query.edit_message_text("🎓 *تمريض مكثف - مايو 2026*\n\nاختر من القائمة أو ابحث بكتابة الاسم:", parse_mode="Markdown", reply_markup=main_menu_keyboard())

    elif data == "user_search_click":
        await query.edit_message_text(
            "🔍 *البحث الذكي*\n\nببساطة، قم بإرسال اسم الملف أو الرابط أو جزء منه كرسالة نصية الآن.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="back_main")]])
        )

    elif data.startswith("send_file_"):
        row_id = int(data.replace("send_file_", ""))
        file_info = get_file_info_by_row_id(row_id)
        if file_info:
            await send_stored_file(context, query.message.chat_id, file_info[0], file_info[1])
        else:
            await query.answer("⚠️ المحتوى غير موجود بقاعدة البيانات.", show_alert=True)

    # --- لوحة تحكم المشرف ---
    elif data == "admin_panel":
        if not is_admin(user_id): return
        context.user_data.clear() 
        await query.edit_message_text("🔧 *لوحة المشرف*\n\nاختر ما تريد:", parse_mode="Markdown", reply_markup=admin_panel_keyboard())

    elif data == "admin_add_info":
        if not is_admin(user_id): return
        await query.edit_message_text("➕ *إضافة محتوى*\n\nأرسل للمحادثة أي (ملف، صورة، فيديو، أو رابط يبدأ بـ http) وسيطلب منك البوت تحديد قسمه فوراً.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]))

    elif data == "admin_stats":
        if not is_admin(user_id): return
        lines = ["📊 *إحصائيات المحتوى*\n"]
        total = 0
        for sid, name in ALL_SECTIONS:
            c = count_files(sid)
            total += c
            lines.append(f"• {name}: {c}")
        lines.append(f"\n📦 الإجمالي: {total} ملف/رابط")
        await query.edit_message_text("\n".join(lines), parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]))

    # --- تعديل المحتوى ونقله ---
    elif data == "admin_edit_files_select":
        if not is_admin(user_id): return
        await query.edit_message_text("📝 *إدارة وتعديل المحتوى*\n\nاختر القسم الذي يحتوي على المادة المراد تعديلها:", parse_mode="Markdown", reply_markup=admin_sections_keyboard("admin_edsec"))

    elif data.startswith("admin_edsec_"):
        if not is_admin(user_id): return
        sid = data.replace("admin_edsec_", "")
        files = get_all_files_with_ids(sid)
        if not files:
            await query.answer("⚠️ لا يوجد محتوى في هذا القسم.", show_alert=True)
            return
        keyboard = []
        for row_id, file_id, file_name in files:
            icon = "🔗" if file_id.startswith("http") else "⚙️"
            keyboard.append([InlineKeyboardButton(f"{icon} {file_name}", callback_data=f"file_manage_{row_id}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_edit_files_select")])
        await query.edit_message_text("⚙️ اختر المحتوى المُراد تعديل اسمه أو نقله:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("file_manage_"):
        if not is_admin(user_id): return
        row_id = int(data.replace("file_manage_", ""))
        keyboard = [
            [InlineKeyboardButton("✏️ تعديل الاسم/العنوان", callback_data=f"file_rename_req_{row_id}")],
            [InlineKeyboardButton("📦 النقل لقسم آخر", callback_data=f"file_move_req_{row_id}")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_edit_files_select")]
        ]
        await query.edit_message_text("⚙️ *خيارات التحكم:*\n\nماذا تريد أن تفعل بالمحتوى المحدد؟", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("file_rename_req_"):
        if not is_admin(user_id): return
        row_id = int(data.replace("file_rename_req_", ""))
        context.user_data["waiting_for_new_filename"] = True
        context.user_data["edit_file_row_id"] = row_id
        await query.edit_message_text("✏️ *تعديل الاسم*\n\nمن فضلك أرسل الاسم الجديد الآن كرسالة نصية هنا.\n(للملفات: سيقوم البوت بإعادة الرفع بالاسم الجديد السحري 🪄)", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")]]))

    elif data.startswith("file_move_req_"):
        if not is_admin(user_id): return
        row_id = int(data.replace("file_move_req_", ""))
        keyboard = []
        for sid, name in ALL_SECTIONS:
            keyboard.append([InlineKeyboardButton(f"➡️ {name}", callback_data=f"file_move_to_{row_id}_{sid}")])
        keyboard.append([InlineKeyboardButton("❌ إلغاء", callback_data="admin_panel")])
        await query.edit_message_text("📦 *نقل المحتوى*\n\nاختر القسم الجديد:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("file_move_to_"):
        if not is_admin(user_id): return
        parts = data.replace("file_move_to_", "").split("_", 1)
        row_id = int(parts[0])
        new_sid = parts[1]
        move_file_in_db(row_id, new_sid)
        target_name = next((name for s_id, name in ALL_SECTIONS if s_id == new_sid), "غير معروف")
        await query.edit_message_text(f"✅ تم النقل بنجاح إلى قسم: *{target_name}*.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة المشرف", callback_data="admin_panel")]]))

    # --- الحذف ---
    elif data == "admin_delete_select":
        if not is_admin(user_id): return
        await query.edit_message_text("🗑 *حذف محتوى*\n\nاختر القسم:", parse_mode="Markdown", reply_markup=admin_sections_keyboard("admin_delsec"))

    elif data.startswith("admin_delsec_"):
        if not is_admin(user_id): return
        sid = data.replace("admin_delsec_", "")
        section_name = next((name for s_id, name in ALL_SECTIONS if s_id == sid), "غير معروف")
        files = get_all_files_with_ids(sid)
        if not files:
            await query.answer("لا يوجد محتوى للحذف.", show_alert=True)
            return
        keyboard = []
        for row_id, file_id, file_name in files:
            keyboard.append([InlineKeyboardButton(f"🗑 {file_name or 'ملف'}", callback_data=f"admin_del_file_{row_id}_{sid}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_delete_select")])
        await query.edit_message_text(f"🗑 *حذف من: {section_name}*\n\nاختر المحتوى للحذف الدائم:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_del_file_"):
        if not is_admin(user_id): return
        parts = data.replace("admin_del_file_", "").split("_", 1)
        row_id = int(parts[0])
        sid = parts[1]
        delete_file_by_id(row_id)
        section_name = next((name for s_id, name in ALL_SECTIONS if s_id == sid), "غير معروف")
        remaining = count_files(sid)
        await query.edit_message_text(f"✅ تم الحذف بنجاح.\n📊 المتبقي في القسم: {remaining}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لوحة المشرف", callback_data="admin_panel")]]))

    # --- إدارة المشرفين ---
    elif data == "admin_manage_users":
        if not is_admin(user_id): return
        admins = get_all_admins()
        text = "👥 *إدارة مشرفي البوت*\n\nالمشرفون الحاليون:\n"
        for idx, adm_id in enumerate(admins, 1):
            tag = " [المالك]" if adm_id == PRIMARY_ADMIN else ""
            text += f"{idx}. `{adm_id}`{tag}\n"
        keyboard = [
            [InlineKeyboardButton("➕ إضافة مشرف", callback_data="admin_add_new_click")],
            [InlineKeyboardButton("🗑 حذف مشرف", callback_data="admin_remove_select")],
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]
        ]
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_add_new_click":
        if not is_admin(user_id): return
        context.user_data["waiting_for_admin_id"] = True
        await query.edit_message_text("📥 *إضافة مشرف جديد*\n\nأرسل الـ **ID** كرسالة نصية الآن.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data="admin_manage_users")]]))

    elif data == "admin_remove_select":
        if not is_admin(user_id): return
        admins = get_all_admins()
        sub_admins = [a for a in admins if a != PRIMARY_ADMIN]
        if not sub_admins:
            await query.answer("⚠️ لا يوجد مشرفون لحذفهم.", show_alert=True)
            return
        keyboard = []
        for adm_id in sub_admins:
            keyboard.append([InlineKeyboardButton(f"❌ حذف {adm_id}", callback_data=f"admin_confirm_del_{adm_id}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_users")])
        await query.edit_message_text("🗑 *اختر المشرف المراد حذفه:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("admin_confirm_del_"):
        if not is_admin(user_id): return
        target_id = int(data.replace("admin_confirm_del_", ""))
        remove_admin(target_id)
        await query.edit_message_text("✅ تم إزالة المشرف بنجاح.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_users")]]))


# دالة شاملة لاستقبال الميديا والملفات
async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("⛔ عذراً، الرفع متاح للمشرف فقط.")
        return

    msg = update.message
    if msg.document:
        file_id = msg.document.file_id
        file_name = msg.document.file_name or "ملف_بدون_اسم"
    elif msg.photo:
        file_id = msg.photo[-1].file_id # أعلى جودة
        file_name = f"صورة_{file_id[-6:]}.jpg"
    elif msg.video:
        file_id = msg.video.file_id
        file_name = msg.video.file_name or f"فيديو_{file_id[-6:]}.mp4"
    else:
        return

    context.user_data["pending_file_id"] = file_id
    context.user_data["pending_file_name"] = file_name

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

    await update.message.reply_text(f"📎 استلمت الميديا/الملف: *{file_name}*\n\nاختر القسم لحفظه فيه:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


async def save_file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "cancel_save":
        context.user_data.clear()
        await query.edit_message_text("❌ تم إلغاء عملية الحفظ.")
        return

    if data.startswith("save_"):
        sid = data.split("_", 1)[1]
        section_name = next((name for s_id, name in ALL_SECTIONS if s_id == sid), "غير معروف")
        file_id = context.user_data.get("pending_file_id")
        file_name = context.user_data.get("pending_file_name", "محتوى")

        if not file_id:
            await query.edit_message_text("⚠️ انتهت صلاحية الجلسة، أرسل المحتوى مجدداً.")
            return

        save_file(sid, file_id, file_name)
        context.user_data.clear()
        await query.edit_message_text(f"✅ تم الحفظ بنجاح في قسم *{section_name}*.", parse_mode="Markdown")


async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_admin(user_id):
        # ميزة حفظ الروابط للمشرفين
        if text.startswith("http://") or text.startswith("https://"):
            context.user_data["pending_file_id"] = text
            context.user_data["pending_file_name"] = "رابط مفيد"
            
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
            
            await update.message.reply_text(f"🔗 استلمت الرابط.\n\nاختر القسم لحفظه فيه:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # التعديل السحري للاسم
        if context.user_data.get("waiting_for_new_filename"):
            row_id = context.user_data.get("edit_file_row_id")
            if row_id is not None:
                new_name = text
                file_info = get_file_info_by_row_id(row_id)
                
                if file_info:
                    old_file_id, old_file_name = file_info
                    
                    if old_file_id.startswith("http"):
                        # الروابط نغير اسمها فقط في قاعدة البيانات
                        update_file_name_in_db(row_id, new_name)
                        await update.message.reply_text(
                            f"✅ تم تعديل عنوان الرابط بنجاح إلى:\n*\"{new_name}\"*",
                            parse_mode="Markdown",
                            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="admin_panel")]])
                        )
                    else:
                        # للملفات والصور والفيديو نقوم بإعادة الرفع
                        _, ext = os.path.splitext(old_file_name)
                        if not ext:
                            ext = ".pdf" 
                        if not new_name.lower().endswith(ext.lower()):
                            new_name += ext

                        processing_msg = await update.message.reply_text("⏳ جاري سحب الملف وإعادة تسميته ورفعه... قد يستغرق ثواني.")

                        try:
                            tg_file = await context.bot.get_file(old_file_id)
                            downloaded_bytes = await tg_file.download_as_bytearray()

                            sent_msg = await update.message.reply_document(
                                document=downloaded_bytes,
                                filename=new_name,
                                caption=f"✅ النسخة الجديدة بالاسم: {new_name}"
                            )
                            new_file_id = sent_msg.document.file_id
                            update_file_in_db(row_id, new_name, new_file_id)

                            await processing_msg.edit_text(
                                f"✅ اكتمل السحر! تم تغيير الاسم الفعلي إلى:\n*\"{new_name}\"*",
                                parse_mode="Markdown",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="admin_panel")]])
                            )
                        except Exception as e:
                            logger.error(f"خطأ في تغيير اسم الملف: {e}")
                            await processing_msg.edit_text(
                                "⚠️ عذراً، لم أتمكن من إعادة رفع الملف (قد يكون حجمه كبيراً جداً بالنسبة لقيود التليجرام).\n\n"
                                "💡 **نصيحة:** قم بتعديل اسمه من هاتفك وارفعه كملف جديد.",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 العودة", callback_data="admin_panel")]])
                            )
            context.user_data.clear()
            return

        # إضافة مشرفين
        if context.user_data.get("waiting_for_admin_id"):
            if not text.isdigit():
                await update.message.reply_text("⚠️ يرجى إرسال الـ ID كأرقام فقط.")
                return
            new_admin_id = int(text)
            if add_admin(new_admin_id):
                await update.message.reply_text(f"✅ تم إضافة المشرف `{new_admin_id}` بنجاح.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_manage_users")]]))
            context.user_data.clear()
            return

    # --- 2. البحث الافتراضي المباشر ---
    results = search_files_by_name(text)
    if not results:
        await update.message.reply_text(f"🔍 لم أجد أي محتوى يحتوي على الاسم: *\"{text}\"* 😢\n\nتأكد من الحروف.", parse_mode="Markdown")
        return
    
    keyboard = []
    for row_id, file_name in results:
        keyboard.append([InlineKeyboardButton(f"📄 {file_name}", callback_data=f"send_file_{row_id}")])
    keyboard.append([InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="back_main")])
    
    await update.message.reply_text(f"🔍 *نتائج البحث عن:* \"{text}\"\n\nاضغط على المحتوى للتحميل:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


def main():
    if not TOKEN: return
    init_db()

    async def post_init(application: Application):
        from telegram import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat
        await application.bot.set_my_commands([BotCommand("start", "🏠 القائمة الرئيسية")], scope=BotCommandScopeAllPrivateChats())

        admin_cmds = [BotCommand("start", "🏠 الرئيسية"), BotCommand("admin", "🔧 لوحة المشرف")]
        admins = get_all_admins()
        for admin_id in admins:
            try:
                await application.bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception: pass

    app = Application.builder().token(TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CallbackQueryHandler(save_file_handler, pattern=r"^save_|^cancel_save$"))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # التقاط كل أنواع الملفات والميديا!
    app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO, handle_media))
    
    # التقاط الروابط والبحث
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
