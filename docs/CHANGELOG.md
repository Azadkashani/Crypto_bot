FILE: docs/CHANGELOG.md

# FTR Crypto Trading Bot — گزارش تغییرات و پیشرفت پروژه

## نسخه: 1.3
## آخرین به‌روزرسانی: 16 آگوست 2026
## وضعیت: فعال

---

## مرحله ۰: طراحی معماری

| مورد | مقدار |
|------|-------|
| **تاریخ** | 15 آگوست 2026 |
| **فاز** | Phase 0 |
| **عنوان** | Architecture & System Design |
| **وضعیت** | ✅ تکمیل‌شده و تأیید شده |

### خلاصه

طراحی کامل معماری سیستم شامل تعریف استراتژی FTR، معماری لایه‌ای، ساختار دایرکتوری، State Machine مدیریت Zone، الگوریتم‌های تشخیص، مکانیزم‌های جلوگیری از Look-ahead Bias، طراحی Entry/SL/TP ساختاری و فازهای توسعه انجام شد.

### فایل‌های ایجاد شده

- `docs/ARCHITECTURE.md`

---

## مرحله ۱: پیاده‌سازی هسته FTR

| مورد | مقدار |
|------|-------|
| **تاریخ** | 15 آگوست 2026 |
| **فاز** | Phase 1 |
| **عنوان** | FTR Core Implementation |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

هسته اصلی موتور تشخیص FTR پیاده‌سازی شد:

- تایپ‌های داده (SwingPoint, StructureLevel, FTRZone, BaseData, FTBEvent و غیره)
- تشخیص Swing با الگوریتم Pivot و تأخیر تأیید
- تحلیل ساختار بازار (روند، BOS، CHoCH، سطوح ساختاری)
- تشخیص شکست (Breakout) با اعتبارسنجی فاصله و تأیید
- تشخیص Impulse با اندازه‌گیری قدرت و فاصله
- تشخیص Base با اعتبارسنجی عدم بازگشت کامل
- ساخت FTR Zone از مرزهای Base با نقطه ابطال
- تشخیص FTB (First Time Back) با تفکیک از لمس‌های بعدی
- موتور اصلی FTR Engine برای هماهنگی تمام اجزا

### فایل‌های ایجاد شده

- `src/strategy/types/market_structure.py`
- `src/strategy/types/ftr_types.py`
- `src/strategy/market_structure/swing_detector.py`
- `src/strategy/market_structure/structure_analyzer.py`
- `src/strategy/ftr/breakout_detector.py`
- `src/strategy/ftr/impulse_detector.py`
- `src/strategy/ftr/base_detector.py`
- `src/strategy/ftr/zone_constructor.py`
- `src/strategy/ftr/ftb_detector.py`
- `src/strategy/ftr/ftr_engine.py`
- `tests/unit/test_ftr_detection.py`
- `tests/unit/test_no_lookahead.py`
- `tests/unit/test_ftb_detection.py`

---

## مرحله ۲: ایجاد مستندات

| مورد | مقدار |
|------|-------|
| **تاریخ** | 15 آگوست 2026 |
| **فاز** | Documentation |
| **عنوان** | Project Documentation |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

مستندات کامل پروژه ایجاد شد.

### فایل‌های ایجاد شده

- `docs/ARCHITECTURE.md`
- `docs/CHANGELOG.md`

---

## مرحله ۳: رفع خطای Import

| مورد | مقدار |
|------|-------|
| **تاریخ** | 15 آگوست 2026 |
| **فاز** | Phase 1 Debug |
| **عنوان** | Import Fix — MarketStructureState |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

خطای `NameError: name 'MarketStructureState' is not defined` برطرف شد. import مربوطه به `ftr_types.py` اضافه شد.

### فایل‌های اصلاح‌شده

- `src/strategy/types/ftr_types.py`
- `src/strategy/types/market_structure.py`

---

## مرحله ۴: رفع خطای ساختار بازار

| مورد | مقدار |
|------|-------|
| **تاریخ** | 15 آگوست 2026 |
| **فاز** | Phase 1 Debug |
| **عنوان** | StructureAnalyzer Fix |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

خطای `TypeError: MarketStructureState.__init__() missing 1 required positional argument` برطرف شد.

### فایل‌های اصلاح‌شده

- `src/strategy/market_structure/structure_analyzer.py`

---

## مرحله ۵: رفع خطای FTB Detector

| مورد | مقدار |
|------|-------|
| **تاریخ** | 15 آگوست 2026 |
| **فاز** | Phase 1 Debug |
| **عنوان** | FTB Detector Fix — NoneType base |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

خطای `AttributeError: 'NoneType' object has no attribute 'end_index'` برطرف شد. بررسی `zone.base is not None` اضافه شد.

### فایل‌های اصلاح‌شده

- `src/strategy/ftr/ftb_detector.py`

---

## مرحله ۶: رفع Bug اصلی — is_consumed Lifecycle

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 1 Root-Cause Fix |
| **عنوان** | StructureBreak / Level Consumption Lifecycle |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

Root Cause اصلی پیدا و اصلاح شد:

- `StructureAnalyzer._register_break` دیگر `level.is_consumed = True` نمی‌کند
- سطح فقط پس از ساخت موفق FTR Zone در `FTREngine` مصرف می‌شود
- `FTREngine` از `get_recent_breaks()` به جای `BreakoutDetector` مستقل استفاده می‌کند

