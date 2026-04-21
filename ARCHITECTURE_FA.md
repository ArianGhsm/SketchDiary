# معماری SketchDiary

این سند معماری واقعی پروژه را از روی ساختار فعلی کد توضیح می‌دهد.

---

## تصویر کلی

پروژه یک بات تلگرامی مبتنی بر `aiogram 3` است که با این لایه‌ها کار می‌کند:

1. لایه bootstrap و startup
2. لایه application و wiring
3. لایه handlerها و flowها
4. لایه UI شامل متن و کیبورد
5. لایه service برای helperهای قابل استفاده‌ی مجدد
6. لایه data access در `db.py`

---

## 1. Bootstrap

### `main.py`

وظیفه‌ها:

- تنظیم logging
- اجرای `init_db()`
- seed اولیه از `data/default_students.csv`
- ساخت `Bot` و `Dispatcher`
- حذف webhook قبلی
- جلوگیری از اجرای هم‌زمان polling با فایل قفل

فایل قفل:

```text
data/bot.polling.lock
```

---

## 2. Application Wiring

### `bot/application.py`

این فایل لایه‌ی اتصال اجزای اصلی است:

- ساخت نمونه‌ی `Bot`
- ساخت `Dispatcher`
- include کردن router اصلی
- ساخت و راه‌اندازی `APScheduler`
- ثبت startup/shutdown hook

قرارداد مهم:

- jobهای زمان‌بندی‌شده از دیتابیس خوانده می‌شوند
- callback اجرای schedule به `publish_scheduled_form` وصل است

---

## 3. Handler Layer

### `bot/handlers.py`

این فایل هسته‌ی جریان‌های بات است. مهم‌ترین گروه‌ها:

### احراز هویت

- شروع احراز هویت
- دریافت شماره دانشجویی
- دریافت معرفی کوتاه
- شروع flow با یک پیام واحد
- ساخت `verification_requests`
- ارسال کارت بررسی به نماینده‌ها و مدیرها
- تایید/رد نهایی و اطلاع‌رسانی به دانشجو
- تایید idempotent درخواست و جلوگیری از `UNIQUE` روی `telegram_students`

### فرم و ثبت‌نام

- ساخت فرم
- ساخت سریع لیست بدون سوال اضافه
- تعریف سوال‌ها
- شروع پاسخ‌گویی دانشجو
- ذخیره‌ی پاسخ‌ها
- مدیریت فرم توسط نماینده

### پنل نماینده

- لیست درخواست‌های در انتظار
- ثبت گروهی نمره
- اطلاعیه همگانی
- مدیریت فرم‌ها
- زمان‌بندی‌ها

### پنل مدیر

- تنظیم کانال‌های سراسری ربات
- مشاهده‌ی دانشجوهای تاییدشده
- مشاهده‌ی ثبت‌های اخیر
- غیرفعال‌سازی ثبت فعال با تایید نهایی
- دریافت بکاپ ZIP از دیتابیس

---

## 4. UI Layer

### `bot/ui/texts.py`

این فایل محل تولید متن‌های HTML است.

قواعد این لایه:

- متن‌ها فارسی و کاربرمحور باشند
- داده‌های قابل‌کپی با `monospace`
- زمان‌های مهم با helperهای مرکزی رندر شوند
- متن خام در handlerها کمتر شود

### `bot/ui/keyboards.py`

این فایل همه‌ی keyboardهای اینلاین را متمرکز نگه می‌دارد.

قواعد این لایه:

- button semantics یکدست
- استفاده از `style="success"` و `style="danger"` فقط برای اکشن‌های برجسته
- نگه‌داشتن دکمه‌های خنثی در حالت پیش‌فرض و بی‌رنگ
- دکمه‌های `copy_text` برای موارد مناسب
- back/cancel/home در flowها

---

## 5. Service Layer

### `bot/services/date_picker.py`

منطق reusable picker تاریخ/زمان:

- state پیش‌فرض انتخاب
- navigation بین سال و ماه
- محدودکردن روزهای نامعتبر
- تبدیل انتخاب جلالی به UTC
- summary مرحله‌ای انتخاب کاربر

### `bot/services/datetime_fa.py`

مسئول:

- تبدیل زمان‌ها به `Asia/Tehran`
- نمایش جلالی
- ساخت `<tg-time unix="...">...</tg-time>`
- نمایش زمان باقی‌مانده

### `bot/services/exporters.py`

مسئول:

- خروجی متنی فرم
- خروجی `CSV`
- خروجی `XLSX`
- خروجی `JSON`

