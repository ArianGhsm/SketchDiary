# معماری پروژه

## لایه‌ها

### `main.py`

- bootstrap
- init دیتابیس
- seed اولیه
- اجرای polling با `aiogram`

### `bot/application.py`

- ساخت `Bot` و `Dispatcher`
- ثبت router
- راه‌اندازی و shutdown `APScheduler`
- بارگذاری jobهای ذخیره‌شده

### `bot/handlers.py`

هسته‌ی جریان‌های ربات:

- احراز هویت
- بررسی درخواست‌ها
- پروفایل و نمره‌ها
- پنل نماینده
- ساخت فرم
- پاسخ‌دهی به فرم
- export
- schedule
- پنل مدیر

### `bot/ui/`

- `texts.py`: متن‌های کاربرمحور
- `keyboards.py`: کیبوردهای اینلاین

### `bot/services/`

- `datetime_fa.py`: زمان جلالی/تهران
- `formatting.py`: helperهای نمایش
- `parsers.py`: پارس ورودی‌های متنی
- `policies.py`: نقش‌ها و permission
- `exporters.py`: خروجی‌های CSV/XLSX/JSON/Text
- `scheduler.py`: helperهای APScheduler

### `db.py`

لایه‌ی داده برای:

- احراز هویت
- دانشجوها و نمره‌ها
- فرم‌ها و سوال‌ها
- پاسخ‌ها و order ثبت
- scheduleها

## قراردادهای معماری

### Inline-First

entry point همه‌ی featureها باید callback اینلاین باشد.

### Auth-First

تا قبل از تایید احراز هویت:

- پروفایل
- کارنامه
- ثبت فرم

در دسترس کامل نیستند.

### Central Formatting

برای داده‌های قابل‌کپی و زمان‌های مهم از helperهای مشترک استفاده می‌شود تا متن‌ها در کل پروژه یکدست بمانند.

### Data in `data/`

فایل‌های عملیاتی بیرون از `data/` ساخته نمی‌شوند.

## جریان‌های اصلی

### احراز هویت

1. ثبت شماره دانشجویی
2. ثبت معرفی کوتاه
3. ساخت `verification_requests`
4. ارسال کارت بررسی به نماینده
5. تایید یا رد
6. ثبت نهایی در `telegram_students`

### فرم

1. ساخت فرم توسط نماینده
2. ساخت سوال‌ها
3. انتشار مستقیم یا زمان‌بندی‌شده
4. ثبت پاسخ دانشجو
5. ذخیره در `form_submissions` و `submission_answers`
6. export و عملیات مدیریتی

### زمان‌بندی

1. انتخاب فرم الگو
2. ثبت کانال
3. ثبت زمان انتشار
4. ثبت مهلت فرم منتشرشده
5. ثبت job در scheduler
6. ساخت نسخه جدید فرم و انتشار در کانال
