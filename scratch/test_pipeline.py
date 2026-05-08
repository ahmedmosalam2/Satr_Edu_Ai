import sys
import os


# Add the project root to the path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pipeline.pipeline_manager import DocumentPipeline

def run_test():
    print("Initializing DocumentPipeline...")
    pipeline = DocumentPipeline()
    
    sample_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "sample.txt"))
    
    print(f"Testing pipeline with file: {sample_file}")
    
    # Process the file
    result = pipeline.process(
        file_path=sample_file,
        chunk_strategy="naive",
        chunk_size=100
    )
    
    print("\n--- Pipeline Result ---")
    print(f"Success: {result.success}")
    if not result.success:
        print(f"Error: {result.error}")
        return

    print(f"File Type: {result.file_type}")
    print(f"Pages Extracted: {result.pages_count}")
    print(f"Chunks Created: {result.chunks_count}")
    print(f"Total Time (ms): {result.total_time_ms:.2f}")
    
    print("\n--- Chunks Extracted ---")
    for i, chunk in enumerate(result.chunks):
        content = chunk.page_content.replace('\n', ' ')
        print(f"Chunk {i+1} [{len(content)} chars]: {content}")

if __name__ == "__main__":
    run_test()
