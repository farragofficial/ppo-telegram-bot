import os
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import telebot
from fpdf import FPDF
import time

# توكن البوت من متغير البيئة
TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

# مكان ملفات البيانات
DATA_FILE = "ppo_data.json"

# تحميل البيانات لو موجودة
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        car_data = json.load(f)
else:
    car_data = {}

# إعداد Chrome + Chromedriver للـ Linux على Railway
chrome_options = Options()
chrome_options.binary_location = "/usr/bin/chromium"
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")

service = Service("/usr/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)

# دالة لحفظ البيانات
def save_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(car_data, f, ensure_ascii=False, indent=2)

# دالة لإنشاء PDF من Screenshot
def create_pdf(screenshot_bytes, filename="screenshot.pdf"):
    tmp_img = "tmp_screenshot.png"
    with open(tmp_img, "wb") as f:
        f.write(screenshot_bytes)

    pdf = FPDF()
    pdf.add_page()
    pdf.image(tmp_img, x=10, y=10, w=190)
    pdf.output(filename)
    return filename

# بدء المحادثة مع المستخدم
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message, "أهلا! ابعتي رقم العربية لعرض المخالفات.")

# التعامل مع رسالة رقم العربية
@bot.message_handler(func=lambda m: True)
def handle_plate(message):
    plate = message.text.strip()
    
    if not plate.isdigit():
        bot.reply_to(message, "من فضلك ابعتي أرقام فقط للوحة العربية.")
        return

    # لو الرقم موجود مسبقا
    if plate in car_data:
        data = car_data[plate]
        bot.send_message(message.chat.id, f"البيانات محفوظة: {data}")
        return

    # لو جديد، نطلب باقي البيانات
    msg = bot.send_message(message.chat.id, "ابعتي الحروف (3 خانات) والرقم (خانة رقمية) والرقم القومي ورقم الهاتف، مثال: ميف 12345 12345678901234 01012345678")
    bot.register_next_step_handler(msg, fill_data, plate)

def fill_data(message, plate):
    parts = message.text.strip().split()
    if len(parts) < 4:
        bot.reply_to(message, "خطأ: ابعتي 3 حروف + الرقم + الرقم القومي + رقم الهاتف.")
        return

    letter1, letter2, letter3 = parts[0][0], parts[0][1], parts[0][2]
    number_part = parts[1]
    national_id = parts[2]
    phone = parts[3]

    # ملء النموذج على الموقع
    driver.get("https://ppo.gov.eg/ppo/r/ppoportal/ppoportal/home")
    try:
        # الضغط على نيابة المرور
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//h5[text()='نيابات المرور']/.."))
        ).click()

        # انتظار ظهور الحقول
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "P14_LETER_1"))
        )

        # ملء الحروف
        driver.find_element(By.ID, "P14_LETER_1").send_keys(letter1)
        driver.find_element(By.ID, "P14_LETER_2").send_keys(letter2)
        driver.find_element(By.ID, "P14_LETER_3").send_keys(letter3)

        # ملء الرقم
        driver.find_element(By.ID, "P14_NUMBER_WITH_LETTER").send_keys(number_part)

        # الرقم القومي ورقم الهاتف
        driver.find_element(By.ID, "P7_NATIONAL_ID_CASE_1").send_keys(national_id)
        driver.find_element(By.ID, "P7_PHONE_NUMBER_ID_CASE_1").send_keys(phone)

        # الضغط على زر تفاصيل المخالفات
        driver.find_element(By.ID, "B1776099686727570788").click()

        time.sleep(5)  # انتظار تحميل الصفحة بالكامل

        # أخذ Screenshot
        screenshot_bytes = driver.get_screenshot_as_png()

        # إنشاء PDF
        pdf_file = create_pdf(screenshot_bytes)

        # إرسال PDF للمستخدم
        with open(pdf_file, "rb") as f:
            bot.send_document(message.chat.id, f, caption=f"تفاصيل المخالفات للوحة {plate}")

        # حفظ البيانات محلياً
        car_data[plate] = {
            "letters": f"{letter1}{letter2}{letter3}",
            "number": number_part,
            "national_id": national_id,
            "phone": phone
        }
        save_data()
        bot.send_message(message.chat.id, "تم حفظ البيانات بنجاح!")

    except Exception as e:
        bot.reply_to(message, f"حدث خطأ أثناء الوصول للموقع: {e}")

# تشغيل البوت
bot.polling()
