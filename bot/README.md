# مستندات پوشه `bot`

این پوشه هسته‌ی اجرایی بات را نگه می‌دارد: wiring، handlerها، UI و serviceهای reusable.

---

## نمای کلی

```text
bot/
├── application.py
├── handlers.py
├── states.py
├── services/
└── ui/
```

---

## `application.py`

مسئول:

- ساخت `Bot`
- ساخت `Dispatcher`
- include کردن router
- راه‌اندازی `APScheduler`
- load کردن jobهای ذخیره‌شده
- ثبت hookهای startup/shutdown

---

## `handlers.py`

بزرگ‌ترین فایل اجرایی پروژه و مسئول flowهای اصلی:

- start و home
- احراز هویت
- تایید/رد نماینده
- پروفایل و کارنامه
- پنل نماینده
- ساخت و مدیریت فرم
- پاسخ‌گویی به فرم
- خروجی‌گیری
- زمان‌بندی
- پنل مدیریت
- picker تاریخ/زمان

نکته:

- اگر منطق reusable پیدا کردید، آن را مستقیم داخل handler نگه ندارید
- helperها باید به `services/` و بخش متن/keyboard به `ui/` منتقل شوند

---

## `states.py`

فقط stateهای مربوط به data-entry و flowهای چندمرحله‌ای در این فایل قرار می‌گیرند.

مثال‌ها:

- احراز هویت
- ساخت فرم
- ثبت نمره
- ساخت schedule
- عملیات admin

---

## `ui/`

### `texts.py`

- متن‌های HTML
- لحن فارسی کاربرمحور
- کارت‌های اطلاعاتی
- متن picker تاریخ/زمان

### `keyboards.py`

- keyboard factory
- button semantics با `style`
- دکمه‌های copy/open
- pagination
- picker تاریخ/زمان
- تایید حذف و flowهای امن

---

## `services/`

serviceها قرار است reusable باشند و از handlerها جدا بمانند.

در وضعیت فعلی:

- `date_picker.py`
- `datetime_fa.py`
- `exporters.py`
- `formatting.py`
- `localization.py`
- `media.py`
- `parsers.py`
- `policies.py`
- `scheduler.py`

---

## قرارداد توسعه داخل این پوشه

1. متن و keyboard را از flow جدا نگه دارید.
2. برای داده‌های قابل‌کپی از helperهای formatting استفاده کنید.
3. برای زمان از helperهای مرکزی استفاده کنید.
4. برای picker تاریخ/زمان از component موجود استفاده کنید و دوباره تایپ دستی خام نسازید.
5. برای عملیات خطرناک از flow تایید نهایی استفاده کنید.

---

## اسناد مرتبط

- [README اصلی](../README.md)
- [مستندات serviceها](./services/README.md)
- [مستندات UI](./ui/README.md)
