import os
import sqlite3
import telebot
from telebot import types

# 1. إعداد البوت والمعلومات الأساسية
BOT_TOKEN = os.getenv("BOT_TOKEN")  # يقرأ التوكن من متغيرات Railway البيئية
ADMIN_ID = 123456789  # ⚠️ استبدل هذا الرقم بـ ID حسابك الخاص على تليجرام

bot = telebot.TeleBot(BOT_TOKEN)

# 2. إعداد قاعدة البيانات المتقدمة
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

# إنشاء الجداول الأساسية
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS folders (id INTEGER PRIMARY KEY AUTOINCREMENT, term INTEGER, name TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY AUTOINCREMENT, folder_id INTEGER, name TEXT, file_id TEXT, file_type TEXT)''')
conn.commit()

# دمج مواد الترم الأول تلقائياً عند أول تشغيل للبوت إذا كانت فارغة
cursor.execute("SELECT COUNT(*) FROM folders WHERE term = 1")
if cursor.fetchone()[0] == 0:
    default_term1_subjects = ["تشريح (Anatomy)", "وظائف أعضاء (Physiology)", "أساسيات التمريض", "المصطلحات الطبية"]
    for subject in default_term1_subjects:
        cursor.execute("INSERT INTO folders (term, name) VALUES (?, ?)", (1, subject))
    conn.commit()


# 3. لوحات التحكم والأزرار (Keyboards)

def main_menu_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [types.KeyboardButton(f"الترم {i}") for i in ["الأول", "الثاني", "الثالث", "الرابع", "الخامس", "السادس"]]
    markup.add(*buttons)
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("⚙️ لوحة المشرف"))
    return markup

def admin_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("➕ إضافة مادة"), 
        types.KeyboardButton("❌ حذف مادة"),
        types.KeyboardButton("📤 إضافة ملف/محاضرة"),
        types.KeyboardButton("📢 إذاعة إعلان للطلاب"),
        types.KeyboardButton("📊 إحصائيات الطلاب"),
        types.KeyboardButton("🔙 العودة للقائمة الرئيسية")
    )
    return markup

def terms_inline_keyboard(action_type):
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = [types.InlineKeyboardButton(f"الترم {i}", callback_data=f"{action_type}_{i}") for i in range(1, 7)]
    markup.add(*buttons)
    return markup


# 4. معالجة الأوامر والرسائل النصية للطلاب

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    # حفظ المستخدم في قاعدة البيانات للإحصائيات والتعميم
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
    except Exception as e:
        print(f"Error saving user: {e}")

    welcome_text = "🎯 *أهلاً بك في بوت المواد الدراسية التمريضية.*\n\nالرجاء اختيار الترم لعرض المواد والمحاضرات المتوفرة:"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_keyboard(user_id), parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    text = message.text

    term_mapping = {"الترم الأول": 1, "الترم الثاني": 2, "الترم الثالث": 3, "الترم الرابع": 4, "الترم الخامس": 5, "الترم السادس": 6}
    
    if text in term_mapping:
        term_num = term_mapping[text]
        cursor.execute("SELECT id, name FROM folders WHERE term = ?", (term_num,))
        subjects = cursor.fetchall()
        
        if subjects:
            markup = types.InlineKeyboardMarkup(row_width=1)
            for sub_id, sub_name in subjects:
                markup.add(types.InlineKeyboardButton(f"📁 {sub_name}", callback_data=f"viewfolder_{sub_id}"))
            bot.send_message(message.chat.id, f"📚 *اختر المادة من {text} لتصفح ملفاتها:*", reply_markup=markup, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, f"ℹ️ لا توجد مواد مضافة في {text} حالياً.")

    # أقسام لوحة تحكم الأدمن
    elif user_id == ADMIN_ID:
        if text == "⚙️ لوحة المشرف":
            bot.send_message(message.chat.id, "🎯 مرحباً بك في لوحة الإدارة المتقدمة:", reply_markup=admin_keyboard())
        elif text == "🔙 العودة للقائمة الرئيسية":
            bot.send_message(message.chat.id, "تمت العودة بنجاح.", reply_markup=main_menu_keyboard(user_id))
        elif text == "➕ إضافة مادة":
            bot.send_message(message.chat.id, "اختر الترم المُراد إضافة المادة إليه:", reply_markup=terms_inline_keyboard("add"))
        elif text == "❌ حذف مادة":
            bot.send_message(message.chat.id, "اختر الترم المراد حذف المادة منه:", reply_markup=terms_inline_keyboard("del"))
        elif text == "📤 إضافة ملف/محاضرة":
            bot.send_message(message.chat.id, "اختر الترم الذي تقع فيه المادة المستهدفة:", reply_markup=terms_inline_keyboard("addfile"))
        elif text == "📊 إحصائيات الطلاب":
            cursor.execute("SELECT COUNT(*) FROM users")
            count = cursor.fetchone()[0]
            bot.send_message(message.chat.id, f"📊 *عدد الطلاب المشتركين في البوت حالياً:* `{count}` طالب.", parse_mode="Markdown")
        elif text == "📢 إذاعة إعلان للطلاب":
            msg = bot.send_message(message.chat.id, "✍️ أرسل الآن نص الإعلان أو الرسالة التي تريد إرسالها لجميع الطلاب:")
            bot.register_next_step_handler(msg, broadcast_to_all)


# 5. معالجة أزرار التفاعل الـ Inline (Callbacks)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data.split('_')
    action = data[0]

    # --- قسم تصفح الطلاب للملفات ---
    if action == "viewfolder":
        folder_id = int(data[1])
        cursor.execute("SELECT name, file_id, file_type FROM files WHERE folder_id = ?", (folder_id,))
        all_files = cursor.fetchall()
        
        if not all_files:
            bot.answer_callback_query(call.id, "ℹ️ هذا المجلد فارغ لا يحتوي على ملفات حالياً.", show_alert=True)
            return
        
        bot.answer_callback_query(call.id, "جاري تحميل الملفات...")
        for name, f_id, f_type in all_files:
            if f_type == "text":
                bot.send_message(call.message.chat.id, f"🔗 *{name}*", parse_mode="Markdown")
            elif f_type == "document":
                bot.send_document(call.message.chat.id, f_id, caption=f"📄 {name}")
            elif f_type == "photo":
                bot.send_photo(call.message.chat.id, f_id, caption=f"🖼️ {name}")
            elif f_type == "audio":
                bot.send_audio(call.message.chat.id, f_id, caption=f"🎵 {name}")

    # --- صلاحيات المشرف فقط ---
    elif user_id == ADMIN_ID:
        term_num = int(data[1]) if len(data) > 1 and data[1].isdigit() else None

        if action == "add":
            msg = bot.edit_message_text(f"✍️ أرسل اسم المادة الجديد لإضافته إلى *الترم {term_num}*:", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            bot.register_next_step_handler(msg, save_new_folder, term_num)
            
        elif action == "del":
            cursor.execute("SELECT id, name FROM folders WHERE term = ?", (term_num,))
            subjects = cursor.fetchall()
            if not subjects:
                bot.edit_message_text(f"ℹ️ لا توجد مواد في الترم {term_num} لحذفها.", call.message.chat.id, call.message.message_id)
                return
            markup = types.InlineKeyboardMarkup(row_width=1)
            for sub_id, sub_name in subjects:
                markup.add(types.InlineKeyboardButton(f"🗑️ {sub_name}", callback_data=f"confirmdel_{sub_id}"))
            bot.edit_message_text(f"🗑️ اختر المادة المراد حذفها نهائياً:", call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif action == "confirmdel":
            sub_id = int(data[1])
            cursor.execute("DELETE FROM folders WHERE id = ?", (sub_id,))
            cursor.execute("DELETE FROM files WHERE folder_id = ?", (sub_id,)) # حذف ملفات المادة أيضاً حماية للمساحة
            conn.commit()
            bot.edit_message_text("✅ تم حذف المادة وجميع محتوياتها بنجاح.", call.message.chat.id, call.message.message_id)

        elif action == "addfile":
            cursor.execute("SELECT id, name FROM folders WHERE term = ?", (term_num,))
            subjects = cursor.fetchall()
            if not subjects:
                bot.edit_message_text(f"⚠️ لا توجد مواد في هذا الترم، قم بإضافة مادة أولاً.", call.message.chat.id, call.message.message_id)
                return
            markup = types.InlineKeyboardMarkup(row_width=1)
            for sub_id, sub_name in subjects:
                markup.add(types.InlineKeyboardButton(f"📁 {sub_name}", callback_data=f"selectforfile_{sub_id}"))
            bot.edit_message_text("🎯 اختر المادة المُراد رفع الملف بداخلها:", call.message.chat.id, call.message.message_id, reply_markup=markup)

        elif action == "selectforfile":
            folder_id = int(data[1])
            msg = bot.edit_message_text("📥 *قم بإرسال الملف الآن* (PDF، صورة، صوت، أو رابط نصي):\n\n⚠️ *ملاحظة:* إذا كان ملفاً أو صورة، اكتب اسم المحاضرة في وصف الملف (Caption) قبل الإرسال.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            bot.register_next_step_handler(msg, save_file_to_db, folder_id)


# 6. دوال استقبال البيانات المتقدمة (Next Step Handlers)

def save_new_folder(message, term_num):
    folder_name = message.text.strip() if message.text else ""
    if folder_name == "" or folder_name.startswith('/') or "العودة" in folder_name:
        bot.send_message(message.chat.id, "❌ تم إلغاء العملية.", reply_markup=admin_keyboard())
        return
    cursor.execute("INSERT INTO folders (term, name) VALUES (?, ?)", (term_num, folder_name))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ تم حفظ مادة: *{folder_name}* بالترم {term_num}.", reply_markup=admin_keyboard(), parse_mode="Markdown")

def save_file_to_db(message, folder_id):
    file_id = None
    file_type = None
    file_name = "ملف غير مسمى"

    if message.document:
        file_id = message.document.file_id
        file_type = "document"
        file_name = message.caption if message.caption else message.document.file_name
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_type = "photo"
        file_name = message.caption if message.caption else "صورة مرفقة"
    elif message.audio or message.voice:
        file_id = message.audio.file_id if message.audio else message.voice.file_id
        file_type = "audio"
        file_name = message.caption if message.caption else "تسجيل صوتي"
    elif message.text and not message.text.startswith('/'):
        file_id = "none"
        file_type = "text"
        file_name = message.text

    if not file_type:
        bot.send_message(message.chat.id, "❌ صيغة غير مدعومة، تم إلغاء الرفع.", reply_markup=admin_keyboard())
        return

    cursor.execute("INSERT INTO files (folder_id, name, file_id, file_type) VALUES (?, ?, ?, ?)", (folder_id, file_name, file_id, file_type))
    conn.commit()
    bot.send_message(message.chat.id, f"✅ تم رفع وإضافة *({file_name})* بنجاح داخل المادة المحددة.", reply_markup=admin_keyboard(), parse_mode="Markdown")

def broadcast_to_all(message):
    if not message.text or message.text.startswith('/'):
        bot.send_message(message.chat.id, "❌ تم إلغاء الإذاعة.", reply_markup=admin_keyboard())
        return
    
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    
    bot.send_message(message.chat.id, f"📢 جاري بدء إرسال الإعلان إلى {len(users)} طالب...")
    
    success_count = 0
    for user in users:
        try:
            bot.send_message(user[0], f"📢 *إعلان مهم من إدارة البوت:*\n\n{message.text}", parse_mode="Markdown")
            success_count += 1
        except Exception:
            continue  # تخطي الحسابات المحظورة أو المعطلة
            
    bot.send_message(message.chat.id, f"✅ تم اكتمال الإذاعة بنجاح ووصلت لـ {success_count} طالب فعّال.", reply_markup=admin_keyboard())


if __name__ == '__main__':
    print("🚀 البوت الذكي والجديد يعمل الآن بأعلى كفاءة...")
    bot.infinity_polling()
