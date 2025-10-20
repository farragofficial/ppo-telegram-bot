import time
import json
import base64
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import telebot
import os

# ==== إعدادات البوت ====
TOKEN = "8343868844:AAG5rK_3MflfqxRiBBe7eM4Ux0iXQvBzjrQ"
bot = telebot.TeleBot(TOKEN)
TARGET_URL = "https://ppo.gov.eg/ppo/r/ppoportal/ppoportal/home"
DATA_FILE = "ppo_data.json"

# ==== تحميل البيانات الموجودة أو إنشاء ملف جديد ====
try:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
except:
    saved_data = {}

# ==== دالة فتح الصفحة وضغط زر نيابات المرور ====
def open_page():
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--window-size=1920,1440")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--allow-insecure-localhost")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(TARGET_URL)
    wait = WebDriverWait(driver, 15)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    divs = driver.find_elements(By.CLASS_NAME, "icon-title")
    for div in divs:
        try:
            h5 = div.find_element(By.TAG_NAME, "h5")
            if "نيابات المرور" in h5.text:
                div.click()
                break
        except:
            continue

    time.sleep(3)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    return driver

# ==== ملء الحروف الثلاثة ====
def fill_letters(driver, letters):
    for i, letter in enumerate(letters[:3], start=1):
        input_id = f"P14_LETER_{i}"
        try:
            input_field = driver.find_element(By.ID, input_id)
            input_field.clear()
            input_field.send_keys(letter)
        except Exception as e:
            print(f"خطأ في ملء الخانة {i}: {e}")

# ==== ملء رقم العربية (الخانة الوحيدة للأرقام) ====
def fill_plate_number(driver, plate_number):
    try:
        number_field = driver.find_element(By.ID, "P14_NUMBER_WITH_LETTER")
        number_field.clear()
        number_field.send_keys(plate_number)
    except Exception as e:
        print(f"خطأ في ملء رقم العربية: {e}")

# ==== الضغط على زر "إجمالى المخالفات" ====
def click_total_violations(driver):
    try:
        btn = driver.find_element(By.ID, "GET_FIN_LETTER_NUMBERS_BTN")
        btn.click()
        time.sleep(2)
    except Exception as e:
        print(f"خطأ في الضغط على الزر: {e}")

# ==== ملء الرقم القومي والهاتف ====
def fill_national_and_phone(driver, national_id, phone):
    try:
        nid_field = driver.find_element(By.ID, "P7_NATIONAL_ID_CASE_1")
        nid_field.clear()
        nid_field.send_keys(national_id)
    except Exception as e:
        print(f"خطأ في الرقم القومي: {e}")

    try:
        phone_field = driver.find_element(By.ID, "P7_PHONE_NUMBER_ID_CASE_1")
        phone_field.clear()
        phone_field.send_keys(phone)
    except Exception as e:
        print(f"خطأ في رقم الهاتف: {e}")

# ==== الضغط على زر "تفاصيل المخالفات" ====
def click_details_button(driver):
    try:
        btn = driver.find_element(By.ID, "B1776099686727570788")
        btn.click()
        time.sleep(2)
    except Exception as e:
        print(f"خطأ في الضغط على زر التفاصيل: {e}")

# ==== طباعة الصفحة كاملة إلى PDF ====
def print_to_pdf(driver, output_name="page_output.pdf"):
    print_options = {
        "paperWidth": 8.27,  # A4 width in inches
        "paperHeight": 11.69,  # A4 height in inches
        "marginTop": 0,
        "marginBottom": 0,
        "marginLeft": 0,
        "marginRight": 0,
        "printBackground": True,
        "landscape": False
    }
    result = driver.execute_cdp_cmd("Page.printToPDF", print_options)
    pdf_bytes = base64.b64decode(result['data'])  # تصحيح: تحويل من base64
    with open(output_name, "wb") as f:
        f.write(pdf_bytes)
    return output_name

# ==== تخزين الحالة المؤقتة للمستخدم ====
user_pending = {}  # chat_id -> بيانات مؤقتة
user_save_pending = {}  # chat_id -> بيانات جاهزة للحفظ

@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    bot.reply_to(message, "أرسل رقم العربية لتبدأ العملية (أرقام فقط):")

