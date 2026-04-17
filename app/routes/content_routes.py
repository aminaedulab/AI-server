from flask import Blueprint, request, jsonify
from app.services.content_service import fetch_topic_content, fetch_rich_content, get_available_topics
from app.services.quiz_service import generate_questions_from_text
from app.services.evaluation_service import evaluate_quiz
from app.services.ml_service import summarize_text_t5, estimate_knowledge_state
from app.services.explain_service import explain_concept, get_code_examples
import traceback

content_bp = Blueprint("content", __name__)


@content_bp.route("/topics", methods=["GET"])
def list_topics():
    return jsonify({"topics": get_available_topics()})


@content_bp.route("/topic-content", methods=["POST"])
def topic_content():
    try:
        topic = request.json.get("topic", "")
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        text = fetch_topic_content(topic)
        return jsonify({"success": True, "topic": topic, "content": text})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Failed to fetch content"}), 500


@content_bp.route("/topic-summary", methods=["POST"])
def topic_summary():
    """
    Returns both a short AI summary AND the full structured rich content.
    The summary is stored in the DB; richContent is used for display.
    """
    try:
        topic = request.json.get("topic", "")
        if not topic:
            return jsonify({"error": "topic is required"}), 400

        raw_text = fetch_topic_content(topic)

        # Short summary for DB storage (used as lesson description)
        summary = summarize_text_t5(raw_text, max_length=300)
        if not summary:
            sentences = [s.strip() for s in raw_text.split(". ") if len(s.strip()) > 40]
            summary = ". ".join(sentences[:6]) + "."

        # Full structured content for lesson display
        try:
            rich = fetch_rich_content(topic)
        except Exception:
            rich = None

        return jsonify({
            "success": True,
            "topic": topic,
            "summary": summary,
            "rawContent": raw_text,
            "richContent": rich,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Failed to generate summary"}), 500


@content_bp.route("/topic-rich", methods=["POST"])
def topic_rich():
    """
    Returns full structured MDN content for a topic.
    Used by the lesson page to show rich sectioned content.
    Body: { topic: str }
    """
    try:
        topic = (request.json or {}).get("topic", "")
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        rich = fetch_rich_content(topic)
        return jsonify({"success": True, **rich})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Failed to fetch rich content"}), 500


@content_bp.route("/topic-quiz", methods=["POST"])
def topic_quiz():
    try:
        data = request.json
        topic = data.get("topic", "")
        num_questions = int(data.get("numQuestions", 10))
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        text = fetch_topic_content(topic)
        questions = generate_questions_from_text(text, num_questions=num_questions)
        if not questions:
            return jsonify({"error": "Could not generate questions for this topic"}), 422
        return jsonify({"success": True, "topic": topic, "quiz": questions})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500


@content_bp.route("/evaluate-quiz", methods=["POST"])
def evaluate_quiz_route():
    try:
        data = request.json
        topic = data.get("topic", "")
        answers = data.get("answers", [])
        attempt_history = data.get("attempt_history", [])
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        if not answers:
            return jsonify({"error": "answers array is required"}), 400
        result = evaluate_quiz(topic, answers)
        if attempt_history:
            result["knowledgeState"] = estimate_knowledge_state(attempt_history)
        return jsonify({"success": True, **result})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Evaluation failed"}), 500


@content_bp.route("/explain-concept", methods=["POST"])
def explain_concept_route():
    try:
        data = request.json or {}
        topic = data.get("topic", "")
        question = data.get("question", "")
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        result = explain_concept(topic, question)
        return jsonify({"success": True, **result})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Explanation failed"}), 500


@content_bp.route("/code-examples", methods=["POST"])
def code_examples_route():
    try:
        topic = (request.json or {}).get("topic", "")
        if not topic:
            return jsonify({"error": "topic is required"}), 400
        examples = get_code_examples(topic)
        return jsonify({"success": True, "topic": topic, "examples": examples})
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Failed to fetch examples"}), 500
