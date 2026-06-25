import os
import sqlite3
import telebot
from telebot import types

# 1. إعداد البوت والمعلومات الأساسية
BOT_TOKEN = os.getenv("BOT_TOKEN")  # سيقرأ التوكن تلقائياً من المتغيرات البيئية في Railway
ADMIN_ID = 123456789  # ⚠️ ضع هنا الـ ID الخاص بحسابك على تليجرام لتفعيل صلاحيات الأدمن

bot = telebot.TeleBot(BOT_TOKEN)

# 2. إعداد قاعدة البيانات وحفظ المواد
conn = sqlite3.connect('bot_database.db', check_same_thread=False)
cursor = conn.cursor()

# إنشاء جدول المجلدات/المواد إذا لم يكن موجوداً
cursor.execute('''
    CREATE TABLE IF NOT EXISTS folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        term INTEGER,
        name TEXT
    )
''')
conn.commit()

# دمج مواد الترم الأول تلقائياً عند أول تشغيل للبوت إذا كانت فارغة
cursor.execute("SELECT COUNT(*) FROM folders WHERE term = 1")
if cursor.fetchone()[0] == 0:
    default_term1_subjects = ["تشريح (Anatomy)", "وظائف أعضاء (Physiology)", "أساسيات التمريض", "المصطلحات الطبية"]
    for subject in default_term1_subjects:
        cursor.execute("INSERT INTO folders (term, name) VALUES (?, ?)", (1, subject))
    conn.commit()


# 3. القوائم ولوحات الأزرار (Keyboards)

def main_menu_keyboard(user_id):
    """القائمة الرئيسية للمستخدمين والأدمن"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton("الترم الأول")
    btn2 = types.KeyboardButton("الترم الثاني")
    btn3 = types.KeyboardButton("الترم الثالث")
    btn4 = types.KeyboardButton("الترم الرابع")
    btn5 = types.KeyboardButton("الترم الخامس")
    btn6 = types.KeyboardButton("الترم السادس")
    
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    # إظهار لوحة التحكم للمشرف فقط
    if user_id == ADMIN_ID:
        admin_btn = types.KeyboardButton("⚙️ لوحة المشرف")
        markup.add(admin_btn)
    return markup

def admin_keyboard():
    """لوحة تحكم الأدمن الخاصة بالإدارة"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    add_btn = types.KeyboardButton("➕ إضافة مجلد (مادة)")
    del_btn = types.KeyboardButton("❌ حذف مجلد (مادة)")
    back_btn = types.KeyboardButton("🔙 العودة للقائمة الرئيسية")
    markup.add(add_btn, del_btn, back_btn)
    return markup

