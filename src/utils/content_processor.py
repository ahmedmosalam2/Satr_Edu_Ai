import os

class DirectPDFLoader:
    """
    A manual PDF loader using 'pypdf' directly.
    Replaces langchain_community.document_loaders.PyPDFLoader to avoid Bus Error in WSL.
    """
    def __init__(self, file_path):
        self.file_path = file_path
    
    def load(self):
        try:
            import pypdf
        except ImportError:
            raise ImportError("pypdf is required. Please install it with `pip install pypdf`.")

        class SimpleDocument:
            def __init__(self, page_content, metadata):
                self.page_content = page_content
                self.metadata = metadata

        docs = []
        try:
            reader = pypdf.PdfReader(self.file_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    docs.append(SimpleDocument(page_content=text, metadata={"source": self.file_path, "page": i}))
        except Exception as e:
            print(f"Error reading PDF with pypdf: {e}")
        return docs


class RecursiveTextSplitter:
    """
    A manual text splitter implementing recursive splitting logic (Paragraphs -> Sentences -> Words).
    Replaces langchain_text_splitters to avoid crashes.
    Stable, fast, and does not require heavy ML libraries.
    """
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

        # Find the best separator that exists in the text
        separator = self.separators[-1] # Default to last one (char/space)
        for sep in self.separators:
            if sep in text:
                separator = sep
                break
        
        # Split by the separator
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