### فایل‌های اصلاح‌شده

- `src/strategy/market_structure/structure_analyzer.py`
- `src/strategy/ftr/ftr_engine.py`

---

## مرحله ۷: رفع Look-ahead Bias

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 1 Root-Cause Fix |
| **عنوان** | Look-ahead Prevention — Historical Break Reprocessing |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

مشکل پردازش مجدد Breakهای تاریخی با داده‌های آینده برطرف شد:

- `visible_ohlcv` برای تمام Detectorها استفاده می‌شود
- فقط Breakهای با `break_timestamp <= current_timestamp` پردازش می‌شوند
- Break ناقص در `_pending_breaks` باقی می‌ماند
- `_processed_breaks` برای جلوگیری از پردازش تکراری

### فایل‌های اصلاح‌شده

- `src/strategy/ftr/ftr_engine.py`
- `src/strategy/market_structure/structure_analyzer.py`

---

## مرحله ۸: رفع Duplicate Break Registration

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 2.1 |
| **عنوان** | Duplicate Break Prevention |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

مشکل ثبت تکراری Break برای سطوح قدیمی‌تر برطرف شد. `_registered_break_keys` در `StructureAnalyzer` اضافه شد.

### فایل‌های اصلاح‌شده

- `src/strategy/market_structure/structure_analyzer.py`

---

## مرحله ۹: FTB Lifecycle Validation

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 2 |
| **عنوان** | FTB / First-Touch Lifecycle |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

Zone creation candle دیگر به عنوان FTB candidate در نظر گرفته نمی‌شود.

### فایل‌های اصلاح‌شده

- `src/strategy/ftr/ftr_engine.py`

---

## مرحله ۱۰: Signal Quality Layer

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 4 |
| **عنوان** | Signal Quality & Confluence Layer |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

لایه مستقل Signal Quality ایجاد شد:

- `SignalQualityEngine` با امتیازدهی به Structure، Displacement، Base، Zone، FTB و Trend
- طبقه‌بندی QUALIFIED / WATCH / REJECTED
- توضیح‌پذیری از طریق positive_factors و warning_factors

### فایل‌های ایجاد شده

- `src/strategy/signal/__init__.py`
- `src/strategy/signal/signal_quality_types.py`
- `src/strategy/signal/signal_quality_engine.py`
- `tests/unit/test_signal_quality.py`

---

## مرحله ۱۱: رفع FTB Penetration Scoring

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 4.1 |
| **عنوان** | FTB Penetration Scoring Fix |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

تابع `_calculate_ftb_penetration_ratio` برای محاسبه صحیح عمق نفوذ از سمت صحیح Zone اضافه شد.

### فایل‌های اصلاح‌شده

- `src/strategy/signal/signal_quality_engine.py`

---

## مرحله ۱۲: Trade Signal Layer

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 5.1 |
| **عنوان** | Trade Signal Generation |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

Trade Signal Layer ایجاد شد:

- `TradeSignalEngine` فقط سیگنال‌های QUALIFIED را به TradeSignal تبدیل می‌کند
- Entry از FTB price
- SL از zone.invalidation_level
- TP از نزدیک‌ترین سطح ساختاری
- R:R محاسبه دینامیک

### فایل‌های ایجاد شده

- `src/strategy/trade/__init__.py`
- `src/strategy/trade/trade_signal_types.py`
- `src/strategy/trade/trade_signal_engine.py`
- `tests/unit/test_trade_signal.py`

---

## مرحله ۱۳: Risk Management Layer

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 5.2 |
| **عنوان** | Risk Management & Position Sizing |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

Risk Management Layer ایجاد شد:

- `RiskManagementEngine` محاسبه Risk Amount، Position Size و Notional Value
- استقلال از Leverage
- اعتبارسنجی Equity، Risk Percent، Stop Distance و R:R
- پارامترها Configurable

### فایل‌های ایجاد شده

- `src/strategy/risk/__init__.py`
- `src/strategy/risk/risk_types.py`
- `src/strategy/risk/risk_management_engine.py`
- `tests/unit/test_risk_management.py`

---

## خلاصه پیشرفت

### وضعیت فازها

| فاز | عنوان | وضعیت |
|-----|-------|--------|
| Phase 0 | Architecture Design | ✅ تکمیل |
| Phase 1 | FTR Core Implementation | ✅ تکمیل |
| Phase 2 | FTB Lifecycle | ✅ تکمیل |
| Phase 4 | Signal Quality | ✅ تکمیل |
| Phase 5.1 | Trade Signal | ✅ تکمیل |
| Phase 5.2 | Risk Management | ✅ تکمیل |
| Phase 6 | Execution | ⏳ آینده |
| Phase 7 | Exchange Integration | ⏳ آینده |

### آمار

| مورد | تعداد |
|------|-------|
| فایل‌های Production | 20 |
| فایل‌های تست | 7 |
| تعداد تست‌ها | 48 |
| وضعیت تست‌ها | ✅ 48 passed / 0 failed |

---

## پایان گزارش

**نسخه: 1.3 — آخرین به‌روزرسانی: 16 آگوست 2026**
