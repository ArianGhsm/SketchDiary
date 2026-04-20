# راهنمای مشارکت

## قانون اصلی

هر تغییر کد باید همراه با تغییر مستندات تحویل شود.

حداقل:

- `README.md`

در صورت ارتباط مستقیم:

- `ARCHITECTURE_FA.md`
- `INLINE_UX_POLICY_FA.md`
- `data/README.md`
- `bot/README.md`

اگر وابستگی یا import جدید اضافه شد:

- `requirements.txt`

## Definition of Done

یک تغییر زمانی کامل است که:

1. پروژه compile شود.
2. قرارداد Inline-First حفظ شده باشد.
3. قرارداد Auth-First شکسته نشده باشد.
4. متن‌ها و کیبوردها با استاندارد UI فعلی هماهنگ باشند.
5. README همگام با رفتار جدید پروژه باشد.

## استاندارد کدنویسی در این مخزن

- callbackهای جدید را در `app_callbacks.py` ثبت کنید.
- متن‌ها را در `bot/ui/texts.py` نگه دارید.
- کیبوردها را در `bot/ui/keyboards.py` اضافه کنید.
- helperهای مشترک را در `bot/services/` قرار دهید.
- برای تاریخ و زمان فقط از `bot/services/datetime_fa.py` استفاده کنید.
- داده‌های قابل‌کپی را با monospace نمایش دهید.

## قوانین UX

- دکمه‌ها معنی‌دار باشند.
- مسیر مخفی یا command-only نسازید.
- راهنمای عمومی بلند به منوی اصلی اضافه نکنید.
- destructive action بدون مسیر برگشت یا هشدار نسازید.

## هوک محلی

برای فعال‌سازی pre-commit hook:

```bash
git config core.hooksPath .githooks
```

اسکریپت بررسی:

```text
tools/check_readme_sync.py
```

## پیشنهاد فرایند توسعه

1. ساختار فعلی را بخوانید.
2. callback و state لازم را تعریف کنید.
3. handler را اضافه یا اصلاح کنید.
4. متن و کیبورد را یکدست کنید.
5. README و اسناد وابسته را آپدیت کنید.
6. یک دور compile یا اجرای محلی بگیرید.
