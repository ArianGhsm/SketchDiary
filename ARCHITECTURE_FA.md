# معماری پروژه

## نمای کلی

معماری این ربات عمدا ساده اما لایه‌دار نگه داشته شده است تا سه چیز حفظ شود:

- UX اینلاین و قابل‌پیش‌بینی
- توسعه‌پذیری برای قابلیت‌های بعدی
- خوانایی برای توسعه‌دهنده انسانی یا عامل AI

## لایه‌ها

### 1. Bootstrap

- `main.py`
- کارها:
  - init دیتابیس
  - seed اولیه از CSV
  - ساخت application
  - اجرای polling

### 2. Wiring

- `bot/application.py`
- کارها:
  - ثبت handlerها
  - تعریف stateهای conversation
  - ثبت callback routeها
  - اعمال `parse_mode=HTML`

### 3. Flow Orchestration

- `bot/handlers.py`
- کارها:
  - اجرای جریان‌های اصلی
  - کنترل permission
  - اتصال UI به داده
  - پایان‌دادن به stateها

### 4. UI Layer

- `bot/ui/texts.py`
- `bot/ui/keyboards.py`

این دو فایل باید تنها مرجع تولید متن و کیبورد برای UX کاربر باشند.

### 5. Service Layer

- `bot/services/policies.py`
  - نقش‌ها و سطح دسترسی
- `bot/services/parsers.py`
  - پارس ورودی‌های متنی
- `bot/services/formatting.py`
  - قالب‌بندی HTML-safe برای اطلاعات مهم
- `bot/services/datetime_fa.py`
  - تاریخ و زمان جلالی/تهران
- `bot/services/localization.py`
  - ابزارهای سبک بومی‌سازی

### 6. Data Layer

- `db.py`

مسئول مدیریت جدول‌های:

- `students`
- `telegram_students`
- `verification_requests`
- `student_grades`
- `rep_forms`
- `rep_form_entries`

## قراردادهای معماری

### Inline-First

هر قابلیت جدید باید با callback اینلاین شروع شود. اگر برای رفتن به یک بخش نیاز به دستور جدید باشد، معماری شکسته شده است.

### Auth-First

تا وقتی کاربر تایید نشده:

- منوی کامل دریافت نمی‌کند
- به پروفایل و نمره‌ها دسترسی ندارد
- به عضویت در فرم‌ها دسترسی ندارد

### Centralized Formatting

نمایش حرفه‌ای داده‌ها باید از helperهای مرکزی عبور کند:

- `code(...)`
- `labeled_row(...)`
- `render_telegram_time(...)`

این باعث می‌شود کیفیت متن‌ها در کل پروژه یکدست بماند.

### Centralized Date/Time

تمام تاریخ‌های کاربرمحور باید از `bot/services/datetime_fa.py` عبور کنند. نمایش مستقیم تاریخ خام دیتابیس مجاز نیست.

## جریان‌های اصلی

### احراز هویت

1. دانشجو شماره دانشجویی می‌فرستد.
2. اگر معتبر بود، معرفی کوتاه می‌فرستد.
3. رکورد `verification_requests` ساخته می‌شود.
4. پیام تایید برای نماینده/مدیر ارسال می‌شود.
5. با تایید یکی از بررسی‌کننده‌ها، رکورد `telegram_students` فعال می‌شود.

### نمره‌ها

1. نماینده نمره‌ها را خط‌به‌خط ثبت می‌کند.
2. داده در `student_grades` upsert می‌شود.
3. دانشجو تحلیل را از روی `grade_analytics.py` می‌بیند.

### فرم‌ها

1. نماینده عنوان، توضیح و مهلت اختیاری را ثبت می‌کند.
2. فرم در `rep_forms` ذخیره می‌شود.
3. دانشجو با لینک start-parameter وارد می‌شود.
4. عضویت در `rep_form_entries` ثبت می‌شود.

## انتظار از توسعه‌های بعدی

هر توسعه‌ی جدید باید:

- لایه مناسب خودش را حفظ کند
- متن و کیبورد را به `ui/` ببرد
- تاریخ را از helper مرکزی بگیرد
- قرارداد Auth-First را نشکند
- README را در همان تغییر به‌روزرسانی کند