### `bot/services/backup.py`

- ساخت snapshot از SQLite
- بسته‌بندی دیتابیس در فایل ZIP برای ارسال در تلگرام

### `bot/services/formatting.py`

helperهای نمایش:

- escape
- monospace
- blockquote
- badge وضعیت
- کارت‌های اطلاعاتی

### `bot/services/media.py`

منطق fallback تصویر:

- استفاده از عکس پروفایل تلگرام در صورت وجود
- fallback به فایل محلی `data/default_verification_photo.png`

### `bot/services/parsers.py`

- parse لیست نمره‌ها
- parse callbackها

### `bot/services/policies.py`

- تشخیص نقش‌ها
- normalizing شناسه‌ها
- سیاست‌های احراز هویت و نمایندگی

### `bot/services/scheduler.py`

- ساخت scheduler
- load کردن jobها از دیتابیس
- محاسبه‌ی زمان بعدی برای scheduleهای recurring

---

## 6. Data Layer

### `db.py`

این فایل DAL پروژه است و همه‌ی queryهای اصلی را در خود دارد.

### جدول‌های اصلی

- `students`
- `representatives`
- `telegram_students`
- `verification_requests`
- `student_grades`
- `forms`
- `form_questions`
- `form_submissions`
- `submission_answers`
- `form_schedules`
- `bot_settings`

### قراردادهای داده

- زمان‌ها به‌صورت UTC ذخیره می‌شوند
- نمایش زمان در UI همیشه جلالی/تهران است
- ترتیب ثبت فرم با `registration_order` نگه‌داری می‌شود
- حذف ثبت فرم به‌صورت status-based انجام می‌شود، نه delete فیزیکی
- کانال‌های سراسری ربات در `bot_settings` ذخیره می‌شوند
- هر فرم فقط `announcement_channel_id` خودش را از بین کانال‌های سراسری انتخاب می‌کند

---

## 7. Flow Contracts

### Inline-First

- feature جدید باید از callback اینلاین شروع شود
- message text فقط در data-entry استفاده شود

### Auth-First

قبل از تایید احراز هویت، این بخش‌ها نباید دسترسی کامل بدهند:

- پروفایل
- کارنامه
- پاسخ‌گویی به فرم

### Safe Destructive Actions

عملیات خطرناک باید:

- context کافی بدهند
- اثر نهایی را روشن کنند
- دکمه‌ی تایید خطر (`danger`) داشته باشند
- امکان انصراف بدهند

---

## 8. توسعه‌ی قابلیت جدید

اگر قابلیت تازه‌ای اضافه می‌کنید:

1. callback آن را در `app_callbacks.py` ثبت کنید
2. متن‌ها را در `bot/ui/texts.py` بسازید
3. keyboardها را در `bot/ui/keyboards.py` تعریف کنید
4. helperهای مشترک را به `bot/services/` ببرید
5. در صورت نیاز query جدید را به `db.py` اضافه کنید
6. مستندات را هم‌زمان به‌روزرسانی کنید

---

## 9. نقاط حساس معماری

### Race Condition در تایید احراز هویت

تصمیم نهایی درخواست در `decide_verification_request` انجام می‌شود تا:

- فقط اولین تصمیم معتبر اعمال شود
- اتصال تکراری شماره دانشجویی جلوگیری شود
- رکورد قبلی همان کاربر به‌صورت upsert امن به‌روزرسانی شود و خطای `UNIQUE` رخ ندهد

### Polling Conflict

اجرای هم‌زمان polling هم از سمت تلگرام و هم روی سیستم محلی می‌تواند conflict ایجاد کند. برای همین:

- `delete_webhook()` در startup اجرا می‌شود
- فایل lock محلی ساخته می‌شود

### Schedule Persistence

زمان‌بندی‌ها در دیتابیس می‌مانند و بعد از restart دوباره load می‌شوند.

### Global Channel Registry

کانال اطلاع‌رسانی و کانال جزوه یک‌بار برای کل ربات ثبت می‌شوند.

- هر فرم فقط مقصد انتشار خودش را از بین همین کانال‌ها انتخاب می‌کند
- اگر فقط یک کانال سراسری موجود باشد، فرم می‌تواند به‌صورت خودکار همان مقصد را بگیرد

---

## اسناد مرتبط

- [README اصلی](./README.md)
- [سیاست UX](./INLINE_UX_POLICY_FA.md)
- [راهنمای مشارکت](./CONTRIBUTING_FA.md)
- [مستندات پوشه bot](./bot/README.md)
