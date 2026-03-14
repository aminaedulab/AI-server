from flask import Flask
from flask_cors import CORS
from app.routes.pdf_routes import pdf_bp
from app.routes.quiz_routes import quiz_bp

def create_app():
    app = Flask(__name__)
    CORS(app)

    app.register_blueprint(pdf_bp)
    # app.register_blueprint(quiz_bp)
    app.register_blueprint(quiz_bp, url_prefix="/v1")
    return app
