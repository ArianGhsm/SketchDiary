# راهنمای مشارکت

این پروژه علاوه بر کیفیت کد، روی کیفیت UX و کیفیت مستندسازی هم حساس است.

---

## قانون طلایی

هر تغییر کد باید **هم‌زمان** با به‌روزرسانی مستندات تحویل شود.

حداقل فایل‌های اجباری:

- `README.md`

در صورت ارتباط مستقیم:

- `ARCHITECTURE_FA.md`
- `INLINE_UX_POLICY_FA.md`
- `CONTRIBUTING_FA.md`
- `bot/README.md`
- `data/README.md`

اگر import یا dependency عوض شد:

- `requirements.txt`

---

## Definition of Done

یک تغییر وقتی کامل است که:

1. compile پایه را پاس کند.
2. Inline-First را نشکند.
3. Button-First را تا جای ممکن رعایت کند.
4. Auth-First را حفظ کند.
5. فایل‌های عملیاتی را بیرون از `data/` نسازد.
6. `README.md` با رفتار واقعی پروژه sync باشد.
7. اگر لینک/توکن/کد جدیدی ساخته شده، actionهای UX مناسب برای آن هم وجود داشته باشد.
8. اگر زمان جدیدی به UI اضافه شده، با جلالی + تهران + `tg-time` رندر شود.

---

## استاندارد توسعه

### محل قرارگیری تغییرها

- callbackها: `app_callbacks.py`
- متن‌ها: `bot/ui/texts.py`
- keyboardها: `bot/ui/keyboards.py`
- helperهای reusable: `bot/services/`
- queryهای دیتابیس: `db.py`

### قواعد مهم

- برای flow جدید اول از خودت بپرس آیا می‌شود دکمه‌ای‌ترش کرد یا نه
- تایپ آزاد را فقط برای ورودی‌های واقعاً لازم نگه دار
- عملیات خطرناک را بدون تایید نهایی رها نکن
- داده‌های قابل‌کپی را با `monospace` نمایش بده
- متن خام زیاد را داخل handler نریز

---

## تست‌های پیشنهادی قبل از تحویل

```bash
git config core.hooksPath .githooks
python -m compileall main.py bot db.py config.py app_callbacks.py
python tools/check_readme_sync.py
```

اگر روی flow خاصی کار کرده‌ای، حداقل یک smoke test همان مسیر هم بگیر.

---

## وقتی UX را تغییر می‌دهی

حتماً این موارد را بررسی کن:

- آیا دکمه‌ها style مناسب دارند؟
- آیا back/cancel/home وجود دارد؟
- آیا user بدون خواندن guide اضافی می‌فهمد چه باید بکند؟
- آیا اگر کاربر بخواهد چیزی را کپی کند، UI این کار را آسان کرده؟
- آیا اگر dataset بزرگ است، pagination یا search مناسب داری؟

---

## مستندسازی

مستندات این پروژه باید:

- فارسی
- دقیق
- GitHub-friendly
- همسو با UX واقعی پروژه

اگر feature تازه‌ای اضافه می‌کنی، README را فقط با یک bullet کوتاه patch نکن. باید مطمئن شوی:

- مسیر استفاده روشن است
- فایل‌های مرتبط معرفی شده‌اند
- نکات پیکربندی و محدودیت‌ها ثبت شده‌اند

---

## چیزهایی که نباید انجام شوند

- شکستن Inline-First با commandهای جدید
- اضافه‌کردن فایل دیتابیس یا runtime asset بیرون از `data/`
- dump کردن لینک یا token بدون action کمکی
- نمایش raw UTC/ISO در UI
- باقی گذاشتن flowهای حذف/رد بدون تایید
- merge کردن تغییر کد بدون sync مستندات

---

## اسناد مرتبط

- [README اصلی](./README.md)
- [معماری پروژه](./ARCHITECTURE_FA.md)
- [سیاست UX](./INLINE_UX_POLICY_FA.md)
