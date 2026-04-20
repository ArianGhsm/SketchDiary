# مستندات پوشه `bot`

این پوشه هسته‌ی اجرایی ربات را نگه می‌دارد.

## اجزا

### `application.py`

- ساخت `Bot`
- ساخت `Dispatcher`
- راه‌اندازی scheduler
- ثبت startup/shutdown hook

### `handlers.py`

flowهای اصلی:

- شروع و منوی اصلی
- احراز هویت
- بررسی درخواست‌ها
- پروفایل
- کارنامه
- پنل نماینده
- ساخت و مدیریت فرم
- پاسخ‌دهی به فرم
- export
- schedule
- پنل مدیر

### `states.py`

تمام stateهای FSM مربوط به data-entry.

### `ui/`

- `texts.py`: متن‌های HTML
- `keyboards.py`: کیبوردهای اینلاین

### `services/`

- `datetime_fa.py`
- `exporters.py`
- `formatting.py`
- `localization.py`
- `parsers.py`
- `policies.py`
- `scheduler.py`

## قرارداد توسعه

- feature جدید را مستقیما در handler شلوغ نکنید اگر helper مستقل لازم است.
- متن و کیبورد را از flow جدا نگه دارید.
- زمان و داده‌ی قابل‌کپی را با helper مرکزی رندر کنید.
