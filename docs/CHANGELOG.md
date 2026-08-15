FILE: docs/CHANGELOG.md

# FTR Crypto Trading Bot — گزارش تغییرات و پیشرفت پروژه

## نسخه: 1.4
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

## مرحله ۳: رفع خطاهای Phase 1

| مورد | مقدار |
|------|-------|
| **تاریخ** | 15-16 آگوست 2026 |
| **فاز** | Phase 1 Debug |
| **عنوان** | Import Fixes & Core Debugging |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

خطاهای زیر برطرف شدند:

- `NameError: MarketStructureState is not defined` — اصلاح import
- `TypeError: MarketStructureState.__init__()` — اصلاح سازنده
- `AttributeError: 'NoneType' object has no attribute 'end_index'` — بررسی None بودن base
- `is_consumed` Lifecycle — سطح فقط پس از ساخت موفق Zone مصرف می‌شود
- Duplicate Break Registration — جلوگیری از ثبت تکراری
- Zone Creation Candle ≠ FTB — جلوگیری از FTB در کندل ساخت

### فایل‌های اصلاح‌شده

- `src/strategy/types/ftr_types.py`
- `src/strategy/types/market_structure.py`
- `src/strategy/market_structure/structure_analyzer.py`
- `src/strategy/ftr/ftb_detector.py`
- `src/strategy/ftr/ftr_engine.py`

---

## مرحله ۴: Signal Quality Layer

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 4 |
| **عنوان** | Signal Quality & Confluence |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

لایه مستقل Signal Quality ایجاد شد:

- `SignalQualityEngine` با امتیازدهی به Structure، Displacement، Base، Zone، FTB و Trend
- طبقه‌بندی QUALIFIED / WATCH / REJECTED
- توضیح‌پذیری از طریق positive_factors و warning_factors
- رفع Bug محاسبه penetration ratio

### فایل‌های ایجاد شده

- `src/strategy/signal/__init__.py`
- `src/strategy/signal/signal_quality_types.py`
- `src/strategy/signal/signal_quality_engine.py`
- `tests/unit/test_signal_quality.py`

---

## مرحله ۵: Trade Signal Layer

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

## مرحله ۶: Risk Management Layer

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

## مرحله ۷: Execution Layer

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 5.3 |
| **عنوان** | Execution Layer + Risk Consistency Fix |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

Execution Layer ایجاد شد:

- `ExecutionEngine` ساخت و اعتبارسنجی سفارش
- بررسی Risk Consistency
- جلوگیری از Duplicate
- حالت DRY_RUN بدون اتصال به Exchange
- رفع Bug ترتیب اعتبارسنجی (Risk Consistency قبل از is_valid)

### فایل‌های ایجاد شده

- `src/strategy/execution/__init__.py`
- `src/strategy/execution/execution_types.py`
- `src/strategy/execution/execution_engine.py`
- `tests/unit/test_execution.py`

---

## مرحله ۸: Backtest Layer

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 5.4 |
| **عنوان** | Backtest & Simulation |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

Backtest Engine ایجاد شد:

- پردازش رویداد-محور کندل به کندل
- مدیریت پوزیشن و خروج SL/TP
- سیاست SL_FIRST برای کندل همزمان
- محاسبه PnL و Equity
- متریک‌های عملکرد

### فایل‌های ایجاد شده

- `src/strategy/backtest/__init__.py`
- `src/strategy/backtest/backtest_types.py`
- `src/strategy/backtest/backtest_engine.py`
- `tests/unit/test_backtest.py`

---

## مرحله ۹: Pipeline Integration

| مورد | مقدار |
|------|-------|
| **تاریخ** | 16 آگوست 2026 |
| **فاز** | Phase 5.5 |
| **عنوان** | Strategy Pipeline |
| **وضعیت** | ✅ تکمیل‌شده |

### خلاصه

Strategy Pipeline به عنوان Coordinator ایجاد شد:

- اتصال FTR → Signal Quality → Trade → Risk → Execution
- فیلتر QUALIFIED/WATCH/REJECTED
- مدیریت Duplicate
- بدون Look-ahead

### فایل‌های ایجاد شده

- `src/strategy/pipeline/__init__.py`
- `src/strategy/pipeline/pipeline_types.py`
- `src/strategy/pipeline/strategy_pipeline.py`
- `tests/unit/test_strategy_pipeline.py`

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
| Phase 5.3 | Execution | ✅ تکمیل |
| Phase 5.4 | Backtest | ✅ تکمیل |
| Phase 5.5 | Pipeline Integration | ✅ تکمیل |
| Phase 6 | Exchange Integration | ⏳ آینده |
| Phase 7 | Live Trading | ⏳ آینده |

### آمار

| مورد | تعداد |
|------|-------|
| فایل‌های Production | 30+ |
| فایل‌های تست | 12 |
| تعداد تست‌ها | 82 |
| وضعیت تست‌ها | ✅ 82 passed / 0 failed |

---

## پایان گزارش

**نسخه: 1.4 — آخرین به‌روزرسانی: 16 آگوست 2026**
