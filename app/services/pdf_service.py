import re
import pdfplumber


def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text.strip()


def clean_text(text: str) -> str:
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # remove emojis
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def get_sentences(text: str) -> list:
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 40]


def summarize_by_extraction(text: str, max_sentences: int = 8) -> str:
    """Extractive summarization — picks the most informative sentences."""
    text = clean_text(text)
    sentences = get_sentences(text)

    # Score sentences by keyword density and position
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    freq = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1

    def score(sentence):
        s_words = re.findall(r'\b[a-z]{4,}\b', sentence.lower())
        return sum(freq.get(w, 0) for w in s_words) / (len(s_words) + 1)

    scored = sorted(enumerate(sentences), key=lambda x: score(x[1]), reverse=True)
    top = sorted(scored[:max_sentences], key=lambda x: x[0])  # restore original order

    return " ".join(s for _, s in top)


def generate_pdf_summary(pdf_path: str) -> str:
    text = extract_text_from_pdf(pdf_path)
    if not text:
        return "No readable text found in PDF."
    return summarize_by_extraction(text)
