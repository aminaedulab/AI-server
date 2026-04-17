from flask import Blueprint, request, jsonify
from app.services.quiz_service import generate_quiz
import traceback

quiz_bp = Blueprint("quiz", __name__)


@quiz_bp.route("/generate-quiz", methods=["POST"])
def generate_quiz_route():
    try:
        data = request.json
        content = data.get("content", "")
        pdf_url = data.get("pdfUrl", None)
        pdf_path = data.get("pdfPath", None)

        if not content and not pdf_url and not pdf_path:
            return jsonify({"error": "No content, pdfUrl, or pdfPath provided"}), 400

        questions = generate_quiz(content=content, pdf_path=pdf_path, pdf_url=pdf_url)

        if not questions:
            return jsonify({"error": "Could not generate questions from provided input"}), 422

        return jsonify({"success": True, "quiz": questions})

    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500
