import os
from src.helper import OCRConfig
from src.ai_engine import OCREngine

def main():
 
    config = OCRConfig()

    os.makedirs(config.output_path, exist_ok=True)

    engine = OCREngine(config)

    image_file = 'test_exam.png'
    

    if not os.path.exists(image_file):
        print(f" Error: Image '{image_file}' not found!")
        return


    try:
        result = engine.process_image(image_file)
        print("\n Extraction Result:\n")
        print(result)
    except Exception as e:
        print(f" Error during inference: {e}")

if __name__ == "__main__":
    main()