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
                text = doc.load_page(i).get_text()
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
        except Exception as e:
            print(f"pypdf failed: {e}")

        print("[PDF] All text extraction methods failed or returned no text. The PDF might be an image without a text layer.")
        docs.append(SimpleDocument(page_content="[System Note: This PDF appears to be an image or scanned document without a text layer. Since OCR is disabled, no text could be extracted.]", metadata={"source": self.file_path, "page": 0}))
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
        if len(text) <= self.chunk_size:
            return [text]


        separator = self.separators[-1] 
        for sep in self.separators:
            if sep in text:
                separator = sep
                break
        

        
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text) # Fallback to char split

        # Merge splits into chunks
        good_splits = []
        current_chunk = []
        current_len = 0
        
        for s in splits:
            s_len = len(s)
            
            # If a single split is too big, recurse!
            if s_len > self.chunk_size:
                if current_chunk:
                    good_splits.append(separator.join(current_chunk))
                    current_chunk = []
                    current_len = 0
                # Use next level separators for this big part
                next_seps = self.separators[self.separators.index(separator)+1:] if separator in self.separators else []
                if not next_seps: next_seps = [""]
                sub_splitter = RecursiveTextSplitter(self.chunk_size, self.chunk_overlap, next_seps)
                good_splits.extend(sub_splitter._split_text(s))
                continue

            # Accumulate
            sep_len = len(separator) if current_chunk else 0
            if current_len + s_len + sep_len <= self.chunk_size:
                current_chunk.append(s)
                current_len += s_len + sep_len
            else:
                # Chunk is full
                if current_chunk:
                    good_splits.append(separator.join(current_chunk))
                
                # Handle overlap (simplified start fresh)
                current_chunk = [s]
                current_len = s_len
        
        if current_chunk:
            good_splits.append(separator.join(current_chunk))
            
        return good_splits
