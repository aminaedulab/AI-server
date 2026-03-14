import pdfplumber
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

MODEL_NAME = "sshleifer/distilbart-cnn-12-6"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)


def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + " "
    return text.strip()


def chunk_text(text, max_tokens=900):
    tokens = tokenizer.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk = tokens[i:i + max_tokens]
        chunks.append(tokenizer.decode(chunk, skip_special_tokens=True))
    return chunks


def summarize_text(text, max_length=180, min_length=60):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=1024).to(device)
    summary_ids = model.generate(
        inputs["input_ids"],
        max_length=max_length,
        min_length=min_length,
        num_beams=4,
        early_stopping=True
    )
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)


def generate_pdf_summary(pdf_path):
    text = extract_text_from_pdf(pdf_path)

    if not text:
        return "No readable text found in PDF."

    chunks = chunk_text(text)
    chunk_summaries = [summarize_text(chunk) for chunk in chunks]
    combined = " ".join(chunk_summaries)

    final_summary = summarize_text(combined, max_length=250, min_length=100)
    return final_summary
