from flask import Blueprint, request, jsonify
from transformers import pipeline
import torch

quiz_bp = Blueprint("quiz", __name__)

MODEL_NAME = "google/flan-t5-base"

generator = pipeline(
    "text2text-generation",
    model=MODEL_NAME,
    device=0 if torch.cuda.is_available() else -1
)


@quiz_bp.route("/generate-quiz", methods=["POST"])
def generate_quiz():
    data = request.json
    content = data.get("content")

    if not content:
        return jsonify({"error": "No content provided"}), 400

    prompt = f"""
    Generate 5 multiple choice questions from the following text.
    Format:
    Question:
    A.
    B.
    C.
    D.
    Answer:

    Text:
    {content}
    """

    result = generator(prompt, max_length=512)

    return jsonify({
        "quiz": result[0]["generated_text"]
    })