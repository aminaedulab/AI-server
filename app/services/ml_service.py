"""
ML/DL Service — MSc Project
Uses HuggingFace Transformers for:
  1. T5-based question generation from text
  2. Sentence-transformers for semantic distractor selection
  3. Difficulty scoring using linguistic features + sentence complexity
Falls back to spaCy rule-based generation if models unavailable.
"""

import re
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ── Lazy-load heavy models so startup is fast ──────────────────────────────
_t5_pipeline = None
_embedder    = None
_spacy_nlp   = None


def _get_spacy():
    global _spacy_nlp
    if _spacy_nlp is None:
        import spacy
        _spacy_nlp = spacy.load("en_core_web_sm")
    return _spacy_nlp


def _get_t5():
    """Load T5 question-generation pipeline (valhalla/t5-base-qg-hl)."""
    global _t5_pipeline
    if _t5_pipeline is None:
        try:
            from transformers import pipeline
            _t5_pipeline = pipeline(
                "text2text-generation",
                model="valhalla/t5-base-qg-hl",
                max_new_tokens=64,
            )
            logger.info("T5 QG model loaded")
        except Exception as e:
            logger.warning(f"T5 model unavailable: {e}")
            _t5_pipeline = False   # mark as failed so we don't retry
    return _t5_pipeline if _t5_pipeline else None


def _get_embedder():
    """Load sentence-transformers for semantic similarity."""
    global _embedder
    if _embedder is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedder = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Sentence embedder loaded")
        except Exception as e:
            logger.warning(f"Sentence embedder unavailable: {e}")
            _embedder = False
    return _embedder if _embedder else None


# ── Difficulty scoring ──────────────────────────────────────────────────────

def score_difficulty(sentence: str) -> str:
    """
    Classify a sentence as easy / medium / hard based on:
    - Average word length (lexical complexity)
    - Sentence length (syntactic complexity)
    - Subordinate clause count (dependency depth)
    Returns: 'easy' | 'medium' | 'hard'
    """
    nlp = _get_spacy()
    doc = nlp(sentence)
    tokens = [t for t in doc if not t.is_punct and not t.is_space]

    if not tokens:
        return "medium"

    avg_word_len = sum(len(t.text) for t in tokens) / len(tokens)
    sent_len     = len(tokens)
    sub_clauses  = sum(1 for t in doc if t.dep_ in ("advcl", "relcl", "ccomp", "xcomp"))

    score = 0
    if avg_word_len > 6:   score += 1
    if avg_word_len > 8:   score += 1
    if sent_len > 20:      score += 1
    if sent_len > 30:      score += 1
    if sub_clauses >= 2:   score += 1

    if score <= 1:   return "easy"
    if score <= 3:   return "medium"
    return "hard"


# ── Semantic distractor generation ─────────────────────────────────────────

def semantic_distractors(correct: str, candidates: list[str], n: int = 3) -> list[str]:
    """
    Use sentence-transformers cosine similarity to pick distractors that are
    semantically related to the correct answer but not identical.
    Falls back to keyword-based selection if embedder unavailable.
    """
    embedder = _get_embedder()
    if not embedder or len(candidates) < n:
        # Fallback: just pick random candidates
        pool = [c for c in candidates if c.lower() != correct.lower()]
        random.shuffle(pool)
        result = pool[:n]
        fallbacks = ["None of the above", "All of the above", "Not applicable"]
        i = 0
        while len(result) < n:
            result.append(fallbacks[i % len(fallbacks)])
            i += 1
        return result

    import numpy as np

    pool = [c for c in candidates if c.lower() != correct.lower()]
    if not pool:
        return ["None of the above", "All of the above", "Not applicable"][:n]

    try:
        correct_emb = embedder.encode([correct])[0]
        pool_embs   = embedder.encode(pool)

        # Cosine similarity
        def cosine(a, b):
            return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

        scored = [(cosine(correct_emb, e), p) for e, p in zip(pool_embs, pool)]
        # Sort by similarity descending — pick most related but not identical
        scored.sort(reverse=True)

        # Filter out near-duplicates (similarity > 0.95)
        distractors = []
        for sim, phrase in scored:
            if sim < 0.95 and phrase not in distractors:
                distractors.append(phrase)
            if len(distractors) == n:
                break

        fallbacks = ["None of the above", "All of the above", "Not applicable"]
        i = 0
        while len(distractors) < n:
            distractors.append(fallbacks[i % len(fallbacks)])
            i += 1

        return distractors

    except Exception as e:
        logger.warning(f"Semantic distractor failed: {e}")
        random.shuffle(pool)
        return pool[:n]


# ── T5 Question Generation ──────────────────────────────────────────────────

def _highlight_answer(sentence: str, answer: str) -> str:
    """Wrap answer span with <hl> tags for T5 QG model."""
    return sentence.replace(answer, f"<hl> {answer} <hl>", 1)


