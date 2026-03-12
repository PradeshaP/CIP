"""
resume_parser.py
Extracts raw text from PDF, DOCX, and TXT resume files.
Fixes applied:
  1. _extract_from_txt: was reading undefined `text` variable → fixed to file.read()
  2. clean_text: fixed broken indentation (extra leading space caused IndentationError)
  3. extract_name: now skips entities that look like organisations/cities; falls back
     to first SHORT capitalised line (a reliable heuristic for resume names)
"""

import PyPDF2
import docx
import spacy
import re
from pathlib import Path


class ResumeParser:

    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except Exception:
            print("WARNING: spaCy model 'en_core_web_sm' not found.")
            print("Run: python -m spacy download en_core_web_sm")
            self.nlp = None

    # ─────────────────────────────────────────────────────────────────── #
    #  TEXT EXTRACTION                                                      #
    # ─────────────────────────────────────────────────────────────────── #

    def extract_text(self, file_path: str) -> str:
        file_extension = Path(file_path).suffix.lower()

        if file_extension == ".pdf":
            return self._extract_from_pdf(file_path)
        elif file_extension in [".docx", ".doc"]:
            return self._extract_from_docx(file_path)
        elif file_extension == ".txt":
            return self._extract_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

    # ── BUG FIX 1 & 2: clean indentation; was also missing the file.read() ─ #
    def clean_text(self, text: str) -> str:
        # Remove bullet/arrow symbols (preserve ++ . # / for tech names like C++, C#)
        text = re.sub(r'[•●■►▪→]', ' ', text)
        # Collapse multiple spaces to one
        text = re.sub(r' +', ' ', text)
        # Collapse 3+ blank lines to 2
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Fix hyphenated line-breaks (word-\nnext → wordnext)
        text = re.sub(r'-\n', '', text)
        return text.strip()

    def _extract_from_pdf(self, pdf_path: str) -> str:
        try:
            text = ""
            with open(pdf_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return self.clean_text(text)
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return ""

    def _extract_from_docx(self, docx_path: str) -> str:
        try:
            doc  = docx.Document(docx_path)
            text = "\n".join(p.text for p in doc.paragraphs)
            return self.clean_text(text)
        except Exception as e:
            print(f"Error extracting DOCX: {e}")
            return ""

    # ── BUG FIX 1: was `return self.clean_text(text)` — `text` was never assigned ── #
    def _extract_from_txt(self, txt_path: str) -> str:
        try:
            with open(txt_path, "r", encoding="utf-8") as file:
                text = file.read()           # ← was missing; `text` was undefined
            return self.clean_text(text)
        except Exception as e:
            print(f"Error extracting TXT: {e}")
            return ""

    # ─────────────────────────────────────────────────────────────────── #
    #  NAME EXTRACTION (NLP)                                                #
    # ─────────────────────────────────────────────────────────────────── #

    # ── BUG FIX 3: old code returned on the FIRST PERSON entity, which is  #
    #    often a company/city mentioned early.  New logic:                   #
    #    • collect all PERSON entities in the first 1 000 chars              #
    #    • skip any that contain org-like words (Inc, Ltd, University, etc.) #
    #    • prefer the shortest one (likely the candidate's own name)         #
    #    • fall back to the first short Title-Case line if NER finds nothing #
    def extract_name(self, text: str) -> str | None:
        if not text:
            return None

        ORG_HINTS = {
            "inc", "ltd", "llc", "corp", "university", "college",
            "institute", "school", "technologies", "solutions", "services",
            "consulting", "labs", "systems",
        }

        if self.nlp:
            doc      = self.nlp(text[:1000])
            persons  = [
                ent.text for ent in doc.ents
                if ent.label_ == "PERSON"
                and not any(w.lower() in ORG_HINTS for w in ent.text.split())
            ]
            if persons:
                # Shortest entity is most likely just "First Last" (the candidate)
                return min(persons, key=len)

        # Fallback: first line that looks like a name
        #   — 1-4 words, mostly title-case, no digits, < 50 chars
        for line in text.split("\n"):
            line = line.strip()
            if (
                line
                and 1 <= len(line.split()) <= 4
                and len(line) < 50
                and not any(ch.isdigit() for ch in line)
                and line == line.title()
            ):
                return line

        return None