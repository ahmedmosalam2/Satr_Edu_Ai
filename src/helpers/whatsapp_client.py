"""
src/helpers/whatsapp_client.py
──────────────────────────────
Ultramsg WhatsApp API Client.

Ultramsg هو أسهل طريقة لبعت WhatsApp messages:
  - مجاني للتجربة
  - بيشتغل مع WhatsApp Business وWhatsApp العادي
  - API بسيط جداً
  - بيدعم الرسائل النصية، الصور، والـ templates

الإعداد:
  1. روح على https://app.ultramsg.com/
  2. سجّل وربط تليفونك
  3. جيب الـ instance_id والـ token من الـ dashboard
  4. حطهم في .env

الـ phone format المطلوب: 201012345678 (بدون +، مع كود البلد)
"""

import logging
import httpx
from typing import Optional
from src.helpers.config import get_settings

logger = logging.getLogger("uvicorn.error")


class WhatsAppClient:
    """
    Wrapper لـ Ultramsg API.
    
    استخدام:
        client = WhatsAppClient()
        await client.send_message("201012345678", "مرحباً يا محمد!")
    """

    BASE_URL = "https://api.ultramsg.com"

    def __init__(self):
        settings = get_settings()
        self.instance_id = settings.ULTRAMSG_INSTANCE_ID
        self.token = settings.ULTRAMSG_TOKEN
        self.enabled = bool(self.instance_id and self.token)

        if not self.enabled:
            logger.warning(
                "[WhatsApp] ULTRAMSG_INSTANCE_ID or ULTRAMSG_TOKEN not set. "
                "WhatsApp notifications are DISABLED."
            )

    def _build_url(self, endpoint: str) -> str:
        return f"{self.BASE_URL}/{self.instance_id}/{endpoint}"

    @staticmethod
    def _clean_phone(phone: str) -> str:
        """
        تنظيف رقم الهاتف — Ultramsg بيحتاج الرقم بدون + وبكود البلد.
        +201012345678 → 201012345678
        0201012345678 → 201012345678 (مصري)
        01012345678   → 201012345678 (مصري بدون كود)
        """
        phone = phone.strip().replace(" ", "").replace("-", "")
        if phone.startswith("+"):
            phone = phone[1:]
        # مصري بدون كود الدولة
        if phone.startswith("0") and len(phone) == 11:
            phone = "2" + phone
        return phone

    async def send_message(self, phone: str, message: str) -> Optional[str]:
        """
        بعت رسالة نصية على WhatsApp.
        
        Args:
            phone: رقم الهاتف (بأي format)
            message: نص الرسالة
            
        Returns:
            message_id لو نجح، None لو فشل
        """
        if not self.enabled:
            logger.info(f"[WhatsApp] DISABLED — would send to {phone}: {message[:50]}")
            return None

        clean = self._clean_phone(phone)

        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                response = await http.post(
                    self._build_url("messages/chat"),
                    data={
                        "token": self.token,
                        "to": clean,
                        "body": message,
                        "priority": 10,
                    },
                )
                response.raise_for_status()
                data = response.json()

                if data.get("sent") == "true" or data.get("id"):
                    msg_id = str(data.get("id", "sent"))
                    logger.info(f"[WhatsApp] ✅ Sent to {clean} — id={msg_id}")
                    return msg_id
                else:
                    logger.error(f"[WhatsApp] ❌ API error: {data}")
                    return None

        except httpx.HTTPStatusError as e:
            logger.error(f"[WhatsApp] HTTP error {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"[WhatsApp] Unexpected error: {e}")
            return None

    async def send_absence_alert_student(
        self,
        phone: str,
        student_name: str,
        absence_count: int,
        project_name: str,
    ) -> Optional[str]:
        """رسالة غياب للطالب نفسه."""
        message = (
            f"🎓 *منصة سطر التعليمية*\n\n"
            f"مرحباً {student_name} 👋\n\n"
            f"نود إعلامك أنك غبتَ عن *{absence_count} جلسات/امتحانات* في مادة *{project_name}*.\n\n"
            f"📌 التغيب المتكرر يؤثر على تقدمك الدراسي.\n"
            f"نتمنى لك التوفيق ونرجو حضورك في المرات القادمة. 💪"
        )
        return await self.send_message(phone, message)

    async def send_absence_alert_guardian(
        self,
        phone: str,
        student_name: str,
        guardian_name: str,
        absence_count: int,
        project_name: str,
    ) -> Optional[str]:
        """رسالة غياب لولي الأمر."""
        message = (
            f"🎓 *منصة سطر التعليمية — إشعار أولياء الأمور*\n\n"
            f"حضرة ولي أمر الطالب/ة *{student_name}*،\n\n"
            f"نود إعلامكم بأن ابنكم/ابنتكم غاب/ت عن *{absence_count} جلسات/امتحانات* "
            f"في مادة *{project_name}*.\n\n"
            f"📞 نرجو التواصل مع الطالب/ة لمتابعة حضوره/حضورها.\n\n"
            f"مع تحيات فريق سطر التعليمية 🙏"
        )
        return await self.send_message(phone, message)
