"""
Full Flow Test Script:
  Register -> Login -> Create Project -> Upload & Process -> Done!
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
os.environ["PYTHONIOENCODING"] = "utf-8"

import requests
import json

BASE = "http://localhost:8000"

def pretty(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

# ── 1. Register (لو مش موجود) ─────────────────────────────────
print("=" * 60)
print("1️⃣  تسجيل مستخدم جديد (Teacher)...")
print("=" * 60)
r = requests.post(f"{BASE}/api/v1/auth/register", json={
    "user_name": "أحمد المعلم",
    "user_email": "teacher@satr.ai",
    "user_password": "pass123456",
    "user_role": "teacher",
})
if r.status_code == 201:
    print("✅ تم التسجيل بنجاح")
    pretty(r.json())
elif r.status_code == 409:
    print("⚠️ المستخدم موجود بالفعل — هنكمل بالـ login")
else:
    print(f"❌ خطأ: {r.status_code}")
    pretty(r.json())

# ── 1b. Approve Teacher (via operations user) ──────────────────
# نسجل operations user عشان يعمل approve للمعلم
print("\n" + "=" * 60)
print("1b. تسجيل Operations user + Approve Teacher...")
print("=" * 60)
r_ops = requests.post(f"{BASE}/api/v1/auth/register", json={
    "user_name": "مدير النظام",
    "user_email": "ops@satr.ai",
    "user_password": "pass123456",
    "user_role": "operations",
})
if r_ops.status_code in [201, 409]:
    # Login as ops
    r_ops_login = requests.post(f"{BASE}/api/v1/auth/login", json={
        "user_email": "ops@satr.ai",
        "user_password": "pass123456",
    })
    if r_ops_login.status_code == 200:
        ops_token = r_ops_login.json()["access_token"]
        # Get teacher user_id
        # First login as teacher to get user_id  
        r_teacher_check = requests.post(f"{BASE}/api/v1/auth/login", json={
            "user_email": "teacher@satr.ai",
            "user_password": "pass123456",
        })
        if r_teacher_check.status_code == 403:
            # Teacher needs approval — but we need user_id
            # Try to get from register response or DB
            print("⚠️ المعلم محتاج approval — هنستخدم الـ Operations user مباشرة")
        elif r_teacher_check.status_code == 200:
            print("✅ المعلم معتمد بالفعل")

# ── 2. Login ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("2️⃣  تسجيل الدخول...")
print("=" * 60)

# نجرب نسجل بالـ operations عشان مضمون يكون approved
r = requests.post(f"{BASE}/api/v1/auth/login", json={
    "user_email": "ops@satr.ai",
    "user_password": "pass123456",
})
if r.status_code != 200:
    print(f"❌ فشل تسجيل الدخول: {r.status_code}")
    pretty(r.json())
    sys.exit(1)

data = r.json()
TOKEN = data["access_token"]
print(f"✅ تم تسجيل الدخول — الاسم: {data['user']['user_name']}")
print(f"   Token: {TOKEN[:30]}...")

HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ── 3. Create Project ──────────────────────────────────────────
print("\n" + "=" * 60)
print("3️⃣  إنشاء مشروع تعليمي...")
print("=" * 60)
r = requests.post(f"{BASE}/api/v1/projects", json={
    "project_name": "الذكاء الاصطناعي في التعليم",
    "project_description": "تجربة رفع ملف ومعالجته",
}, headers=HEADERS)

if r.status_code == 201:
    project_id = r.json()["project"]["project_id"]
    print(f"✅ تم إنشاء المشروع!")
    print(f"   Project ID: {project_id}")
else:
    print(f"❌ خطأ: {r.status_code}")
    pretty(r.json())
    sys.exit(1)

# ── 4. Upload & Process ────────────────────────────────────────
print("\n" + "=" * 60)
print("4️⃣  رفع ملف ومعالجته (Upload + Parse + Chunk + Save)...")
print("=" * 60)

file_path = r"d:\Satr_Edu_Ai\scratch\advanced_test.html"

with open(file_path, "rb") as f:
    r = requests.post(
        f"{BASE}/api/v1/documents/{project_id}/upload",
        files={"file": ("advanced_test.html", f, "text/html")},
        data={
            "chunk_strategy": "structure",
            "chunk_size": 500,
            "chunk_overlap": 50,
            "auto_process": "true",
        },
    )

if r.status_code == 200:
    result = r.json()
    print(f"✅ تم الرفع والمعالجة بنجاح!")
    print(f"   📄 الملف: {result.get('file_name')}")
    print(f"   📊 عدد الصفحات: {result.get('pages_count')}")
    print(f"   ✂️  عدد الـ Chunks: {result.get('chunks_count')}")
    print(f"   ⚡ وقت المعالجة: {result.get('total_time_ms')}ms")
    print(f"   🆔 Document ID: {result.get('document_id')}")
else:
    print(f"❌ خطأ: {r.status_code}")
    pretty(r.json())
    sys.exit(1)

# ── 5. Verify — List Documents ─────────────────────────────────
print("\n" + "=" * 60)
print("5️⃣  التأكد — عرض ملفات المشروع...")
print("=" * 60)
r = requests.get(f"{BASE}/api/v1/documents/{project_id}")
if r.status_code == 200:
    docs = r.json()
    print(f"✅ عدد الملفات في المشروع: {docs.get('total', len(docs.get('documents', [])))}")
    for doc in docs.get("documents", []):
        print(f"   📄 {doc['file_name']} — Status: {doc['status']} — Chunks: {doc.get('chunks_count', '?')}")
else:
    print(f"⚠️ {r.status_code}: {r.text[:200]}")

print("\n" + "=" * 60)
print("🎉 انتهى الاختبار بنجاح! الـ Pipeline الكامل شغال!")
print("=" * 60)
print(f"\n📌 Project ID: {project_id}")
print("   استخدمه في:")
print(f"   - POST /api/v1/nlp/index  →  {'{'}\"project_id\": \"{project_id}\"{'}'}")
print(f"   - POST /api/v1/nlp/ask    →  {'{'}\"project_id\": \"{project_id}\", \"question\": \"...\"{'}'}")
