# Codify - منصة تعلم البرمجة

منصة تعليمية تفاعلية لتعلم البرمجة باللغة العربية. تقدم دورات في مختلف مجالات البرمجة مع نظام تتبع التقدم واختبارات تفاعلية.

## المميزات
- تسجيل وتسجيل دخول مع تحقق من البريد الإلكتروني
- مسارات تعليمية متنوعة
- اختبارات تفاعلية
- لوحة متصدرين
- تتبع تقدم المستخدم
- واجهة مستخدم عربية سهلة الاستخدام

## المتطلبات
- Python 3.8 أو أحدث
- pip (مدير حزم Python)
- متصفح حديث

## التثبيت

1. قم بإنشاء بيئة افتراضية:
```bash
python -m venv venv
source venv/bin/activate  # على Linux/Mac
venv\Scripts\activate     # على Windows
```

2. قم بتثبيت المتطلبات:
```bash
pip install -r requirements.txt
```

3. قم بإعداد متغيرات البيئة:
```bash
export MAIL_USERNAME="your-email@gmail.com"
export MAIL_PASSWORD="your-app-password"
export SECRET_KEY="your-secret-key"
```

## التشغيل
1. قم بتشغيل الخادم:
```bash
python app.py
```

2. افتح المتصفح على العنوان:
```
http://localhost:8765
```

## هيكل المشروع
```
codify/
├── app.py              # تطبيق Flask الرئيسي
├── requirements.txt    # متطلبات Python
├── static/            # الملفات الثابتة
│   ├── images/        # الصور
│   └── styles/        # ملفات CSS
├── templates/         # قوالب HTML
└── instance/         # قاعدة البيانات
```

## المساهمة
نرحب بمساهماتكم! يرجى اتباع الخطوات التالية:
1. Fork المشروع
2. إنشاء فرع للميزة الجديدة
3. تقديم طلب Pull Request

## الترخيص
هذا المشروع مرخص تحت رخصة MIT. 