def terms_inline_keyboard(action_type):
    """قائمة اختيار الترم للأدمن لإضافة أو حذف المواد منها"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    # تتيح للأدمن التحكم بالترمات (من الترم 1 إلى الترم 6)
    buttons = [types.InlineKeyboardButton(f"الترم {i}", callback_data=f"{action_type}_{i}") for i in range(1, 7)]
    markup.add(*buttons)
    return markup


# 4. معالجة الأوامر والرسائل النصية

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = "🎯 *أهلاً بك في بوت المواد الدراسية التمريضية.*\n\nالرجاء اختيار الترم من الأزرار بالأسفل لعرض المواد المتاحة:"
    bot.send_message(message.chat.id, welcome_text, reply_markup=main_menu_keyboard(message.from_user.id), parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    user_id = message.from_user.id
    text = message.text

    # خريطة تحويل النصوص إلى أرقام الترمات المقابلة لها
    term_mapping = {
        "الترم الأول": 1, "الترم الثاني": 2, "الترم الثالث": 3,
        "الترم الرابع": 4, "الترم الخامس": 5, "الترم السادس": 6
    }
    
    if text in term_mapping:
        term_num = term_mapping[text]
        cursor.execute("SELECT name FROM folders WHERE term = ?", (term_num,))
        subjects = cursor.fetchall()
        
        if subjects:
            response = f"📚 *المواد المتاحة في {text}:*\n\n"
            for sub in subjects:
                response += f"📁 {sub[0]}\n"
            bot.send_message(message.chat.id, response, parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, f"ℹ️ لا توجد مواد مضافة في {text} حالياً.")

    # الدخول إلى لوحة المشرف للأدمن فقط
    elif text == "⚙️ لوحة المشرف" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "🎯 مرحباً بك في لوحة التحكم الخاصة بالمشرف. اختر الإجراء المطلوب:", reply_markup=admin_keyboard())

    # العودة للقائمة الرئيسية
    elif text == "🔙 العودة للقائمة الرئيسية":
        bot.send_message(message.chat.id, "تمت العودة للقائمة الرئيسية بنجاح.", reply_markup=main_menu_keyboard(user_id))

    # طلب إضافة مادة جديدة
    elif text == "➕ إضافة مجلد (مادة)" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "اختر الترم الذي تريد إضافة المجلد إليه:", reply_markup=terms_inline_keyboard("add"))

    # طلب حذف مادة
    elif text == "❌ حذف مجلد (مادة)" and user_id == ADMIN_ID:
        bot.send_message(message.chat.id, "اختر الترم الذي تريد حذف المجلد منه:", reply_markup=terms_inline_keyboard("del"))


# 5. معالجة أزرار الـ Inline (الضغط على الترمات والقوائم الفرعية)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    if user_id != ADMIN_ID:
        return

    data = call.data.split('_')
    action = data[0]

    # حالة: طلب إضافة مادة لترم معين
    if action == "add":
        term_num = int(data[1])
        msg = bot.edit_message_text(f"✍️ أرسل الآن اسم المجلد (المادة) الجديد لإضافته إلى *الترم {term_num}*:", 
                                    call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        bot.register_next_step_handler(msg, save_new_folder, term_num)
        
    # حالة: عرض قائمة المواد المتوفرة في الترم المختار لحذفها
    elif action == "del":
        term_num = int(data[1])
        cursor.execute("SELECT id, name FROM folders WHERE term = ?", (term_num,))
        subjects = cursor.fetchall()
        
        if not subjects:
            bot.edit_message_text(f"ℹ️ لا توجد مواد في الترم {term_num} لحذفها حالياً.", call.message.chat.id, call.message.message_id)
            return
            
        markup = types.InlineKeyboardMarkup(row_width=1)
        for sub_id, sub_name in subjects:
            markup.add(types.InlineKeyboardButton(f"🗑️ {sub_name}", callback_data=f"confirm_{sub_id}"))
        
        bot.edit_message_text(f"🗑️ اختر المادة التي تريد حذفها نهائياً من الترم {term_num}:", 
                                call.message.chat.id, call.message.message_id, reply_markup=markup)

    # حالة: تأكيد الحذف الفعلي من قاعدة البيانات باستخدام الـ ID الخاص بالمادة
    elif action == "confirm":
        sub_id = int(data[1])
        
        # جلب اسم المادة والترم قبل الحذف لإظهارهما في رسالة النجاح
        cursor.execute("SELECT name, term FROM folders WHERE id = ?", (sub_id,))
        result = cursor.fetchone()
        
        if result:
            sub_name, term_num = result[0], result[1]
            cursor.execute("DELETE FROM folders WHERE id = ?", (sub_id,))
            conn.commit()
            bot.edit_message_text(f"✅ تم حذف المجلد *({sub_name})* من الترم {term_num} بنجاح وتحديث القوائم.", 
                                  call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        else:
            bot.edit_message_text("❌ حدث خطأ، المادة غير موجودة أو تم حذفها مسبقاً.", call.message.chat.id, call.message.message_id)


# 6. وظائف استقبال المدخلات النصية (Next Step Handlers)

def save_new_folder(message, term_num):
    """تلقي اسم المادة الجديدة من الأدمن وحفظها في قاعدة البيانات"""
    folder_name = message.text.strip()
    
    # الحماية من إدخال نصوص فارغة أو أوامر تخريبية أثناء خطوة التسجيل
    if folder_name == "" or folder_name.startswith('/') or folder_name == "🔙 العودة للقائمة الرئيسية":
        bot.send_message(message.chat.id, "❌ عملية إلغاء أو اسم مادة غير صالحة. تم التراجع عن الإضافة.", reply_markup=admin_keyboard())
        return

    # إدخال المادة الجديدة وحفظ التغييرات
    cursor.execute("INSERT INTO folders (term, name) VALUES (?, ?)", (term_num, folder_name))
    conn.commit()
    
    bot.send_message(message.chat.id, f"✅ تم بنجاح إضافة مجلد المادة: *{folder_name}* إلى الترم {term_num}.", 
                     reply_markup=admin_keyboard(), parse_mode="Markdown")


# تشغيل واستمرار استقبال البيانات للبوت دون توقف
if __name__ == '__main__':
    print("🚀 البوت المطور يعمل الآن بكفاءة عالية...")
    bot.infinity_polling()
