# دستیار دانشجویان دندان‌پزشکی ورودی ۱۴۰۲

ربات تلگرامی دانشجویی با طراحی **Inline-First**:
- احراز هویت دانشجو با شماره دانشجویی
- نمایش نمرات + تحلیل میانگین و رتبه
- پنل نماینده کلاس (نمره گروهی، اطلاعیه همگانی، فرم/لیست تلگرامی)
- پذیرش ورودی عدد فارسی/عربی/انگلیسی و نمایش اعداد خروجی به فارسی

## چرا این ری‌استراکچر انجام شد؟

با الگو گرفتن از نقاط قوت پروژه‌های بزرگ‌تر (مثل تفکیک واضح `text/keyboard/handler`) ساختار پروژه ماژولار شد، اما منطق این ربات کاملا اختصاصی خود این پروژه ماند.

هدف:
- توسعه‌پذیری بالا برای آپشن‌های بعدی
- نگهداری ساده‌تر توسط هر انسان/ربات
- UX یکدست، سریع و اینلاین‌محور

## اصول غیرقابل مذاکره

1. ناوبری کاربر باید با دکمه‌های اینلاین باشد.
2. ورودی متنی فقط برای Data Entry مجاز است.
3. هر مسیر باید دکمه بازگشت/لغو/منو داشته باشد.
4. قبل از احراز هویت، منوی کامل نمایش داده نشود (Auth-First).
5. سطح command حداقلی بماند: فقط `/start` و `/cancel`.

## ساختار جدید پروژه

```text
.
├── main.py                      # Bootstrap: init DB + seed + run polling
├── config.py                    # Token, IDs, data paths
├── app_callbacks.py             # callback_data constants
├── db.py                        # SQLite data layer
├── grade_analytics.py           # ranking/average analytics
├── text_utils.py                # Persian/English digit utilities
├── import_students.py           # CSV import utility
├── data/
│   ├── students.db              # runtime database
│   └── default_students.csv     # default seed data
└── bot/
    ├── application.py           # wiring handlers/conversation
    ├── handlers.py              # all async telegram handlers
    ├── states.py                # conversation states
    ├── ui/
    │   ├── keyboards.py         # inline keyboards
    │   └── texts.py             # user-facing texts
    └── services/
        ├── localization.py      # Persian output helper
        ├── policies.py          # roles/auth checks + ID normalization
        └── parsers.py           # grade list parsing + callback id parsing
```

## قابلیت‌ها

- احراز هویت دائمی دانشجو (تا زمان حذف توسط ادمین)
- پروفایل دانشجو
- نمایش نمرات و تحلیل:
  - میانگین شخصی
  - رتبه در کلاس
  - میانگین کلاس
  - اختلاف با میانگین کلاس
- پنل نماینده:
  - ثبت گروهی نمرات یک درس
  - اطلاعیه همگانی برای کاربران احراز‌شده
  - ساخت فرم/لیست داخل تلگرام با لینک عضویت
  - تایید عضویت دانشجو با دکمه اینلاین
  - مشاهده و بروزرسانی لحظه‌ای لیست اعضا

## پیش‌نیاز

- Python 3.10+
- `python-telegram-bot>=21.0,<22.0`

## راه‌اندازی

1. نصب وابستگی‌ها:

```bash
pip install -r requirements.txt
```

2. تنظیم `config.py`:
- `bot_token`
- `ADMIN_IDS`
- `MAIN_REP_STUDENT_NUMBER`
- `MAIN_REP_TELEGRAM_ID`

3. (اختیاری) ایمپورت اولیه دستی:

```bash
python import_students.py --replace-all
```

4. اجرای بات:

```bash
python main.py
```

نکته: اگر جدول `students` خالی باشد، در startup به صورت خودکار از `data/default_students.csv` seed انجام می‌شود.

## فرمت CSV

حداقل ستون‌ها:
- `StudentID`
- یکی از این دو حالت:
  - `Name`
  - یا `FirstName` + `LastName`

ستون `Password` نادیده گرفته می‌شود.

## تشخیص ادمین و نماینده

- ادمین‌ها از `ADMIN_IDS` خوانده می‌شوند.
- `MAIN_REP_TELEGRAM_ID` به‌صورت پیش‌فرض سطح مدیریتی دارد.
- نرمال‌سازی شناسه‌ها انجام می‌شود تا خطاهای رایج ورودی عدد (فارسی/عربی/spacing) باعث عدم تشخیص نشود.

## عیب‌یابی سریع

### ربات گفت شماره دانشجویی در دیتابیس نیست

1. مطمئن شو `data/students.db` داده دارد.
2. این دستور را اجرا کن:

```bash
python import_students.py --replace-all
```

3. دوباره `/start` و احراز هویت را تست کن.

### نماینده با آیدی خودش تشخیص داده نشد

1. مقدار `MAIN_REP_TELEGRAM_ID` در `config.py` را چک کن.
2. مطمئن شو همان کاربر با `MAIN_REP_STUDENT_NUMBER` احراز هویت شده باشد.

## قانون نگهداری (اجباری)

هر تغییر کد باید همزمان مستندات را آپدیت کند.

حداقل:
- `README.md`

در صورت نیاز:
- `ARCHITECTURE_FA.md`
- `INLINE_UX_POLICY_FA.md`
- `CONTRIBUTING_FA.md`

و اگر import/dependency عوض شد:
- `requirements.txt`

## فعال‌سازی چک خودکار قبل commit

```bash
git config core.hooksPath .githooks
```

اسکریپت بررسی:
- `tools/check_readme_sync.py`

## بکاپ و مهاجرت

برای بکاپ کامل داده‌های عملیاتی، پوشه `data/` را نگه‌دار یا جابجا کن.
