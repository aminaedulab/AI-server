import os
import re
import random
import requests
import pdfplumber
import io


def extract_text_from_path(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text.strip()


def extract_text_from_url(pdf_url: str) -> str:
    response = requests.get(pdf_url, timeout=30)
    response.raise_for_status()
    text = ""
    with pdfplumber.open(io.BytesIO(response.content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text.strip()


def preprocess_text(text: str) -> str:
    # Remove emojis and non-ASCII symbols
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    # Flatten newlines
    text = re.sub(r'\n+', ' ', text)
    # Remove excessive whitespace
    text = re.sub(r'\s{2,}', ' ', text)
    # Cut off promotional/meta content after common markers
    cutoff = re.search(
        r'(BEST WAY TO CREATE|Option 1|Option 2|If You Want|WHY THIS CONTENT|Tell me what)',
        text, re.IGNORECASE
    )
    if cutoff:
        text = text[:cutoff.start()]
    return text.strip()


def resolve_pronouns(sentences: list) -> list:
    """Replace leading 'It/This/That' with the last identified subject."""
    resolved = []
    last_subject = None

    for s in sentences:
        # Try to find a subject from definition-style sentences
        match = re.match(r'^([A-Z][A-Za-z\s]{3,30}?)\s+(?:is|are)\s+', s)
        if match:
            candidate = match.group(1).strip()
            if candidate.lower() not in ("it", "this", "that", "he", "she", "they"):
                last_subject = candidate

        # Replace leading pronoun with last known subject
        if last_subject:
            s = re.sub(r'^(It|This|That|They)\b', last_subject, s)

        resolved.append(s)
    return resolved


def get_clean_sentences(text: str) -> list:
    text = preprocess_text(text)
    raw = re.split(r'(?<=[.!?])\s+', text)
    clean = []
    for s in raw:
        s = s.strip()
        if len(s) < 35 or len(s) > 180:
            continue
        if re.match(r'^\d+\.', s):          # starts with "1."
            continue
        if re.search(r'[:()]', s):           # headings or parenthetical noise
            continue
        if s.count(' ') < 5:                 # too few words
            continue
        if re.search(r'\b(PDF|Paste|Download|Click|Open|Save|Tell|Want)\b', s, re.IGNORECASE):
            continue
        clean.append(s)

    return resolve_pronouns(clean)


def extract_keywords(text: str) -> list:
    words = re.findall(r'\b[A-Za-z][a-z]{4,}\b', text)
    freq = {}
    for w in words:
        freq[w.lower()] = freq.get(w.lower(), 0) + 1
    sorted_words = sorted(freq, key=freq.get, reverse=True)
    return [w.capitalize() for w in sorted_words[:60]]


def make_distractors(correct: str, keywords: list, n: int = 3) -> list:
    distractors = []
    for kw in keywords:
        if kw.lower() not in correct.lower() and kw not in distractors:
            distractors.append(kw)
        if len(distractors) == n:
            break
    fallbacks = ["None of the above", "All of the above", "Not applicable"]
    i = 0
    while len(distractors) < n:
        distractors.append(fallbacks[i % len(fallbacks)])
        i += 1
    return distractors


def build_definition_question(sentence: str, keywords: list) -> dict | None:
    match = re.match(
        r'^([A-Z][^,\.]{3,40}?)\s+(?:is|are|refers to|means|defined as)\s+(.{15,120})$',
        sentence, re.IGNORECASE
    )
    if not match:
        return None

    subject = match.group(1).strip()
    definition = match.group(2).strip().rstrip('.')

    if subject.lower() in ("it", "this", "that", "he", "she", "they", "which"):
        return None
    if len(subject.split()) > 6:
        return None

    distractors = make_distractors(definition, keywords)
    options = distractors + [definition]
    random.shuffle(options)
    correct_label = next(chr(65 + i) for i, o in enumerate(options) if o == definition)

    return {
        "question": f"What is {subject}?",
        "options": [{"label": chr(65 + i), "text": o} for i, o in enumerate(options)],
        "correctAnswer": correct_label,
        "correctAnswerText": definition
    }


def build_fill_blank_question(sentence: str, keywords: list) -> dict | None:
    if len(sentence) > 160:
        return None

    words = sentence.split()
    candidates = [
        (i, w) for i, w in enumerate(words)
        if len(re.sub(r'\W', '', w)) > 4
        and i not in (0, len(words) - 1)
        and not re.sub(r'\W', '', w).isdigit()
        and re.sub(r'\W', '', w).lower() not in (
            "which", "their", "there", "these", "those", "about", "would", "could", "should"
        )
    ]
    if not candidates:
        return None

    idx, target = random.choice(candidates)
    clean_target = re.sub(r'\W', '', target)
    blanked = words[:idx] + ["______"] + words[idx + 1:]
    question_text = " ".join(blanked)

    distractors = make_distractors(clean_target, keywords)
    options = distractors + [clean_target]
    random.shuffle(options)
    correct_label = next(chr(65 + i) for i, o in enumerate(options) if o == clean_target)

    return {
        "question": f"Fill in the blank: {question_text}",
        "options": [{"label": chr(65 + i), "text": o} for i, o in enumerate(options)],
        "correctAnswer": correct_label,
        "correctAnswerText": clean_target
    }


def generate_questions_from_text(text: str, num_questions: int = 10) -> list:
    sentences = get_clean_sentences(text)
    keywords = extract_keywords(text)
    questions = []
    seen = set()

    random.shuffle(sentences)

    for sentence in sentences:
        if len(questions) >= num_questions:
            break
        q = build_definition_question(sentence, keywords) or build_fill_blank_question(sentence, keywords)
        if q and q["question"] not in seen:
            seen.add(q["question"])
            questions.append(q)

    return questions


def generate_quiz(content: str = "", pdf_path: str = None, pdf_url: str = None) -> list:
    text = ""

    if pdf_path and os.path.exists(pdf_path):
        try:
            text = extract_text_from_path(pdf_path)
            print(f"Extracted {len(text)} chars from PDF path")
        except Exception as e:
            print(f"PDF path extraction failed: {e}")

    if not text and pdf_url:
        try:
            text = extract_text_from_url(pdf_url)
        except Exception as e:
            print(f"PDF url extraction failed: {e}")

    if not text and content:
        text = content

    if not text:
        return []

    return generate_questions_from_text(text)
