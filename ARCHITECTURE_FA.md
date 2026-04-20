# معماری پروژه

## هدف محصول

این کدبیس برای «دستیار دانشجویان دندان‌پزشکی ورودی ۱۴۰۲» طراحی شده و باید:
- برای توسعه تدریجی ماژول‌های دانشجویی آماده باشد
- رفتار فعلی (ثبت‌نام + نمرات + رتبه + پنل نماینده + فرم/لیست) را پایدار نگه دارد
- برای ادیتورهای بعدی خوانا و قابل پیش‌بینی باشد

## لایه‌بندی

1. لایه Bot/UI (`main.py`)
- مدیریت منوهای اینلاین
- تعریف ConversationHandler و CallbackQueryHandler
- مسیریابی درخواست کاربر به سرویس‌ها

2. لایه Data (`db.py`)
- تعریف و migration ساده جداول SQLite
- تمام query ها و عملیات ذخیره/خواندن
- بدون وابستگی به تلگرام
- مسیر داده‌ها متمرکز در پوشه `data/` برای بکاپ و مهاجرت

3. لایه Domain (`grade_analytics.py`)
- پارس نمره عددی (با پشتیبانی ارقام فارسی)
- محاسبه میانگین فردی/کلاس
- محاسبه رتبه

4. لایه Product Identity
- `assistant_profile.py`: هویت محصول و ماژول‌های فعال/آتی
- `app_callbacks.py`: callback_data ها در یک نقطه ثابت

## قوانین توسعه

1. هر قابلیت جدید اول در callback ثابت تعریف شود (`app_callbacks.py`)
2. متن/هویت محصول در `assistant_profile.py` یا helper های `main.py` نگهداری شود
3. هر منطق محاسباتی جدید خارج از هندلرها و در سرویس جدا نوشته شود
4. هر query دیتابیس فقط در `db.py` اضافه شود
5. در `main.py` فقط orchestration (اتصال UI به سرویس‌ها) انجام شود
6. هر تغییر کد باید همراه آپدیت `README.md` باشد (الزامی)
7. هر تغییر import/وابستگی باید همراه آپدیت `requirements.txt` باشد (الزامی)

سند رسمی مشارکت: `CONTRIBUTING_FA.md`
سند دستور ادیتورهای رباتی: `AGENTS.md`
چک خودکار README و requirements در pre-commit: `tools/check_readme_sync.py` (با `core.hooksPath=.githooks`)

## قرارداد Inline-First

- این پروژه **دکمه‌محور اینلاین** است و باید همین‌طور بماند.
- شروع هر قابلیت جدید باید با CallbackQuery باشد.
- ورودی متنی فقط برای data-entry مجاز است، نه ناوبری.
- سطح command باید حداقلی بماند (`/start` و `/cancel`).
- سند رسمی این قرارداد: `INLINE_UX_POLICY_FA.md`

## قوانین دسترسی نماینده

- نماینده اصلی با `MAIN_REP_STUDENT_NUMBER` و `MAIN_REP_TELEGRAM_ID` در `config.py` تعریف می‌شود.
- دسترسی پنل نماینده فقط زمانی فعال است که:
1. آیدی تلگرام کاربر با نماینده اصلی یکی باشد
2. همان کاربر با شماره دانشجویی نماینده اصلی در ربات ثبت شده باشد

## الگوی افزودن ماژول جدید

مثال: «اطلاع‌رسانی کلاس»
1. callback جدید اضافه کن
2. table یا query لازم را در `db.py` اضافه کن
3. منطق کسب‌وکار را در سرویس جدید (مثلا `announcements_service.py`) بنویس
4. handler مربوطه را در `main.py` اضافه و به منو متصل کن
5. `assistant_profile.py` را برای ماژول فعال/آتی به‌روزرسانی کن

## جداول اصلی

- `students(student_number, full_name)`
- `telegram_students(telegram_user_id, student_number, full_name, profile_text, registered_at, is_active)`
- `student_grades(student_number, grades_json, updated_at)`
- `rep_forms(id, title, created_by_tg_id, created_by_student_number, created_at, is_active)`
- `rep_form_entries(form_id, telegram_user_id, student_number, full_name, joined_at)`

## مدیریت داده و بکاپ

- `config.py` مسیرهای داده را زیر `DATA_DIR` نگه می‌دارد.
- دیتابیس پیش‌فرض: `data/students.db`
- دیتای Seed پیش‌فرض: `data/default_students.csv`
- برای بکاپ/جابجایی محیط، انتقال پوشه `data/` کافی است.

## عملیات دیتابیس ویژه نماینده

- `bulk_upsert_course_grades`: ثبت/به‌روزرسانی گروهی نمره یک درس
- `list_active_registered_users`: لیست گیرنده‌های اطلاعیه همگانی
- `create_rep_form`: ساخت فرم/لیست جدید
- `list_rep_forms_by_creator`: لیست فرم‌های نماینده
- `add_rep_form_entry`: ثبت عضویت دانشجو در لیست
- `list_rep_form_entries`: نمایش اعضای لیست برای نماینده
