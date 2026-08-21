#!/bin/bash
set -e

echo "🔧 اصلاح datetime.utcnow در کل پروژه..."

cd ~/Crypto_bot

# پیدا کردن فایل‌هایی که datetime.utcnow دارند
files=$(grep -rl "datetime.utcnow" --include="*.py" .)

if [ -z "$files" ]; then
    echo "ℹ️ هیچ استفاده‌ای از datetime.utcnow پیدا نشد."
else
    echo "📁 فایل‌های زیر اصلاح می‌شوند:"
    echo "$files"
    for file in $files; do
        # جایگزینی datetime.utcnow با datetime.now(datetime.UTC)
        # در حالتی که به عنوان تابع استفاده شده (با پرانتز)
        sed -i 's/datetime\.utcnow()/datetime.now(datetime.UTC)/g' "$file"
        # در حالتی که به عنوان default بدون پرانتز استفاده شده
        sed -i 's/default=datetime\.utcnow/default=lambda: datetime.now(datetime.UTC)/g' "$file"
        # در حالتی که در انتساب استفاده شده
        sed -i 's/ = datetime\.utcnow/ = lambda: datetime.now(datetime.UTC)/g' "$file"
        # اضافه کردن import مربوط به UTC اگر لازم باشد
        if grep -q "from datetime import" "$file"; then
            # اگر import موجود است، مطمئن شویم UTC هم وارد شده
            if ! grep -q "UTC" "$file"; then
                sed -i '/from datetime import/a import UTC' "$file"
            fi
        else
            # اضافه کردن خط import در ابتدای فایل (بعد از docstring یا خط اول)
            sed -i '1i from datetime import datetime, UTC' "$file"
        fi
    done
fi

# اجرای تست‌ها
echo "🧪 اجرای تست‌ها..."
if ! pytest -q --disable-warnings; then
    echo "❌ تست‌ها شکست خوردند. اصلاح datetime را بررسی کنید."
    exit 1
fi

echo "✅ تست‌ها موفق بودند."

# Commit تغییرات
echo "📦 Commit تغییرات datetime..."
git add -A
git commit -m "fix: replace deprecated datetime.utcnow with timezone-aware datetime.now(datetime.UTC)" || echo "No changes to commit"

git push origin main

echo "🎉 اصلاح datetime انجام شد و به گیت‌هاب Push شد."
