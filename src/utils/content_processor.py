import os

def fix_arabic_text(text: str) -> str:
    """Fix reversed/garbled Arabic text from old PDFs."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception:
        return text


class DirectPDFLoader:
    
    def __init__(self, file_path):
        self.file_path = file_path
    
    def load(self):
        docs = []
        
        class SimpleDocument:
            def __init__(self, page_content, metadata):
                self.page_content = page_content
                self.metadata = metadata

        try:
            import fitz
            doc = fitz.open(self.file_path)
            for i in range(len(doc)):
                page = doc.load_page(i)
                # Try simple text extraction
                text = page.get_text("text").strip()
                
                # If simple text is empty, try "blocks" mode which can sometimes recover text in complex layouts
                if not text:
                    blocks = page.get_text("blocks")
                    text = "\n".join([b[4] for b in blocks if b[4].strip()])
                
                if text and text.strip():
                    text = fix_arabic_text(text)
                    docs.append(SimpleDocument(page_content=text, metadata={"source": self.file_path, "page": i}))
            if docs: return docs
        except Exception as e:
            print(f"fitz failed: {e}")

        try:
            import pdfplumber
            with pdfplumber.open(self.file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        text = fix_arabic_text(text)
                        docs.append(SimpleDocument(page_content=text, metadata={"source": self.file_path, "page": i}))
            if docs: return docs
        except Exception as e:
            print(f"pdfplumber failed: {e}")

        try:
            import pypdf
            reader = pypdf.PdfReader(self.file_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    text = fix_arabic_text(text)
                    docs.append(SimpleDocument(page_content=text, metadata={"source": self.file_path, "page": i}))
            if docs: return docs
        except Exception as e:
            print(f"pypdf failed: {e}")

        print(f"[PDF] Could not extract text from: {self.file_path}. The file might not have a searchable text layer.")
        return docs


class RecursiveTextSplitter:

    def __init__(self, chunk_size, chunk_overlap, separators=None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def create_documents(self, texts, metadatas=None):
        class Document:
            def __init__(self, page_content, metadata):
                self.page_content = page_content
                self.metadata = metadata
        
        documents = []
        for i, text in enumerate(texts):
            meta = metadatas[i] if metadatas else {}
            chunks = self._split_text(text)
            for chunk in chunks:
                documents.append(Document(chunk, meta))
        return documents

    def _split_text(self, text):
        # 1. إذا كان النص صغير أصلاً ومفيش فيه سطور، رجعه زي ما هو
        if len(text) <= self.chunk_size and "\n" not in text:
            return [text.strip()]

        # 2. البحث عن أفضل Separator
        separator = self.separators[-1] 
        for sep in self.separators:
            if sep in text:
                separator = sep
                break
        
        # 3. التقسيم بناءً على الـ Separator
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        # 4. تجميع الـ Splits (هنا هنخلي التجميع أقل عدوانية للسطور)
        good_splits = []
        current_chunk = []
        current_len = 0
        
        for s in splits:
            s_strip = s.strip()
            if not s_strip: continue
            
            s_len = len(s_strip)
            
            # إذا كان الجزء الواحد أكبر من الحجم المطلوب، نقسمه داخلياً
            if s_len > self.chunk_size:
                if current_chunk:
                    good_splits.append(separator.join(current_chunk))
                    current_chunk = []
                    current_len = 0
                
                next_seps = self.separators[self.separators.index(separator)+1:] if separator in self.separators else []
                if not next_seps: next_seps = [""]
                sub_splitter = RecursiveTextSplitter(self.chunk_size, self.chunk_overlap, next_seps)
                good_splits.extend(sub_splitter._split_text(s_strip))
                continue

            # تجميع الحتت مع بعضها (Chunking)
            # ملحوظة: لو الـ separator هو سطر، هنكون حذرين أكتر في التجميع عشان ميطلعش "بلوك" واحد
            sep_len = len(separator) if current_chunk else 0
            
            # إذا كان التجميع هيعدي الـ chunk_size أو لو أحنا بنقسم بالسطور وعايزين نحافظ على استقلالية السطور
            if current_len + s_len + sep_len <= self.chunk_size:
                current_chunk.append(s_strip)
                current_len += s_len + sep_len
            else:
                if current_chunk:
                    good_splits.append(separator.join(current_chunk))
                current_chunk = [s_strip]
                current_len = s_len
        
        if current_chunk:
            good_splits.append(separator.join(current_chunk))
            
        return good_splits