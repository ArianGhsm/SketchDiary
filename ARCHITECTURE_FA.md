# معماری پروژه

این پروژه یک ربات تلگرامی دانشجویی **Inline-First** است که برای ورودی ۱۴۰۲ دندان‌پزشکی طراحی شده و باید برای توسعه تدریجی ماژول‌ها آماده بماند.

## اهداف معماری

- تفکیک واضح UI، منطق جریان، و قواعد دسترسی
- حفظ UX دکمه‌محور و Auth-First
- کاهش ریسک تغییرات آینده با ماژول‌بندی روشن
- خوانایی بالا برای ادیتورهای بعدی (انسان/ربات)

## لایه‌ها

### 1) Bootstrap
- `main.py`
- مسئول init دیتابیس، seed اولیه و اجرای polling
- منطق ویژگی‌ها نباید وارد این فایل شود

### 2) Application Wiring
- `bot/application.py`
- اتصال conversation states، callback handlers و message handlers
- نقطه مرکزی ثبت مسیرهای اینلاین

### 3) Handlers (Orchestration)
- `bot/handlers.py`
- اجرای جریان‌های کاربر، نماینده و ادمین
- اتصال UI به query/service/db
- تصمیم‌گیری‌های سطح جریان

### 4) UI
- `bot/ui/keyboards.py`
  - تمام InlineKeyboardها
- `bot/ui/texts.py`
  - متن‌های کاربر-محور و قالب پیام‌ها

### 5) Service Helpers
- `bot/services/policies.py`
  - نقش‌ها و دسترسی‌ها (`admin`, `rep`, `verified`)
  - نرمال‌سازی شناسه‌ها و شماره دانشجویی
- `bot/services/parsers.py`
  - پارس لیست نمره و callback IDs
- `bot/services/localization.py`
  - خروجی فارسی اعداد

### 6) Data + Domain
- `db.py`: لایه دیتابیس SQLite
- `grade_analytics.py`: منطق میانگین/رتبه
- `text_utils.py`: تبدیل ارقام فارسی/عربی/انگلیسی

## جریان دسترسی

1. `start` -> منوی اصلی
2. اگر کاربر احراز نشده باشد، فقط مسیر احراز + راهنما نمایش داده می‌شود
3. بعد از احراز، امکانات دانشجویی فعال می‌شود
4. پنل نماینده فقط برای نماینده تایید‌شده فعال است
5. پنل ادمین بر اساس policy مرکزی تشخیص داده می‌شود

## قرارداد توسعه

1. هر قابلیت جدید باید از callback اینلاین شروع شود.
2. ورودی متنی فقط در stateهای data-entry استفاده شود.
3. هر مسیر باید دکمه بازگشت/لغو/منو داشته باشد.
4. callback جدید ابتدا در `app_callbacks.py` تعریف شود.
5. تغییرات رفتاری/جریانی باید همزمان در `README.md` مستند شود.

## الگوی افزودن قابلیت جدید

1. callback جدید به `app_callbacks.py` اضافه کن.
2. در صورت نیاز کیبورد در `bot/ui/keyboards.py` بساز.
3. متن‌ها را در `bot/ui/texts.py` اضافه کن.
4. منطق parsing/policy را در `bot/services/*` قرار بده.
5. handler مربوطه را در `bot/handlers.py` اضافه کن.
6. در `bot/application.py` مسیر handler را register کن.
7. README را آپدیت کن.

## داده و بکاپ

تمام داده‌های عملیاتی زیر `data/` نگه‌داری می‌شوند:
- `data/students.db`
- `data/default_students.csv`

برای بکاپ یا مهاجرت، انتقال پوشه `data/` کافی است.