@bot.message_handler(func=lambda msg: True)
def handle_plate(message):
    chat_id = message.chat.id
    text = message.text.strip().upper()
    
    # التحقق من أرقام فقط عند المرحلة الأولى
    if chat_id not in user_pending and chat_id not in user_save_pending:
        if not text.isdigit():
            bot.send_message(chat_id, "رقم العربية يجب أن يحتوي أرقام فقط. أرسل الرقم مرة أخرى:")
            return
        plate_number = text
        if plate_number in saved_data:
            # البحث المباشر: العربية موجودة مسبقًا → أرسل PDF مباشرة
            bot.send_message(chat_id, f"اللوحة {plate_number} موجودة مسبقًا. جاري إنشاء PDF...")
            try:
                data = saved_data[plate_number]
                driver = open_page()
                fill_letters(driver, data["letters"])
                fill_plate_number(driver, data["number"])
                click_total_violations(driver)
                fill_national_and_phone(driver, data["national_id"], data["phone"])
                click_details_button(driver)
                pdf_file = print_to_pdf(driver, f"{plate_number}.pdf")
                driver.quit()
                with open(pdf_file, "rb") as f:
                    bot.send_document(chat_id, f, caption=f"الصفحة كاملة للوحة: {plate_number}")
            except Exception as e:
                bot.send_message(chat_id, f"حصل خطأ: {e}")
            return
        # العربية جديدة → نبدأ جمع البيانات
        user_pending[chat_id] = {"plate_number": plate_number, "step": 1}
        bot.send_message(chat_id, f"لوحة {plate_number} جديدة. ابعت الحروف الثلاثة:")
        return

    # لو المستخدم في مرحلة إدخال بيانات
    if chat_id in user_pending:
        step = user_pending[chat_id]["step"]
        if step == 1:
            letters = text
            if len(letters) != 3:
                bot.send_message(chat_id, "الحروف الثلاثة يجب أن تكون 3 أحرف فقط.")
                return
            user_pending[chat_id]["letters"] = letters
            user_pending[chat_id]["step"] = 2
            bot.send_message(chat_id, "ابعت الرقم القومي:")
        elif step == 2:
            user_pending[chat_id]["national_id"] = text
            user_pending[chat_id]["step"] = 3
            bot.send_message(chat_id, "ابعت رقم الهاتف:")
        elif step == 3:
            user_pending[chat_id]["phone"] = text
            # كل البيانات موجودة الآن → نفذ العملية
            data = user_pending[chat_id]
            bot.send_message(chat_id, "جاري فتح الصفحة وملء البيانات...")
            try:
                driver = open_page()
                fill_letters(driver, data["letters"])
                fill_plate_number(driver, data["plate_number"])
                click_total_violations(driver)
                fill_national_and_phone(driver, data["national_id"], data["phone"])
                click_details_button(driver)
                pdf_file = print_to_pdf(driver, f"{data['plate_number']}.pdf")
                driver.quit()
                with open(pdf_file, "rb") as f:
                    bot.send_document(chat_id, f, caption=f"الصفحة كاملة للوحة: {data['plate_number']}")
                bot.send_message(chat_id, "هل تريد حفظ البيانات؟ (اكتب نعم أو لا)")
                user_save_pending[chat_id] = data.copy()
                del user_pending[chat_id]
            except Exception as e:
                bot.send_message(chat_id, f"حصل خطأ: {e}")
                driver.quit()
                del user_pending[chat_id]
        return

    # التحقق من موافقة الحفظ
    if chat_id in user_save_pending:
        if text.lower() == "نعم":
            data = user_save_pending[chat_id]
            saved_data[data["plate_number"]] = {
                "letters": data["letters"],
                "number": data["plate_number"],
                "national_id": data["national_id"],
                "phone": data["phone"]
            }
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(saved_data, f, ensure_ascii=False, indent=4)
            bot.send_message(chat_id, f"تم حفظ البيانات للوحة: {data['plate_number']}")
            del user_save_pending[chat_id]
        elif text.lower() == "لا":
            bot.send_message(chat_id, "تم تجاهل حفظ البيانات.")
            del user_save_pending[chat_id]
        else:
            bot.send_message(chat_id, "اكتب نعم أو لا فقط للحفظ.")
        return

# ==== تشغيل البوت ====
if __name__ == "__main__":
    print("Bot polling started...")
    bot.infinity_polling(timeout=60)