def generate_questions_t5(sentences: list[str], keywords: list[str], num_questions: int = 10) -> list[dict]:
    """
    Use T5 to generate questions from highlighted sentences.
    Each sentence gets a keyword highlighted as the answer span.
    """
    t5 = _get_t5()
    if not t5:
        return []

    questions = []
    seen = set()
    nlp = _get_spacy()

    for sent in sentences:
        if len(questions) >= num_questions:
            break

        # Find a good answer span in this sentence (prefer named entities, then nouns)
        doc = nlp(sent)
        answer_span = None

        # Try named entities first
        for ent in doc.ents:
            if len(ent.text) > 3 and ent.text.lower() not in {"javascript", "js"}:
                answer_span = ent.text
                break

        # Fall back to prominent noun
        if not answer_span:
            for token in doc:
                if (token.pos_ in ("NOUN", "PROPN")
                        and not token.is_stop
                        and len(token.text) > 4
                        and token.text.lower() not in {"javascript", "js"}):
                    answer_span = token.text
                    break

        if not answer_span or answer_span not in sent:
            continue

        try:
            highlighted = _highlight_answer(sent, answer_span)
            input_text  = f"generate question: {highlighted}"
            output      = t5(input_text, max_new_tokens=64)[0]["generated_text"].strip()

            if not output or output in seen or len(output) < 10:
                continue

            # Build distractors from keywords
            distractors = semantic_distractors(answer_span, keywords, n=3)
            options = distractors + [answer_span]
            random.shuffle(options)
            correct_label = next(chr(65 + i) for i, o in enumerate(options) if o == answer_span)

            difficulty = score_difficulty(sent)

            questions.append({
                "question":         output,
                "options":          [{"label": chr(65 + i), "text": o} for i, o in enumerate(options)],
                "correctAnswer":    correct_label,
                "correctAnswerText": answer_span,
                "difficulty":       difficulty,
                "source":           "t5",
            })
            seen.add(output)

        except Exception as e:
            logger.warning(f"T5 generation failed for sentence: {e}")
            continue

    return questions


# ── Abstractive summarization ───────────────────────────────────────────────

def summarize_text_t5(text: str, max_length: int = 300) -> Optional[str]:
    """
    Use facebook/bart-large-cnn for abstractive summarization.
    Returns None if model unavailable.
    """
    try:
        from transformers import pipeline as hf_pipeline
        summarizer = hf_pipeline(
            "summarization",
            model="sshleifer/distilbart-cnn-12-6",
            max_length=max_length,
            min_length=80,
            do_sample=False,
        )
        # Truncate input to ~1024 tokens worth of text
        truncated = text[:3000]
        result = summarizer(truncated)[0]["summary_text"]
        return result.strip()
    except Exception as e:
        logger.warning(f"Abstractive summarization failed: {e}")
        return None


# ── Knowledge State Estimation (BKT-inspired) ──────────────────────────────

def estimate_knowledge_state(attempt_history: list[dict]) -> dict:
    """
    Bayesian Knowledge Tracing (simplified) to estimate student mastery.

    attempt_history: list of { "accuracy": float (0-100), "topic": str }
    Returns: { "mastery": float 0-1, "trend": "improving"|"stable"|"declining" }

    BKT parameters (standard defaults):
      p_init  = 0.3   (prior probability of knowing)
      p_learn = 0.2   (probability of learning after each attempt)
      p_slip  = 0.1   (probability of wrong answer despite knowing)
      p_guess = 0.2   (probability of correct answer without knowing)
    """
    if not attempt_history:
        return {"mastery": 0.3, "trend": "stable"}

    P_INIT  = 0.3
    P_LEARN = 0.2
    P_SLIP  = 0.1
    P_GUESS = 0.2

    p_know = P_INIT

    for attempt in attempt_history:
        correct = attempt.get("accuracy", 0) / 100.0  # normalize to 0-1

        # BKT update: P(know | correct)
        if correct >= 0.5:
            p_know = (p_know * (1 - P_SLIP)) / (
                p_know * (1 - P_SLIP) + (1 - p_know) * P_GUESS
            )
        else:
            p_know = (p_know * P_SLIP) / (
                p_know * P_SLIP + (1 - p_know) * (1 - P_GUESS)
            )

        # Learning update
        p_know = p_know + (1 - p_know) * P_LEARN

    # Trend: compare last 2 attempts
    trend = "stable"
    if len(attempt_history) >= 2:
        last  = attempt_history[-1].get("accuracy", 0)
        prev  = attempt_history[-2].get("accuracy", 0)
        if last - prev > 10:
            trend = "improving"
        elif prev - last > 10:
            trend = "declining"

    return {
        "mastery": round(p_know, 3),
        "trend":   trend,
    }
