# from flask import Blueprint, request, jsonify
# from app.services.pdf_service import generate_pdf_summary
# import os
# import traceback

# pdf_bp = Blueprint("pdf", __name__)

# @pdf_bp.route("/pdf-summary", methods=["POST"])
# def pdf_summary():
#     try:
#         data = request.json
#         pdf_path = data.get("pdfPath")

#         if not pdf_path:
#             return jsonify({"success": False, "message": "No PDF path provided"}), 400

#         pdf_path = os.path.normpath(pdf_path)

#         if not os.path.exists(pdf_path):
#             return jsonify({"success": False, "message": "File not found"}), 400

#         summary = generate_pdf_summary(pdf_path)

#         return jsonify({
#             "success": True,
#             "summary": summary
#         })

#     except Exception:
#         traceback.print_exc()
#         return jsonify({"success": False, "message": "Internal error"}), 500
from flask import Blueprint, request, jsonify
from app.services.pdf_service import generate_pdf_summary
import os
import traceback

pdf_bp = Blueprint("pdf", __name__)

@pdf_bp.route("/pdf-summary", methods=["POST"])
def pdf_summary():
    try:
        data = request.json
        pdf_path = data.get("pdfPath")

        if not pdf_path:
            return jsonify({"success": False, "message": "No PDF path provided"}), 400

        pdf_path = os.path.normpath(pdf_path)

        if not os.path.exists(pdf_path):
            return jsonify({"success": False, "message": "File not found"}), 404

        summary = generate_pdf_summary(pdf_path)

        return jsonify({"success": True, "summary": summary})

    except Exception:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Internal server error"}), 500
