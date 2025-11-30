import re

class TextCleaner:
    @staticmethod
    def common_clean(text):
        if not text: return ""
        
    
        text = re.sub(r'[\u0640]', '', text)
        

        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        
        return text.strip()

    @staticmethod
    def clean_arabic_exam(text):
        text = TextCleaner.common_clean(text)
        text = re.sub(r'(?i)(السؤال\s+)?(الأول|الثاني|الثالث|الرابع|الخامس|[\u0660-\u0669]+)(\s*:)?', r'\n\1\2:\n', text)
        text = re.sub(r'(بم تفسر|علل|ما النتائج المترتبة على|دلل تاريخيا)(\s*:?)', r'\n\1:\n', text)
        text = re.sub(r'(\b\d{3,4}\b)', r' \1 ', text) 

        return text

    @staticmethod
    def clean_math(text):
    
        text = TextCleaner.common_clean(text)
        

        arabic_nums = '٠١٢٣٤٥٦٧٨٩'
        english_nums = '0123456789'
        trans_table = str.maketrans(arabic_nums, english_nums)
        text = text.translate(trans_table)


        text = re.sub(r'(\d)\s*x\s*(\d)', r'\1 * \2', text, flags=re.IGNORECASE)
        

        text = re.sub(r'(\d)\s*/\s*(\d)', r'\1 / \2', text)
        

        text = text.replace('^', ' ^ ') # الأس
        
        return text

    @staticmethod
    def format_mcq(text):

    
        text = re.sub(r'(?<!\n)\s*(\(|-)\s*([أبجد])\s*(\)|-)', r'\n(\2) ', text)
        
        # نمط الإنجليزي (a) or a.
        text = re.sub(r'(?<!\n)\s*(\(|^)\s*([a-d])\s*(\)|\.)', r'\n(\2) ', text, flags=re.IGNORECASE)
        
        return text