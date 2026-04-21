# مستندات پوشه `bot/services`

این پوشه محل helperها و منطق reusable پروژه است. اگر چیزی در چند flow استفاده می‌شود، جای مناسبش معمولاً اینجاست.

---

## فایل‌ها

### `date_picker.py`

منطق reusable انتخاب تاریخ/زمان:

- state پیش‌فرض picker
- تبدیل جلالی به UTC
- محاسبه‌ی تعداد روزهای ماه
- navigation بین ماه‌ها

### `datetime_fa.py`

- نمایش زمان به جلالی
- timezone تهران
- `tg-time`
- زمان باقی‌مانده

### `exporters.py`

- خروجی متنی فرم
- خروجی `CSV`
- خروجی `XLSX`
- خروجی `JSON`

### `backup.py`

- snapshot امن از دیتابیس SQLite
- ساخت فایل ZIP برای ارسال بکاپ در تلگرام

### `formatting.py`

- escape
- monospace
- info card
- status badge
- blockquote

### `media.py`

- fallback تصویر برای کارت احراز هویت

### `parsers.py`

- parse داده‌های متنی مثل لیست نمره

### `policies.py`

- نقش‌ها
- دسترسی‌ها
- normalize شناسه‌ها

### `scheduler.py`

- ساخت و بارگذاری jobهای زمان‌بندی

---

## قرارداد این پوشه

- service باید reusable باشد
- متن UI اینجا ننویس
- keyboard اینجا نساز
- query دیتابیس مستقیم اینجا نریز مگر helper بودنش توجیه داشته باشد

اگر helper تازه‌ای می‌سازی و در بیش از یک flow به درد می‌خورد، قبل از چسباندنش به handlerها اول این پوشه را در نظر بگیر.
