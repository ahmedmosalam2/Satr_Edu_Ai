from src.utils.content_processor import SemanticTextSplitter

print("⏳ Initializing SemanticTextSplitter...")
try:
    splitter = SemanticTextSplitter(chunk_size=500, min_similarity=0.4)
    print("✅ Initialized.")
except Exception as e:
    print(f"❌ Failed to initialize: {e}")
    exit(1)

text = "Artificial Intelligence is fascinating. It powers many modern applications. Machine learning is a subset of AI. Deep learning uses neural networks. \n\n Separately, cooking is a great hobby. You can make many delicious dishes. Pasta is my favorite. Pizza is also good."
texts = [text]
metadatas = [{"source": "test"}]

print("⏳ Creating documents...")
try:
    docs = splitter.create_documents(texts, metadatas)
    print(f"✅ Created {len(docs)} documents.")
    for i, doc in enumerate(docs):
        print(f"--- Chunk {i} ---")
        print(doc.page_content)
except Exception as e:
    print(f"❌ Failed to create documents: {e}")
