# 🚀 دليل تجربة Satr Edu AI (End-to-End Testing)

اتبع الترتيب ده عشان تتأكد إن كل حاجة شغالة تمام.

### 1. التأكد من الحالة (Health Check)
**Endpoint:** `GET /api/v1/base/health`
- **الغرض:** التأكد إن MongoDB و Qdrant والـ LLM شغالين.
- **النتيجة المتوقعة:** `{"status": "ok", ...}`

---

### 2. تسجيل الدخول (Authentication)
**Endpoint:** `POST /api/v1/auth/login`
- **Body (JSON):** `{"email": "admin@satr.ai", "password": "password123"}`
- **المهم:** خد الـ `access_token` وحطه في الـ Headers بتاعة باقي الطلبات كـ `Authorization: Bearer <TOKEN>`.

---

### 3. إنشاء مشروع تعليمي (Create Project)
**Endpoint:** `POST /api/v1/projects/`
- **Body (JSON):** `{"name": "Physics 101", "description": "High school physics course"}`
- **المهم:** خد الـ `project_id` عشان هتستخدمه في الرفع.

---

### 4. رفع ملف (Upload & OCR)
**Endpoint:** `POST /api/v1/data/upload`
- **Params:** `project_id=<ID>`
- **Body (Form-Data):** ارفع ملف PDF (جرب ملف ممسوح سكانر عشان تختبر Surya).
- **المهم:** السيرفر هيرد بـ `file_id`. المعالجة بتتم في الخلفية (Background Task).

---

### 5. الفهرسة (Indexing)
**Endpoint:** `POST /api/v1/nlp/index`
- **Body (JSON):** `{"project_id": "<ID>"}`
- **الغرض:** تحويل الملفات لـ Vectors عشان البحث. انتظر ثواني لحد ما يخلص.

---

### 6. سؤال وجواب (Chat / RAG)
**Endpoint:** `POST /api/v1/nlp/ask`
- **Body (JSON):** `{"project_id": "<ID>", "question": "ما هي قوانين نيوتن؟"}`
- **النتيجة المتوقعة:** إجابة دقيقة بناءً على الملف اللي رفعته.

---

### 7. توليد امتحان (Exam Generation)
**Endpoint:** `POST /api/v1/nlp/generate-exam`
- **Body (JSON):** `{"project_id": "<ID>", "num_questions": 5, "difficulty": "medium"}`
- **النتيجة المتوقعة:** ملف JSON فيه أسئلة واختيارات صحيحة.

---

### 8. اختبار الـ OCR المنفصل (Direct OCR Test)
**Endpoint:** `POST /api/v1/ocr/test/image`
- **Body (Form-Data):** ارفع أي صورة فيها كتابة.
- **الغرض:** التأكد إن Surya Service بترد على المشروع الأساسي.

---

### 9. التعلم التكيفي (Adaptive Learning)
**Endpoint:** `POST /api/v1/nlp/recommendations`
- **Body (JSON):** `{"project_id": "<ID>", "student_id": "<ID>"}`
- **الغرض:** الحصول على نصائح مذاكرة بناءً على أداء الطالب.
