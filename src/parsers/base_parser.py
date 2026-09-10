"""
src/parsers/base_parser.py
──────────────────────────
Abstract base class for all document parsers.

كل parser لازم يرجع list من ParsedPage:
  - page_content: النص المستخرج
  - metadata: معلومات إضافية (صفحة، مصدر، نوع، ...)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class ParsedPage:
    """
    صفحة/قطعة مستخرجة من ملف.
    نفس الـ interface بتاع LangChain Document عشان نكون compatible.
    """
    page_content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        preview = self.page_content[:80].replace("\n", " ")
        return f"ParsedPage(chars={len(self.page_content)}, page={self.metadata.get('page', '?')}, preview='{preview}...')"


class BaseParser(ABC):
    """
    Abstract base class — كل parser لازم ينفذ:
    - supported_extensions: قائمة الامتدادات المدعومة
    - parse(): يقرأ الملف ويرجع ParsedPage list
    """

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """الامتدادات اللي الـ parser ده بيدعمها (مثلاً ['.pdf'])."""
        ...

    @abstractmethod
    def parse(self, file_path: str, **kwargs) -> List[ParsedPage]:
        """
        قراءة الملف وتحويله لـ pages/sections.

        Parameters:
        - file_path: المسار الكامل للملف

        Returns:
        - list of ParsedPage
        """
        ...

    def can_parse(self, file_path: str) -> bool:
        """هل الـ parser ده يقدر يقرأ الملف ده؟"""
        import os
        ext = os.path.splitext(file_path)[-1].lower()
        return ext in self.supported_extensions
