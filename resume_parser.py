import re
import PyPDF2
import docx
import spacy
from pathlib import Path
class ResumeParser:
    def __init__(self):
        try:
            # Load spaCy English model for NER
            self.nlp = spacy.load("en_core_web_sm")
        except:
            print("WARNING: spaCy model 'en_core_web_sm' not found.")
            print("Run: python -m spacy download en_core_web_sm")
            self.nlp = None
    
    def extract_text(self, file_path):
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.pdf':
            return self._extract_from_pdf(file_path)
        elif file_extension in ['.docx', '.doc']:
            return self._extract_from_docx(file_path)
        elif file_extension == '.txt':
            return self._extract_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    
    def _extract_from_pdf(self, pdf_path):
        try:
            text = ""
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return ""
    
    def _extract_from_docx(self, docx_path):
        try:
            doc = docx.Document(docx_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error extracting DOCX: {e}")
            return ""
    
    def _extract_from_txt(self, txt_path):
        try:
            with open(txt_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except Exception as e:
            print(f"Error extracting TXT: {e}")
            return ""
    
    def extract_email(self, text):
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return emails[0] if emails else None
    
    def extract_phone(self, text):
        # Pattern for various phone formats
        phone_patterns = [
            r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # +1-234-567-8900
            r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (234) 567-8900
            r'\d{10}',  # 2345678900
        ]
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            if phones:
                return phones[0]
        return None
    
    def extract_name(self, text):
        if not self.nlp:
            # Fallback: extract first line as name
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if line and len(line.split()) <= 4 and len(line) < 50:
                    return line
            return None
        
        # Use spaCy NER to find person names
        doc = self.nlp(text[:1000])  # Process first 1000 chars
        
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                return ent.text
        
        # Fallback: extract first line
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line.split()) <= 4 and len(line) < 50:
                return line
        
        return None
    
    def extract_education(self, text):
        education_keywords = [
            'Bachelor', 'Master', 'PhD', 'B.Tech', 'M.Tech', 'MBA', 'B.Sc', 'M.Sc',
            'BCA', 'MCA', 'BE', 'ME', 'B.E', 'M.E', 'Diploma', 'Certificate'
        ]
        
        education = []
        lines = text.split('\n')
        
        for line in lines:
            for keyword in education_keywords:
                if keyword.lower() in line.lower():
                    education.append(line.strip())
                    break
        
        return list(set(education))  # Remove duplicates
    
    def extract_experience_years(self, text):
        # Pattern to find "X years" or "X+ years"
        pattern = r'(\d+)\+?\s*years?'
        matches = re.findall(pattern, text.lower())
        
        if matches:
            # Return the maximum years found
            return max([int(year) for year in matches])
        
        return 0