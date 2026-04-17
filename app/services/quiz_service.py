import os
import re
import random
import requests
import pdfplumber
import io
import spacy
import logging

from app.services.ml_service import (
    generate_questions_t5,
    semantic_distractors,
    score_difficulty,
)

logger = logging.getLogger(__name__)
nlp = spacy.load("en_core_web_sm")

STOP_PATTERNS = re.compile(
    r'(BEST WAY TO CREATE|Option \d|If You Want|WHY THIS|Tell me|'
    r'PDF|Paste|Download|Click|Save As|reportlab|Python code)',
    re.IGNORECASE
)

VAGUE_PRONOUNS = {"it", "this", "that", "they", "he", "she", "which", "these", "those"}


def extract_text_from_path(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text.strip()


def extract_text_from_url(pdf_url):
    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()
    text = ""
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text.strip()


def preprocess_text(text):
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    cutoff = STOP_PATTERNS.search(text)
    if cutoff:
        text = text[:cutoff.start()]
    return text.strip()


def get_clean_sentences(text):
    text = preprocess_text(text)
    doc = nlp(text)
    clean = []
    last_subject = None

    for sent in doc.sents:
        s = sent.text.strip()
        if len(s) < 30 or len(s) > 220:
            continue
        if re.match(r'^\d+\.', s):
            continue
        if len(s.split()) < 6:
            continue
        if STOP_PATTERNS.search(s):
            continue

        subj = None
        for token in sent:
            if token.dep_ in ("nsubj", "nsubjpass") and token.pos_ in ("NOUN", "PROPN"):
                subj = token.text
                break

        if subj and subj.lower() not in VAGUE_PRONOUNS:
            last_subject = subj

        if last_subject:
            s = re.sub(r'^(It|This|That|They|These)\b', last_subject, s)

        clean.append(s)

    return clean


def extract_keywords(doc):
    freq = {}
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and not token.is_stop and len(token.text) > 3:
            w = token.lemma_.lower()
            freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq, key=freq.get, reverse=True)
    return [w.capitalize() for w in sorted_words[:80]]


def build_definition_question(sent, keywords):
    text = sent.text.strip()
    pattern = r'^([A-Z][^,\.]{3,40}?)\s+(?:is|are|refers to|means|defined as)\s+(.{15,120})$'
    match = re.match(pattern, text, re.IGNORECASE)
    if not match:
        return None

    subject = match.group(1).strip()
    definition = match.group(2).strip().rstrip('.')

    if subject.lower() in VAGUE_PRONOUNS or len(subject.split()) > 6:
        return None

    distractors = semantic_distractors(definition, keywords, n=3)
    options = distractors + [definition]
    random.shuffle(options)
    correct_label = next(chr(65 + i) for i, o in enumerate(options) if o == definition)

    return {
        "question": "What is " + subject + "?",
        "options": [{"label": chr(65 + i), "text": o} for i, o in enumerate(options)],
        "correctAnswer": correct_label,
        "correctAnswerText": definition,
        "difficulty": score_difficulty(text),
        "source": "rule",
    }


def build_fill_blank_question(sent, keywords):
    text = sent.text.strip()
    if len(text) > 160:
        return None

    candidates = [
        token for token in sent
        if token.pos_ in ("NOUN", "PROPN")
        and not token.is_stop
        and len(token.text) > 3
        and token.i != sent.start
        and token.i != sent.end - 1
        and not token.text.isdigit()
        and token.text.lower() not in VAGUE_PRONOUNS
    ]

    if not candidates:
        return None

    target = random.choice(candidates)
    blanked = (
        text[:target.idx - sent.start_char]
        + "______"
        + text[target.idx - sent.start_char + len(target.text):]
    ).strip()

    distractors = semantic_distractors(target.text, keywords, n=3)
    options = distractors + [target.text]
    random.shuffle(options)
    correct_label = next(chr(65 + i) for i, o in enumerate(options) if o == target.text)

    return {
        "question": "Fill in the blank: " + blanked,
        "options": [{"label": chr(65 + i), "text": o} for i, o in enumerate(options)],
        "correctAnswer": correct_label,
        "correctAnswerText": target.text,
        "difficulty": score_difficulty(text),
        "source": "rule",
    }


def generate_questions_from_text(text, num_questions=10):
    text = preprocess_text(text)
    doc = nlp(text)
    keywords = extract_keywords(doc)
    sentences = get_clean_sentences(text)

    questions = []
    seen = set()

    # Step 1: Try T5 ML generation
    try:
        ml_questions = generate_questions_t5(sentences, keywords, num_questions=num_questions)
        for q in ml_questions:
            if q["question"] not in seen:
                seen.add(q["question"])
                questions.append(q)
        logger.info("T5 generated %d questions", len(questions))
    except Exception as e:
        logger.warning("T5 pipeline failed: %s", e)

    # Step 2: Fill remaining with spaCy rules
    if len(questions) < num_questions:
        clean_doc = nlp(" ".join(sentences))
        sents = list(clean_doc.sents)
        random.shuffle(sents)

        for sent in sents:
            if len(questions) >= num_questions:
                break
            q = build_definition_question(sent, keywords) or build_fill_blank_question(sent, keywords)
            if q and q["question"] not in seen:
                seen.add(q["question"])
                questions.append(q)

        logger.info("After spaCy fallback: %d questions total", len(questions))

    return questions


def generate_quiz(content="", pdf_path=None, pdf_url=None, num_questions=10):
    text = ""

    if pdf_path and os.path.exists(pdf_path):
        try:
            text = extract_text_from_path(pdf_path)
        except Exception as e:
            logger.warning("PDF path extraction failed: %s", e)

    if not text and pdf_url:
        try:
            text = extract_text_from_url(pdf_url)
        except Exception as e:
            logger.warning("PDF URL extraction failed: %s", e)

    if not text and content:
        text = content

    if not text:
        return []

    return generate_questions_from_text(text, num_questions=num_questions)
