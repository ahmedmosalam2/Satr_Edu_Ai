from enum import Enum

class ExamStatus(str, Enum):
    DRAFT    = "draft"     # تم الإنشاء بواسطة AI — لم يُوافق عليه بعد
    APPROVED = "approved"  # وافق عليه المعلم — متاح للطلاب
