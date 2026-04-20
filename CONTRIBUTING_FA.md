# راهنمای مشارکت

## قانون طلایی

هر تغییر کد باید همراه با تغییر مستندات تحویل شود.

حداقل:

- `README.md`

در صورت ارتباط مستقیم:

- `ARCHITECTURE_FA.md`
- `INLINE_UX_POLICY_FA.md`
- `bot/README.md`
- `data/README.md`

اگر dependency عوض شد:

- `requirements.txt`

## Definition of Done

یک تغییر زمانی کامل است که:

1. compile یا اجرای پایه را پاس کند.
2. Inline-First را حفظ کند.
3. Auth-First را نشکند.
4. داده‌های عملیاتی را بیرون از `data/` پخش نکند.
5. README با رفتار واقعی پروژه sync باشد.

## قواعد توسعه

- callbackها را در `app_callbacks.py` نگه دارید.
- متن‌ها را در `bot/ui/texts.py` متمرکز کنید.
- کیبوردها را در `bot/ui/keyboards.py` نگه دارید.
- helper مشترک را در `bot/services/` بگذارید.
- زمان را فقط از `datetime_fa.py` رندر کنید.
- خروجی‌ها را از `exporters.py` عبور دهید.

## قبل از تحویل

```bash
git config core.hooksPath .githooks
python tools/check_readme_sync.py
```
