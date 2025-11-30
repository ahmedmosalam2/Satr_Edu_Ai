import cv2
import numpy as np
from PIL import Image
import os

class ImagePreProcessor:
    def __init__(self):
        pass

    def load_image(self, image_path):
    
        if not os.path.exists(image_path):
            raise FileNotFoundError(f" Image not found at: {image_path}")
        return cv2.imread(image_path)

    def to_grayscale(self, image):
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def remove_noise(self, image):
        return cv2.medianBlur(image, 3)

    def thresholding(self, image):
 
        return cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    def preprocess_for_ocr(self, image_source):

        if isinstance(image_source, str):
            print(f" Loading image from path: {image_source}")
            img = self.load_image(image_source)
        
    
        elif isinstance(image_source, Image.Image):
            print(" Processing PIL Image object...")
           
            img = np.array(image_source)
        
            if img.shape[-1] == 3: 
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        else:
            raise ValueError("Unsupported input type. Send a file path or PIL Image.")

 
        gray = self.to_grayscale(img)
      
        thresh = self.thresholding(gray)

        print("✅ Preprocessing Done!")
      
        return Image.fromarray(thresh)


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Image Pre-processing Tool")

    parser.add_argument("image_path", type=str, help="The full path to the image file")
    

    args = parser.parse_args()

    processor = ImagePreProcessor()

    try:
        print(f"🔄 Processing: {args.image_path}")
        
    
        result_image = processor.preprocess_for_ocr(args.image_path)
        

        output_name = "processed_output.jpg"
        result_image.save(output_name)
        
        print(f" Done! Saved as: {output_name}")
        
    except Exception as e:
        print(f" Error: {e}")