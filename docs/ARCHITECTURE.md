FILE: docs/ARCHITECTURE.md

# FTR Crypto Trading Bot — مستندات کامل معماری و استراتژی

## نسخه: 1.0
## تاریخ: 2024
## وضعیت: مرجع اصلی پروژه

---

## فهرست مطالب

1. [معرفی پروژه](#1-معرفی-پروژه)
2. [استراتژی FTR](#2-استراتژی-ftr)
3. [معماری سیستم](#3-معماری-سیستم)
4. [ساختار دایرکتوری](#4-ساختار-دایرکتوری)
5. [لایه‌های سیستم](#5-لایه‌های-سیستم)
6. [Pipeline تشخیص FTR](#6-pipeline-تشخیص-ftr)
7. [الگوریتم‌های تشخیص](#7-الگوریتم‌های-تشخیص)
8. [مدیریت Zone و State Machine](#8-مدیریت-zone-و-state-machine)
9. [جلوگیری از Look-ahead Bias](#9-جلوگیری-از-look-ahead-bias)
10. [محاسبه Entry/SL/TP](#10-محاسبه-entrysltp)
11. [مدیریت ریسک](#11-مدیریت-ریسک)
12. [Backtesting](#12-backtesting)
13. [Paper Trading](#13-paper-trading)
14. [Live Trading](#14-live-trading)
15. [پیکربندی](#15-پیکربندی)
16. [تست‌ها](#16-تست‌ها)
17. [لاگ‌گیری](#17-لاگ‌گیری)
18. [امنیت](#18-امنیت)
19. [عملکرد](#19-عملکرد)
20. [محدودیت‌ها و ابهامات](#20-محدودیت‌ها-و-ابهامات)
21. [فازهای توسعه](#21-فازهای-توسعه)
22. [ضمیمه: تایپ‌های داده](#22-ضمیمه-تایپ‌های-داده)

---

## 1. معرفی پروژه

### 1.1 هدف

FTR Crypto Trading Bot یک ربات معاملاتی حرفه‌ای برای معاملات USDT-M Perpetual Futures در صرافی Gate.io است.

### 1.2 استراتژی اصلی

استراتژی اصلی بر پایه **FTR (Failure To Return)** در سبک **Price Action / RTM** است.

### 1.3 ارزهای مجاز

```

BTC, ETH, SOL, XRP, DOGE, HYPE, BNB, ZEC, ADA, UNI, SUI, LINK

```

### 1.4 محیط اجرا

- **Exchange**: Gate.io
- **Market**: USDT-M Perpetual Futures
- **VPS**: Linux
- **Repository**: https://github.com/Azadkashani/Crypto_bot
- **Directory**: /root/Robot_trader

### 1.5 اصول بنیادین پروژه

1. **Correctness First** — صحت منطق بر هر چیز دیگری مقدم است
2. **No Look-ahead Ever** — در هیچ نقطه‌ای از اطلاعات آینده استفاده نشود
3. **Faithful FTR Implementation** — پیاده‌سازی وفادار به مفهوم FTR
4. **Robust Market Structure** — ساختار بازار قوی و قابل اعتماد
5. **Risk Control** — کنترل ریسک در همه حال
6. **Realistic Execution Simulation** — شبیه‌سازی واقع‌بینانه اجرا
7. **Backtest Integrity** — یکپارچگی Backtest
8. **Memory Efficiency** — بهینه‌سازی مصرف حافظه
9. **Speed** — سرعت پردازش
10. **Maintainability** — قابلیت نگهداری

---

## 2. استراتژی FTR

### 2.1 تعریف مفهومی

**FTR = Failure To Return**

قیمت یک ناحیه/سطح مهم را با یک حرکت قدرتمند می‌شکند.

پس از Breakout، قیمت به جای اینکه به سطح شکسته‌شده برگردد، یک اصلاح محدود انجام می‌دهد و یک Base تشکیل می‌دهد.

سپس قیمت در همان جهت حرکت قدرتمند دیگری انجام می‌دهد.

این ساختار یک **FTR Zone** ایجاد می‌کند.

بعداً قیمت ممکن است برای اولین بار به این Zone برگردد.

این اولین بازگشت **FTB (First Time Back)** است.

ورود اصلی Strategy بر اساس First Time Back به FTR Zone طراحی شده است.

### 2.2 اجزای FTR

```

1. Market Structure    → ساختار بازار
2. Important Level     → سطح مهم
3. Breakout           → شکست سطح
4. Impulse            → حرکت قدرتمند
5. Base               → تثبیت/اصلاح محدود
6. FTR Zone           → ناحیه FTR
7. First Time Back    → اولین بازگشت
8. Reaction           → واکنش قیمت
9. Continuation       → ادامه حرکت

```

### 2.3 قوانین بنیادین استراتژی

- FTR باید بر اساس Price Action و Market Structure تشخیص داده شود
- استفاده از اندیکاتور به عنوان هسته اصلی ممنوع است
- Break باید واقعی و از نظر ساختاری معتبر باشد
- کیفیت حرکت Impulse اهمیت دارد
- Base باید ویژگی‌های لازم برای تشکیل FTR را داشته باشد
- Zone باید از ساختار واقعی بازار استخراج شود
- Freshness زون باید بررسی شود
- اولین Touch / First Touch Back اهمیت ویژه دارد
- زون‌هایی که قبلاً مصرف شده‌اند باید از زون Fresh تفکیک شوند
- Market Structure باید در اعتبارسنجی FTR لحاظ شود
- Supply/Demand context باید در تحلیل لحاظ شود
- کیفیت ستاپ باید بر تعداد معاملات اولویت داشته باشد
- ستاپ‌های ضعیف نباید فقط برای افزایش تعداد معاملات وارد سیستم شوند

### 2.4 آنچه ممنوع است

- استفاده از اطلاعات آینده (Look-ahead Bias)
- تغییر Strategy برای بهتر شدن Backtest
- R:R ثابت (مانند 1:2 یا 1:3)
- TP ثابت بدون توجه به Structure
- SL درصدی ثابت به عنوان هسته Strategy
- ورود چندباره به یک FTR به عنوان First Time Back
- Scan کردن ارزهایی خارج از Universe تعریف‌شده
- ارسال Order واقعی در Paper Mode
- Hard-code کردن API credentials
- اضافه کردن Indicatorهای غیرضروری به هسته FTR
- Optimization زودهنگام
- ایجاد فایل‌های اضافی بدون نیاز

### 2.5 R:R دینامیک

R:R نباید مقدار ثابت داشته باشد.

```

Risk/Reward برای هر معامله به صورت Dynamic و بر اساس:

· ساختار FTR
· محل Invalidation
· کیفیت Zone
· فاصله تا Target
· Supply/Demand مقابل
· Market Structure
· فضای حرکتی موجود
· کیفیت و اعتبار Setup

SL = بر اساس ساختار و Invalidation واقعی
TP = بر اساس ساختار بازار و Target منطقی
R:R = نتیجه تحلیل، نه یک ورودی ثابت اجباری

```

---

## 3. معماری سیستم

### 3.1 فلسفه طراحی

معماری بر پایه **جداسازی دقیق مسئولیت‌ها** و **Pipeline-Based Processing** است.

اصل بنیادین:

> **منطق استراتژی مستقل از محیط اجراست و در تمام محیط‌ها (Backtest/Paper/Live) یکسان عمل می‌کند.**

این اصل تضمین می‌کند که:
- نتایج Backtest معتبر و قابل اعتماد باشند
- انتقال از Paper به Live بدون تغییر منطق استراتژی انجام شود
- هر کامپوننت به صورت مستقل قابل تست و Debug باشد

### 3.2 معماری لایه‌ای

```

┌─────────────────────────────────────────────────────────────────┐
│                     CONFIGURATION LAYER                         │
│              (YAML Files + Environment Variables)               │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│                         DATA LAYER                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Data        │  │ Cache       │  │ Data Quality        │   │
│   │ Provider    │  │ Manager     │  │ Validator           │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│                    MARKET STRUCTURE LAYER                       │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Swing       │  │ Structure   │  │ Multi-Timeframe     │   │
│   │ Detector    │  │ Analyzer    │  │ Coordinator         │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│                      FTR DETECTION LAYER                        │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Breakout    │  │ Impulse     │  │ Base                │   │
│   │ Detector    │  │ Detector    │  │ Detector            │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Zone        │  │ Freshness   │  │ FTB                 │   │
│   │ Constructor │  │ Tracker     │  │ Detector            │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│                      SIGNAL GENERATION LAYER                    │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Entry       │  │ SL          │  │ TP                  │   │
│   │ Calculator  │  │ Calculator  │  │ Calculator          │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Quality     │  │ Signal      │  │ Setup               │   │
│   │ Assessor    │  │ Generator   │  │ Validator           │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│                      RISK MANAGEMENT LAYER                      │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Position    │  │ Exposure    │  │ Risk                │   │
│   │ Sizer       │  │ Manager     │  │ Validator           │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│                      EXECUTION LAYER                            │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Backtest    │  │ Paper       │  │ Live                │   │
│   │ Executor    │  │ Executor    │  │ Executor            │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY LAYER                          │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│   │ Logger      │  │ Metrics     │  │ Safety              │   │
│   │             │  │ Collector   │  │ Monitor             │   │
│   └─────────────┘  └─────────────┘  └─────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘

```

### 3.3 تصمیمات کلیدی معماری

| تصمیم | دلیل فنی |
|----------|-----------|
| **استراتژی مبتنی بر Pipeline** | هر مرحله از تشخیص FTR می‌تواند مستقل تست شود |
| **جداسازی استراتژی از اجرا** | امکان استفاده از منطق یکسان در Backtest/Paper/Live |
| **لایه انتزاعی داده** | Strategy Engine مستقل از API صرافی |
| **خارج‌سازی پیکربندی** | بدون Hard-code، امکان تست A/B پارامترها |
| **Backtest رویداد-محور** | جلوگیری از Look-ahead Bias |
| **مدیریت چرخه حیات Zone** | Zoneها حالت دارند، برای منطق FTR حیاتی است |

---

## 4. ساختار دایرکتوری

```

/root/Robot_trader/
├── config/
│   ├── init.py
│   ├── settings.yaml           # تنظیمات اصلی
│   ├── symbols.yaml            # لیست ارزها
│   ├── strategy_params.yaml    # پارامترهای استراتژی
│   └── risk_params.yaml        # پارامترهای ریسک
│
├── src/
│   ├── init.py
│   │
│   ├── data/
│   │   ├── init.py
│   │   ├── data_provider.py    # رابط داده
│   │   ├── gate_io.py          # اتصال Gate.io
│   │   ├── historical.py       # داده تاریخی
│   │   └── cache.py            # مدیریت کش
│   │
│   ├── market_structure/
│   │   ├── init.py
│   │   ├── swing_detector.py   # تشخیص Swing
│   │   ├── structure_analyzer.py # تحلیل ساختار
│   │   └── levels.py           # سطوح مهم
│   │
│   ├── ftr/
│   │   ├── init.py
│   │   ├── breakout_detector.py # تشخیص شکست
│   │   ├── impulse_detector.py  # تشخیص Impulse
│   │   ├── base_detector.py     # تشخیص Base
│   │   ├── zone_constructor.py  # ساخت Zone
│   │   ├── freshness_tracker.py # ردیابی Freshness
│   │   ├── ftb_detector.py      # تشخیص FTB
│   │   └── ftr_engine.py        # موتور اصلی FTR
│   │
│   ├── signal/
│   │   ├── init.py
│   │   ├── entry_calculator.py  # محاسبه ورود
│   │   ├── sl_calculator.py     # محاسبه SL
│   │   ├── tp_calculator.py     # محاسبه TP
│   │   ├── quality_assessor.py  # ارزیابی کیفیت
│   │   └── signal_generator.py  # تولید سیگنال
│   │
│   ├── risk/
│   │   ├── init.py
│   │   ├── position_sizer.py    # اندازه پوزیشن
│   │   ├── exposure_manager.py  # مدیریت اکسپوژر
│   │   └── risk_validator.py    # اعتبارسنجی ریسک
│   │
│   ├── execution/
│   │   ├── init.py
│   │   ├── base_executor.py     # رابط اجرا
│   │   ├── backtest_executor.py # اجرای Backtest
│   │   ├── paper_executor.py    # اجرای Paper
│   │   └── live_executor.py     # اجرای Live (آینده)
│   │
│   ├── backtest/
│   │   ├── init.py
│   │   ├── event_engine.py      # موتور رویداد
│   │   ├── time_controller.py   # کنترل زمان
│   │   ├── equity_tracker.py    # ردیاب Equity
│   │   └── trade_recorder.py    # ثبت معاملات
│   │
│   ├── strategy/
│   │   ├── init.py
│   │   └── types/
│   │       ├── init.py
│   │       ├── market_structure.py  # تایپ‌های ساختار بازار
│   │       └── ftr_types.py         # تایپ‌های FTR
│   │
│   └── utils/
│       ├── init.py
│       ├── logger.py            # لاگ‌گیری
│       ├── validators.py        # اعتبارسنجی
│       └── time_utils.py        # ابزار زمان
│
├── tests/
│   ├── unit/
│   │   ├── test_swing_detector.py
│   │   ├── test_breakout_detector.py
│   │   ├── test_base_detector.py
│   │   ├── test_zone_constructor.py
│   │   ├── test_ftb_detector.py
│   │   ├── test_ftr_detection.py
│   │   ├── test_no_lookahead.py
│   │   └── ...
│   │
│   └── integration/
│       ├── test_ftr_pipeline.py
│       ├── test_backtest_engine.py
│       └── ...
│
├── scripts/
│   ├── download_data.py         # دانلود داده تاریخی
│   ├── run_backtest.py          # اجرای Backtest
│   └── run_paper_trading.py     # اجرای Paper Trading
│
├── docs/
│   └── ARCHITECTURE.md          # این مستند
│
├── logs/                        # لاگ‌های سیستم
├── data/                        # داده‌های ذخیره‌شده
├── .env.example                 # نمونه متغیرهای محیطی
├── requirements.txt             # وابستگی‌ها
├── pyproject.toml               # پیکربندی پروژه
└── README.md

```

---

## 5. لایه‌های سیستم

### 5.1 لایه پیکربندی (Configuration Layer)

**مسئولیت**: مدیریت تمام تنظیمات سیستم

**اصول**:
- هیچ پارامتر Strategy نباید Hard-code شود
- API credentials از Environment Variables خوانده شوند
- اعتبارسنجی پیکربندی در زمان راه‌اندازی
- پیکربندی نامعتبر از شروع سیستم جلوگیری می‌کند

**فایل‌های پیکربندی**:

```yaml
# config/symbols.yaml
symbols:
  - BTC_USDT
  - ETH_USDT
  - SOL_USDT
  - XRP_USDT
  - DOGE_USDT
  - HYPE_USDT
  - BNB_USDT
  - ZEC_USDT
  - ADA_USDT
  - UNI_USDT
  - SUI_USDT
  - LINK_USDT
```

```yaml
# config/strategy_params.yaml
swing_detection:
  pivot_left: 3
  pivot_right: 3
  min_swing_distance_pct: 0.001

breakout_detection:
  break_method: "close"
  min_break_distance_pct: 0.001
  confirmation_candles: 1

impulse_detection:
  min_impulse_candles: 2
  max_impulse_candles: 10
  min_impulse_distance_pct: 0.003

base_detection:
  min_base_candles: 3
  max_base_candles: 20
  max_retracement_pct: 0.382
  max_base_range_pct: 0.30

ftb_detection:
  max_ftb_wait_candles: 50
  min_touch_depth_pct: 0.0
  max_touch_depth_pct: 0.8
```

```yaml
# config/risk_params.yaml
risk:
  risk_per_trade: 0.01
  max_concurrent_positions: 4
  max_position_per_symbol: 1
  max_total_exposure: 0.10
  max_leverage: 5
```

5.2 لایه داده (Data Layer)

مسئولیت: دریافت و استانداردسازی داده بازار

اجزا:

· DataProvider — رابط انتزاعی
· GateIOProvider — پیاده‌سازی Gate.io
· HistoricalProvider — بارگذاری داده تاریخی
· CacheManager — مدیریت کش
· DataNormalizer — نرمال‌سازی داده

اصول:

· Strategy Engine مستقل از API صرافی
· داده‌ها نرمال‌سازی شوند
· کش برای جلوگیری از دریافت تکراری

5.3 لایه ساختار بازار (Market Structure Layer)

مسئولیت: تحلیل ساختار قیمت

اجزا:

· SwingDetector — تشخیص Swing High/Low
· StructureAnalyzer — تحلیل روند و BOS/CHoCH
· MultiTimeframeCoordinator — هماهنگی تایم‌فریم‌ها

5.4 لایه تشخیص FTR (FTR Detection Layer)

مسئولیت: شناسایی الگوهای FTR

اجزا:

· BreakoutDetector — تشخیص شکست ساختاری
· ImpulseDetector — تشخیص حرکت Impulse
· BaseDetector — تشخیص Base/Consolidation
· ZoneConstructor — ساخت FTR Zone
· FTBDetector — تشخیص First Time Back

5.5 لایه تولید سیگنال (Signal Generation Layer)

مسئولیت: تولید سیگنال معاملاتی

اجزا:

· EntryCalculator — محاسبه قیمت ورود
· SLCalculator — محاسبه حد ضرر
· TPCalculator — محاسبه حد سود
· QualityAssessor — ارزیابی کیفیت
· SignalGenerator — تولید سیگنال نهایی

5.6 لایه مدیریت ریسک (Risk Management Layer)

مسئولیت: مدیریت ریسک و اندازه پوزیشن

اصول:

· ریسک هر معامله از equity حساب
· حداکثر ۴ پوزیشن همزمان
· حداکثر ۱ پوزیشن روی هر نماد
· منطق Signal مستقل از Position Size

5.7 لایه اجرا (Execution Layer)

مسئولیت: اجرای معاملات در محیط‌های مختلف

اجزا:

· BacktestExecutor — اجرای شبیه‌سازی‌شده
· PaperExecutor — اجرای Paper Trading
· LiveExecutor — اجرای واقعی (آینده)

---

6. Pipeline تشخیص FTR

```
Market Data (OHLCV)
    ↓
[1] Swing Detection
    - شناسایی Swing High/Low با الگوریتم Pivot
    - تأخیر تأیید: N کندل (Configurable)
    ↓
[2] Market Structure Analysis
    - تعیین روند (HH/HL = Bullish, LH/LL = Bearish)
    - شناسایی BOS (Break of Structure)
    - شناسایی سطوح مهم (Major Swing Levels)
    ↓
[3] Breakout Detection
    - بررسی عبور قیمت از سطح مهم
    - اعتبارسنجی قدرت شکست
    - تأیید شکست با کندل Close
    ↓
[4] Impulse Detection
    - اندازه‌گیری حرکت پس از شکست
    - بررسی قدرت و فاصله حرکت
    - جدا کردن Impulse از Noise
    ↓
[5] Base Detection
    - شناسایی اصلاح محدود پس از Impulse
    - اعتبارسنجی کیفیت Base
    - تعیین مرزهای Base
    ↓
[6] Continuation Confirmation
    - تأیید حرکت ادامه‌دهنده پس از Base
    - اعتبارسنجی خروج از Base
    ↓
[7] FTR Zone Construction
    - ساخت Zone از مرزهای Base
    - تعیین Upper/Lower Bound
    - ثبت متادیتای کامل
    ↓
[8] Zone Freshness Tracking
    - ردیابی وضعیت Zone در طول زمان
    - به‌روزرسانی با هر کندل جدید
    ↓
[9] FTB Detection
    - بررسی اولین بازگشت قیمت به Zone
    - اعتبارسنجی کیفیت لمس
    - تغییر وضعیت Zone به FIRST_TOUCH
    ↓
[10] Signal Generation
    - تولید Signal کامل
    - ارسال به Risk Management
```

---

7. الگوریتم‌های تشخیص

7.1 الگوریتم Swing Detection

```
Input: OHLCV Data
Output: List of Swing Points

Algorithm:
1. برای هر کندل i:
   - اگر High[i] بالاترین در پنجره [i-left, i+right] باشد:
     → Swing High در کندل i
   - اگر Low[i] پایین‌ترین در پنجره [i-left, i+right] باشد:
     → Swing Low در کندل i

2. تأخیر تأیید:
   - Swing فقط پس از right کندل تأیید می‌شود
   - قبل از تأیید، Swing "Provisional" است

3. فیلتر نویز:
   - Swingهای خیلی نزدیک ادغام می‌شوند
   - حداقل فاصله قیمتی بین Swingها (Configurable)

Parameters:
- pivot_left: int (default: 3)
- pivot_right: int (default: 3)
- min_swing_distance: float (default: 0.001 = 0.1%)
```

7.2 الگوریتم Breakout Detection

```
Input: Price, Structure Level
Output: Breakout Result

Algorithm:
1. شناسایی نزدیک شدن قیمت به سطح
2. بررسی عبور قیمت از سطح:
   - Wick Break: High > Level (برای شکست مقاومت)
   - Close Break: Close > Level (تأیید قوی‌تر)

3. اعتبارسنجی شکست:
   - فاصله شکست: (Close - Level) / Level > threshold
   - قدرت کندل: بدنه کندل نسبت به Range
   - حجم (اختیاری): Volume نسبت به میانگین

4. جلوگیری از False Breakout:
   - الزام Close بالاتر از سطح
   - حداقل فاصله شکست
   - تأیید با کندل بعدی (اختیاری)

Parameters:
- break_method: "close" | "wick" (default: "close")
- min_break_distance: float (default: 0.001)
- confirmation_candles: int (default: 1)
```

7.3 الگوریتم Impulse Detection

```
Input: Breakout Point, Subsequent Candles
Output: Impulse Data

Algorithm:
1. شروع از کندل شکست
2. اندازه‌گیری حرکت در جهت شکست:
   - مسافت: قیمت پایان - قیمت شروع
   - مدت: تعداد کندل
   - سرعت: مسافت / مدت

3. اعتبارسنجی قدرت:
   - مسافت > min_impulse_distance (Configurable)
   - نسبت به ATR: مسافت / ATR > threshold
   - کیفیت کندل‌ها: درصد بدنه نسبت به Range

4. تشخیص پایان Impulse:
   - اولین کندل خلاف جهت با بدنه قابل توجه
   - یا کاهش شدید سرعت حرکت

Parameters:
- min_impulse_candles: int (default: 2)
- max_impulse_candles: int (default: 10)
- min_impulse_distance_pct: float (default: 0.003)
- min_body_ratio: float (default: 0.5)
```

7.4 الگوریتم Base Detection

```
Input: Post-Impulse Candles
Output: Base Data

Algorithm:
1. شناسایی شروع Base پس از پایان Impulse
2. تعیین محدوده Base:
   - Base High: بالاترین High در کندل‌های Base
   - Base Low: پایین‌ترین Low در کندل‌های Base

3. اعتبارسنجی کیفیت:
   - تعداد کندل: min_base_candles ≤ n ≤ max_base_candles
   - محدوده: Base Range نسبت به Impulse Distance
   - فشردگی: میانگین Range کندل‌ها نسبت به Base Range

4. اطمینان از عدم بازگشت کامل:
   - Retracement < max_retracement_pct (default: 38.2%)

Parameters:
- min_base_candles: int (default: 3)
- max_base_candles: int (default: 20)
- max_retracement_pct: float (default: 0.382)
- max_base_range_pct: float (default: 0.30)
```

7.5 الگوریتم ساخت FTR Zone

```
Input: Base Data, Impulse Data, Breakout Data
Output: FTR Zone

Algorithm:
1. تعیین مرزهای Zone:
   - برای LONG: Zone از Base Low تا Base High
   - برای SHORT: Zone از Base High تا Base Low

2. تعیین نقطه ابطال:
   - برای LONG: Base Low - buffer
   - برای SHORT: Base High + buffer
   - buffer = invalidation_buffer_pct × Base Height

3. ثبت متادیتا:
   - Creation Time = زمان تأیید Continuation
   - Breakout Reference = سطح شکسته‌شده
   - Impulse Reference = داده حرکت
   - Base Reference = داده Base

Parameters:
- invalidation_buffer_pct: float (default: 0.10 = 10% of Base Height)
- min_zone_height_pct: float (default: 0.0005)
```

7.6 الگوریتم تشخیص FTB

```
Input: FTR Zone, Current Candles
Output: FTB Event

Algorithm:
1. بررسی وضعیت Zone (فقط ACTIVE)
2. بررسی زمان انتظار (max_ftb_wait_candles)
3. بررسی ورود قیمت به Zone:
   - Wick Touch: Low ≤ Zone High (برای LONG)
   - Close Touch: Close ≤ Zone High (برای LONG)
   - Penetration: Close ≤ Zone Low (برای LONG)

4. اعتبارسنجی عمق نفوذ:
   - penetration_pct = depth / zone_height
   - min_touch_depth_pct ≤ penetration_pct ≤ max_touch_depth_pct

5. بررسی اولین لمس:
   - touch_count == 0

6. ثبت FTB و تغییر وضعیت Zone
```

---

8. مدیریت Zone و State Machine

8.1 نمودار وضعیت

```
                    ┌──────────────┐
                    │    NONE      │
                    └──────┬───────┘
                           │
                    Breakout + Impulse + Base Detected
                           │
                           ↓
                    ┌──────────────┐
                    │   CREATED    │
                    └──────┬───────┘
                           │
                    Continuation Confirmed
                           │
                           ↓
                    ┌──────────────┐
                    │    ACTIVE    │◄─────────────────┐
                    └──────┬───────┘                  │
                           │                          │
                    Price Returns to Zone             │
                           │                          │
                           ↓                          │
                    ┌──────────────┐                  │
                    │ FIRST_TOUCH  │                  │
                    └──────┬───────┘                  │
                           │                          │
              ┌────────────┴────────────┐             │
              │                         │             │
              ↓                         ↓             │
       ┌──────────────┐          ┌──────────────┐    │
       │    USED      │          │  INVALIDATED │    │
       └──────────────┘          └──────────────┘    │
              │                         │             │
              │                         │             │
              └─────────────────────────┴─────────────┘
                         (Terminal States)
```

8.2 تعریف وضعیت‌ها

وضعیت توضیح ورود خروج
NONE وضعیت اولیه شروع سیستم Breakout + Impulse + Base شناسایی شد
CREATED Zone ساخته شده از NONE Continuation تأیید شد یا Timeout
ACTIVE Zone فعال و آماده FTB از CREATED اولین Touch یا Invalidation
FIRST_TOUCH اولین بازگشت اتفاق افتاده از ACTIVE Signal صادر شد یا Reject شد
USED Zone استفاده شده از FIRST_TOUCH وضعیت نهایی
INVALIDATED ساختار ابطال شده از ACTIVE یا FIRST_TOUCH وضعیت نهایی
EXPIRED Zone منقضی شده از ACTIVE وضعیت نهایی

8.3 قوانین انتقال

```
CREATED → ACTIVE:
    - خروج از Base با قدرت کافی تأیید شد
    - یا N کندل پس از ساخت Zone گذشته (Timeout)

ACTIVE → FIRST_TOUCH:
    - قیمت وارد محدوده Zone شد (Wick یا Close)
    - این اولین Touch است

ACTIVE → INVALIDATED:
    - قیمت فراتر از نقطه ابطال Zone بسته شد
    - یا ساختار بازار تغییر اساسی کرد

ACTIVE → EXPIRED:
    - بیش از max_ftb_wait_candles کندل گذشته
    - قیمت به Zone بازنگشته است

FIRST_TOUCH → USED:
    - Signal معتبر تولید شد
    - یا Setup ارزیابی و Reject شد

FIRST_TOUCH → INVALIDATED:
    - قیمت از Zone عبور کرد و ساختار ابطال شد
```

---

9. جلوگیری از Look-ahead Bias

9.1 قانون طلایی

```
در هر نقطه زمانی t، سیستم فقط به داده‌هایی دسترسی دارد که در زمان t در دسترس بوده‌اند.
```

9.2 مکانیزم‌های جلوگیری

منبع Look-ahead مکانیزم جلوگیری
استفاده از کندل‌های آینده فقط داده تا timestamp فعلی ارسال شود
Swing با تأخیر تأیید Swing فقط پس از تأیید کامل استفاده شود
MTF ناهم‌تراز کندل HTF فقط هنگام بسته‌شدن کامل به‌روزرسانی شود
TP/SL با دانش آینده فقط از داده زمان ورود محاسبه شود
Zone با داده آینده فقط تا زمان ایجاد Zone اعتبارسنجی شود
استفاده از آینده برای تأیید شکست شکست فقط با کندل‌های بعد از آن تأیید شود

9.3 پیاده‌سازی در Backtest

```python
class TimeController:
    current_timestamp: int
    
    def get_available_data(self):
        """فقط داده تا current_timestamp را برمی‌گرداند"""
        return data[data.timestamp <= self.current_timestamp]
    
    def advance(self):
        """پیشروی به کندل بعدی"""
        self.current_timestamp = next_timestamp

# در هر گام:
# 1. TimeController به کندل بعدی می‌رود
# 2. استراتژی فقط داده تا timestamp فعلی را می‌بیند
# 3. سیگنال‌ها بر اساس داده در دسترس تولید می‌شوند
# 4. اجرا در کندل بعدی شبیه‌سازی می‌شود
```

9.4 تست‌های عدم Look-ahead

```python
def test_causal_detection():
    """تست اینکه تشخیص FTR فقط از داده‌های گذشته استفاده می‌کند"""
    
    # پردازش تا کندل 30
    for i in range(2, 30):
        engine.process_bar(ohlcv_data, i)
    
    zones_at_30 = engine.get_all_zones()
    
    # بازنشانی و پردازش تا کندل 50
    engine.reset()
    for i in range(2, 50):
        engine.process_bar(ohlcv_data, i)
    
    zones_at_50 = engine.get_all_zones()
    
    # Zoneهای تشخیص داده شده در کندل 30 نباید تحت تأثیر داده‌های بعدی باشند
    zone_ids_at_30 = {z.zone_id for z in zones_at_30}
    zone_ids_at_50 = {z.zone_id for z in zones_at_50}
    
    assert zone_ids_at_30.issubset(zone_ids_at_50)
```

---

10. محاسبه Entry/SL/TP

10.1 Entry Calculation

```
برای LONG:
- Zone Reference: FTR Zone (Base Low تا Base High)
- Entry Area: نیمه پایینی Zone (بین Zone Mid و Zone Low)
- Entry Price: بر اساس عمق نفوذ و کیفیت FTB
  - اگر Wick وارد Zone شد: Entry = Zone Mid
  - اگر Close وارد Zone شد: Entry = Zone Low + buffer

برای SHORT:
- Entry Area: نیمه بالایی Zone
- Entry Price: معکوس منطق LONG

عوامل مؤثر:
- عمق نفوذ FTB به Zone
- فاصله تا نقطه ابطال
- کیفیت لمس
```

10.2 SL Calculation

```
برای LONG:
- Primary Invalidation: Zone Low - buffer
- Structure Invalidation: آخرین Swing Low مهم زیر Zone
- SL = پایین‌ترین نقطه ابطال معتبر
- حداقل فاصله: min_stop_distance (Configurable)

برای SHORT:
- Primary Invalidation: Zone High + buffer
- Structure Invalidation: آخرین Swing High مهم بالای Zone
- SL = بالاترین نقطه ابطال معتبر

قانون:
"SL باید جایی باشد که در صورت رسیدن، فرضیه FTR ابطال شود."
```

10.3 TP Calculation

```
منابع Target (به ترتیب اولویت):

1. Opposing Supply/Demand Zone
   - نزدیک‌ترین Zone عرضه/تقاضای معتبر در جهت معامله

2. Major Swing Level
   - آخرین Swing High/Low مهم قبل از شروع حرکت

3. Liquidity Pool
   - تجمع Stop Lossهای معامله‌گران خلاف جهت

4. Structure Projection
   - اندازه حرکت Impulse اولیه در جهت ادامه

الگوریتم:
1. شناسایی تمام Targetهای بالقوه در جهت معامله
2. محاسبه فاصله تا هر Target
3. انتخاب نزدیک‌ترین Target با فضای حرکتی کافی
4. اگر Target مناسبی وجود ندارد → Signal Reject

قانون:
"TP از ساختار بازار استخراج می‌شود، نه از R:R ثابت."
```

10.4 محاسبه R:R

```
R:R = Potential Reward / Risk

Potential Reward = TP - Entry (برای LONG) یا Entry - TP (برای SHORT)
Risk = Entry - SL (برای LONG) یا SL - Entry (برای SHORT)

R:R خروجی Strategy است، نه ورودی ثابت.
اگر R:R به اندازه کافی مناسب نباشد، Trade می‌تواند Reject شود.
```

---

11. مدیریت ریسک

11.1 پارامترهای ریسک

پارامتر پیش‌فرض توضیح
risk_per_trade 0.01 (۱٪) درصد equity ریسک‌شده در هر معامله
max_concurrent_positions 4 حداکثر تعداد پوزیشن‌های همزمان باز
max_position_per_symbol 1 حداکثر پوزیشن روی یک نماد
max_total_exposure 0.10 (۱۰٪) حداکثر مارجین کل به عنوان درصد equity
max_leverage 5x حداکثر اهرم مجاز
min_stop_distance 0.001 (۰.۱٪) حداقل فاصله حد ضرر
max_position_notional None حداکثر ارزش Notional هر پوزیشن

11.2 محاسبه اندازه پوزیشن

```
Position Size = (Account Equity × Risk Per Trade) / Stop Distance

مثال:
Account Equity = $10,000
Risk Per Trade = 1% = $100
Stop Distance = 1% of price = $100
Position Size = $100 / $100 = 1 unit

با Leverage:
Margin Required = Position Size / Leverage
```

11.3 قوانین اکسپوژر

```
1. حداکثر ۴ پوزیشن همزمان
2. حداکثر ۱ پوزیشن روی هر نماد
3. مجموع اکسپوژر ≤ max_total_exposure
4. اگر چند Setup همزمان: بهترین‌ها بر اساس Score انتخاب شوند
5. محدودیت‌ها نباید Score یا کیفیت Signal را تغییر دهند
```

---

12. Backtesting

12.1 معماری Backtest

```
Backtest Engine
├── Data Loader
│   └── بارگذاری داده تاریخی از پیش دانلود شده
│
├── Event Queue
│   ├── مرتب‌سازی تمام کندل‌ها به ترتیب زمانی
│   ├── پردازش هر کندل به عنوان رویداد
│   └── حفظ همگام‌سازی زمانی
│
├── Time Controller
│   ├── پیشروی زمان کندل به کندل
│   ├── اطمینان از ترازبندی صحیح کندل‌های MTF
│   └── ردیابی timestamp فعلی
│
├── Strategy Hook
│   ├── فراخوانی استراتژی در هر بسته‌شدن کندل
│   ├── ارسال فقط داده موجود در timestamp فعلی
│   └── دریافت سیگنال‌ها
│
├── Risk Hook
│   ├── اعتبارسنجی سیگنال‌ها
│   ├── محاسبه اندازه پوزیشن
│   └── اعمال محدودیت‌های اکسپوژر
│
├── Execution Simulator
│   ├── شبیه‌سازی Fill سفارش
│   ├── اعمال مدل کارمزد
│   ├── اعمال مدل لغزش
│   └── ردیابی چرخه حیات پوزیشن
│
├── Equity Tracker
│   ├── Mark-to-Market پوزیشن‌ها
│   ├── محاسبه PnL تحقق‌نیافته
│   └── ردیابی منحنی equity و drawdown
│
└── Results Recorder
    ├── ثبت تمام معاملات
    ├── تولید آمار
    └── خروجی گزارش عملکرد
```

12.2 مدل کارمزد و لغزش

کامپوننت مدل توضیح
کارمزد Taker 0.05٪ هر معامله اعمال بر ورود و خروج
لغزش 0.02٪ هر معامله فقط بر سفارش‌های Market
Funding اختیاری، هر ۸ ساعت اعمال بر پوزیشن‌های نگهداری‌شده

```
Fee = Notional Value × Fee Rate
Slippage = Notional Value × Slippage Rate

برای LONG:
Entry Cost = Entry Price × Size × (1 + Fee + Slippage)
Exit Proceeds = Exit Price × Size × (1 - Fee - Slippage)

برای SHORT:
Entry Proceeds = Entry Price × Size × (1 - Fee - Slippage)
Exit Cost = Exit Price × Size × (1 + Fee + Slippage)
```

12.3 گزارش Trade-by-Trade

```
برای هر Trade باید مشخص باشد:
- FTR Creation Time
- FTR Detection Time
- FTB Time
- Entry Price
- SL Price
- TP Price
- Exit Price
- Fees Paid
- Slippage Cost
- PnL
- R Multiple
- Exit Reason
```

---

13. Paper Trading

13.1 معماری Paper Trading

```
Paper Trading Engine
├── Data Feed (همانند Live)
│   └── داده بازار بلادرنگ از صرافی
│
├── Strategy Engine (همانند backtest/live)
│   └── تشخیص FTR و تولید سیگنال یکسان
│
├── Risk Manager (همانند backtest/live)
│   └── اندازه پوزیشن و اعتبارسنجی یکسان
│
├── Paper Executor
│   ├── شبیه‌سازی Fill سفارش
│   ├── استفاده از قیمت‌های واقعی بازار
│   ├── اعمال لغزش واقع‌بینانه
│   └── ردیابی پوزیشن‌های Paper
│
├── Equity Tracker
│   └── ردیابی equity و PnL Paper
│
└── Result Logging
    └── ردپای کامل حسابرسی
```

13.2 ثبت Signal

```
وقتی Signal ایجاد شد:
- Signal ID
- Symbol
- Direction
- Detection Time
- Current Price (Live)
- Planned Entry
- SL
- TP
- Risk
- Suggested Position Size
- Leverage
- FTR Zone
- FTR metadata
```

13.3 تفکیک قیمت‌ها

```
سیستم باید تفاوت بین:
- Signal Detection Price → قیمت هنگام تشخیص
- Actual Current Market Price → قیمت فعلی بازار
- Planned Entry → ورود برنامه‌ریزی‌شده
- Executed Paper Entry → ورود اجرا شده Paper

را کاملاً مشخص کند.
```

---

14. Live Trading

14.1 معماری Live Trading

```
Live Trading Engine
├── Data Feed
│   └── WebSocket بلادرنگ + REST API از Gate.io
│
├── Strategy Engine (یکسان با backtest/paper)
│   └── تشخیص FTR و تولید سیگنال
│
├── Risk Manager (یکسان با backtest/paper)
│   └── اندازه پوزیشن و اعتبارسنجی
│
├── Live Executor
│   ├── ثبت سفارش واقعی در Gate.io
│   ├── نظارت بر وضعیت سفارش
│   ├── تأیید Fill
│   └── ردیابی پوزیشن
│
├── Safety Layer
│   ├── جلوگیری از سفارش تکراری
│   ├── تشخیص داده قدیمی
│   ├── اعتبارسنجی اندازه سفارش
│   └── قابلیت توقف اضطراری
│
└── Monitoring
    ├── ردیابی بلادرنگ پوزیشن
    ├── نظارت بر equity
    └── سیستم هشدار
```

14.2 Safety Gates

```
قبل از ارسال هر Order واقعی:
1. بررسی Duplicate Order
2. بررسی Stale Data
3. بررسی Order Size Limits
4. بررسی Margin Sufficiency
5. بررسی Exchange Requirements
6. بررسی Emergency Stop Status
```

---

15. پیکربندی

15.1 فایل‌های پیکربندی

فایل محتوا
config/settings.yaml تنظیمات کلی سیستم
config/symbols.yaml لیست ارزهای مجاز
config/strategy_params.yaml پارامترهای استراتژی
config/risk_params.yaml پارامترهای ریسک

15.2 Environment Variables

```bash
# .env.example
GATE_IO_API_KEY=your_api_key_here
GATE_IO_API_SECRET=your_api_secret_here
TRADING_MODE=PAPER  # BACKTEST, PAPER, LIVE
LOG_LEVEL=INFO
```

15.3 اصول پیکربندی

```
Configurable ≠ Optimization

فعلاً هیچ Optimization یا Machine Learning انجام نشود.
هدف ابتدا ساخت یک Implementation صحیح و قابل اعتماد است.
```

---

16. تست‌ها

16.1 تست‌های واحد

کامپوننت تست‌ها
Swing Detector تشخیص صحیح Swing High/Low
Structure Analyzer تشخیص روند، BOS، CHoCH
Breakout Detector شکست معتبر در مقابل نامعتبر
Impulse Detector تشخیص حرکت Impulse
Base Detector تشخیص Base با کیفیت
Zone Constructor ساخت صحیح Zone
FTB Detector تشخیص اولین لمس
Entry/SL/TP Calculator محاسبات صحیح
Position Sizer اندازه پوزیشن صحیح

16.2 تست‌های یکپارچه‌سازی

Pipeline تست‌ها
FTR Full Pipeline ایجاد Zone انتها-به-انتها
MTF Synchronization ترازبندی صحیح تایم‌فریم‌ها
Backtest Engine پردازش زمانی بدون Look-ahead
Risk Management محدودیت‌های اکسپوژر

16.3 Fixtures تست

· داده OHLCV مصنوعی با الگوهای FTR شناخته‌شده
· داده برچسب‌گذاری‌شده با موقعیت‌های Zone مورد انتظار
· موارد لبه (حداقل کندل، نوسان شدید، شکاف‌ها)

---

17. لاگ‌گیری

17.1 سطوح لاگ

سطح کاربرد
DEBUG مراحل دقیق تشخیص FTR
INFO تولید سیگنال، باز/بسته‌شدن پوزیشن
WARNING اعتبارسنجی‌های ناموفق، شرایط غیرعادی
ERROR خطاهای اجرا، مشکلات داده
CRITICAL توقف اضطراری، نقص شدید

17.2 ساختار لاگ

```json
{
  "timestamp": 1700000000,
  "level": "INFO",
  "component": "ftr_engine",
  "event": "zone_created",
  "symbol": "BTC_USDT",
  "timeframe": "1h",
  "details": {
    "zone_id": "zone_123",
    "direction": "LONG",
    "zone_top": 50000,
    "zone_bottom": 49500
  }
}
```

17.3 اطلاعات ضروری در لاگ

```
در Live/Paper Mode باید بتوانیم بفهمیم:
- چه ارزی Scan شد
- چرا FTR شناسایی شد
- چرا FTR رد شد
- Zone کجا قرار دارد
- چرا Signal صادر شد
- Entry چیست
- SL چیست
- TP چیست
- RR چقدر است
- قیمت Live هنگام Signal چقدر بوده
- Timestamp چیست
```

---

18. امنیت

18.1 اصول امنیتی

· API Key و Secret هرگز در Source Code قرار نگیرند
· از Environment Variables استفاده شود
· API credentials هرگز در Log چاپ نشوند
· در Paper Trading هیچ Order واقعی ارسال نشود
· Real Trading باید Safety Gate مستقل داشته باشد

18.2 Safety Gates

```
قبل از ارسال هر Order واقعی:
1. بررسی Duplicate Order Prevention
2. بررسی Stale Market Data Detection
3. بررسی Invalid SL/TP Detection
4. بررسی Invalid Position Size Detection
5. بررسی Exchange Minimum Order Requirements
6. بررسی Precision / Tick Size / Lot Size
7. بررسی API Failure Handling
8. بررسی Emergency Stop Status
```

---

19. عملکرد

19.1 مدیریت حافظه

استراتژی پیاده‌سازی
پردازش جریانی داده پردازش کندل‌ها یک‌به‌یک
جمع‌آوری زباله پاکسازی صریح Zoneهای منقضی
محدودیت اندازه کش کش با اندازه ثابت با LRU
ساختارهای داده کارآمد استفاده محدود از NumPy/Pandas

19.2 بهینه‌سازی CPU

استراتژی پیاده‌سازی
اجتناب از محاسبات تکراری کش نقاط Swing
پردازش دسته‌ای پردازش چند نماد در دسته
حداقل‌سازی محاسبات اندیکاتور فقط اندیکاتورهای ضروری
خروج زودهنگام رد شدن از Pipeline اگر شکست تشخیص داده نشد

19.3 عملکرد هدف

· پردازش ۱ کندل در < ۱۰۰ms
· پردازش تاریخچه کامل ۱ نماد (۱ سال، ۱h) در < ۵ دقیقه
· Backtest ۱۲ نماد در ۶ ماه در < ۱ ساعت
· مصرف حافظه < ۲GB در طول Backtest

---

20. محدودیت‌ها و ابهامات

20.1 ابهامات نیازمند رفع

ابهام توضیح روش رفع
تعریف شکست معتبر قوانین دقیق برای شکست ساختاری Backtesting پارامترهای مختلف
تعریف Base پارامترهای دقیق برای شناسایی Base Backtesting پارامترهای مختلف
قدرت خروج نحوه اندازه‌گیری خروج از Base Backtesting پارامترهای مختلف
مصرف Zone دقیقاً چه زمانی Zone مصرف می‌شود تست و اعتبارسنجی
ترکیب تایم‌فریم سلسله‌مراتب بهینه Backtesting
روش اجرای ورود Limit در مقابل Market Paper Trading

20.2 آنچه هنوز نباید پیاده‌سازی شود

1. معاملات زنده: تا Paper Trading اعتبارسنجی نشود
2. مدل‌سازی Funding Rate: تا دوره‌های نگهداری مشخص نشود
3. تحلیل همبستگی: تا درک همپوشانی پوزیشن‌ها
4. منطق توقف متحرک: بعد از اعتبارسنجی TP/SL پایه
5. پشتیبانی چند صرافی: ابتدا Gate.io
6. بهبود یادگیری ماشین: ابتدا امتیازدهی مبتنی بر قانون
7. اندیکاتورهای پیچیده: ابتدا Price Action و حجم پایه
8. بهینه‌سازی خودکار: ابتدا بهینه‌سازی دستی

---

21. فازهای توسعه

فاز ۱: پایه (Foundation)

· تأیید معماری
· راه‌اندازی ساختار پروژه
· سیستم پیکربندی
· لایه داده با Gate.io

فاز ۲: ساختار بازار

· Swing Detector
· Structure Analyzer
· Multi-Timeframe
· تست‌های واحد

فاز ۳: هسته تشخیص FTR

· Breakout Detector
· Impulse Detector
· Base Detector
· Zone Constructor
· تست‌های واحد

فاز ۴: تولید سیگنال

· FTB Detector
· Entry/SL/TP Calculator
· Quality Assessor
· Signal Generator

فاز ۵: مدیریت ریسک

· Position Sizer
· Exposure Manager
· Risk Validator
· تست‌های واحد

فاز ۶: موتور Backtest

· Event Engine
· Execution Simulator
· Trade Recorder
· Results Analyzer

فاز ۷: Paper Trading

· Paper Executor
· Live Data Feed
· Signal Logger
· Position Tracker

فاز ۸: آماده‌سازی Live

· Live Executor
· Safety Layer
· Emergency Stop
· Monitoring

فاز ۹: اعتبارسنجی و بهینه‌سازی

· Backtest Parameter Optimization
· Paper Trading Validation
· Performance Analysis

فاز ۱۰: Live Trading

· استقرار تدریجی سرمایه
· نظارت مداوم
· بررسی عملکرد

---

22. ضمیمه: تایپ‌های داده

22.1 تایپ‌های ساختار بازار

```python
class SwingType(Enum):
    HIGH = "HIGH"
    LOW = "LOW"

class StructureType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"
    TRANSITIONING = "TRANSITIONING"

class BreakType(Enum):
    BOS = "BOS"      # Break of Structure
    CHOCH = "CHOCH"  # Change of Character

@dataclass
class SwingPoint:
    price: float
    timestamp: int
    swing_type: SwingType
    index: int
    is_confirmed: bool = False
    confirmation_time: Optional[int] = None

@dataclass
class StructureLevel:
    price: float
    level_type: str  # SUPPORT, RESISTANCE, DEMAND, SUPPLY
    created_timestamp: int
    last_touched_timestamp: Optional[int] = None
    touch_count: int = 0
    strength_score: float = 0.0
    is_consumed: bool = False

@dataclass
class StructureBreak:
    break_type: BreakType
    break_price: float
    break_timestamp: int
    broken_level: StructureLevel
    direction: str  # LONG, SHORT
    is_valid: bool = False
    break_strength: float = 0.0
```

22.2 تایپ‌های FTR

```python
class FTRDirection(Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class FTRZoneState(Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    FIRST_TOUCH = "FIRST_TOUCH"
    USED = "USED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"

class FTBTouchType(Enum):
    WICK = "WICK"
    CLOSE = "CLOSE"
    PENETRATION = "PENETRATION"

@dataclass
class DisplacementData:
    start_price: float
    end_price: float
    start_timestamp: int
    end_timestamp: int
    direction: str
    distance: float = 0.0
    candle_count: int = 0
    strength_score: float = 0.0

@dataclass
class BaseData:
    high: float
    low: float
    start_timestamp: int
    end_timestamp: int
    duration_bars: int = 0
    height: float = 0.0
    quality_score: float = 0.0
    compression_ratio: float = 0.0

@dataclass
class FTRZone:
    zone_id: str
    symbol: str
    timeframe: str
    direction: str
    zone_high: float
    zone_low: float
    zone_midpoint: float
    created_timestamp: int
    structure_reference: Optional[StructureLevel] = None
    structure_break: Optional[StructureBreak] = None
    displacement: Optional[DisplacementData] = None
    base: Optional[BaseData] = None
    invalidation_level: Optional[float] = None
    state: FTRZoneState = FTRZoneState.CREATED
    first_touch_timestamp: Optional[int] = None
    first_touch_price: Optional[float] = None
    first_touch_type: Optional[FTBTouchType] = None
    touch_count: int = 0

@dataclass
class FTBEvent:
    zone: FTRZone
    timestamp: int
    price: float
    touch_type: FTBTouchType
    penetration_depth: float = 0.0
    is_valid: bool = False
    validation_reasons: List[str] = None
```

---

پایان مستند

این مستند به عنوان مرجع اصلی معماری و استراتژی پروژه FTR Crypto Trading Bot استفاده می‌شود.

هرگونه تغییر در معماری یا استراتژی باید ابتدا در این مستند اعمال شود و سپس در کد پیاده‌سازی گردد.

نسخه: 1.0 
