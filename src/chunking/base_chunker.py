"""
src/chunking/base_chunker.py
────────────────────────────
Abstract base class for all chunking strategies.

كل strategy بتاخد ParsedPages وترجع chunks جاهزة للـ embedding.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class Chunk:
    """
    قطعة نص جاهزة للـ embedding والتخزين.
    """
    chunk_text: str
    chunk_metadata: Dict[str, Any] = field(default_factory=dict)

    # Compatible with existing DataChunk interface
    @property
    def page_content(self) -> str:
        return self.chunk_text

    @property
    def metadata(self) -> Dict[str, Any]:
        return self.chunk_metadata

    def __repr__(self):
        preview = self.chunk_text[:60].replace("\n", " ")
        return f"Chunk(chars={len(self.chunk_text)}, type={self.chunk_metadata.get('chunk_type', '?')}, preview='{preview}...')"


class BaseChunker(ABC):
    """
    Abstract base class — كل chunker لازم ينفذ:
    - name: اسم الاستراتيجية
    - chunk(): يقسم النصوص لـ chunks
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """اسم الاستراتيجية (مثلاً 'naive', 'structure', 'semantic')."""
        ...

    @abstractmethod
    def chunk(
        self,
        pages: list,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        **kwargs
    ) -> List[Chunk]:
        """
        قسّم الـ pages لـ chunks.

        Parameters:
        - pages: list of ParsedPage أو أي object عنده page_content و metadata
        - chunk_size: الحد الأقصى لحجم الـ chunk بالحروف
        - chunk_overlap: حروف الـ overlap بين chunks

        Returns:
        - list of Chunk
        """
        ...
