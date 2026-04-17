"""
PDF Service
Summarization pipeline:
  1. Extract text from PDF using pdfplumber
  2. Try abstractive summarization via DistilBART (ML)
  3. Fall back to extractive summarization (spaCy TF-IDF sentence scoring)
"""

import re
import logging
import pdfplumber
import spacy

from app.services.ml_service import summarize_text_t5

logger = logging.getLogger(__name__)
nlp = spacy.load("en_core_web_sm")


def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text.strip()


def preprocess_text(text: str) -> str:
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    cutoff = re.search(
        r'(BEST WAY TO CREATE|Option \d|If You Want|WHY THIS|Tell me|reportlab)',
        text, re.IGNORECASE
    )
    if cutoff:
        text = text[:cutoff.start()]
    return text.strip()


def extractive_summary(text: str, num_sentences: int = 8) -> str:
    """
    Extractive summarization: score sentences by noun/keyword density (TF-IDF style).
    Used as fallback when abstractive model is unavailable.
    """
    doc = nlp(text)

    word_freq: dict = {}
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and not token.is_stop and len(token.text) > 3:
            w = token.lemma_.lower()
            word_freq[w] = word_freq.get(w, 0) + 1

    scored = []
    for sent in doc.sents:
        s = sent.text.strip()
        if len(s) < 30 or len(s) > 300:
            continue
        if re.match(r'^\d+\.', s):
            continue
        score = sum(word_freq.get(t.lemma_.lower(), 0) for t in sent if not t.is_stop)
        scored.append((score, s))

    scored.sort(reverse=True)
    top = [s for _, s in scored[:num_sentences]]

    # Restore reading order
    top.sort(key=lambda s: text.find(s))
    return " ".join(top)


def generate_pdf_summary(pdf_path: str) -> str:
    raw = extract_text_from_pdf(pdf_path)
    if not raw:
        return "No readable text found in PDF."

    text = preprocess_text(raw)

    # ── Step 1: Try abstractive summarization (ML) ──
    abstractive = summarize_text_t5(text, max_length=250)
    if abstractive and len(abstractive) > 80:
        logger.info("Using abstractive (DistilBART) summary")
        return abstractive

    # ── Step 2: Fall back to extractive ──
    logger.info("Using extractive (spaCy) summary fallback")
    return extractive_summary(text)
