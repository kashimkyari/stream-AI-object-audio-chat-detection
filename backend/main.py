from config import app
from extensions import db
from models import User
from routes import *
from cleanup import start_chat_cleanup_thread, start_detection_cleanup_thread
from monitoring import start_notification_monitor
import logging
from flask_cors import CORS
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "https://stream-ai-object-audio-chat-detection.vercel.app/"}})


with app.app_context():
    # Create all database tables if they do not exist.
    db.create_all()

    # Create default admin if none exists.
    if not User.query.filter_by(role="admin").first():
        admin = User(
            username="admin",
            password="admin",
            email="admin@example.com",
            firstname="Admin",
            lastname="User",
            phonenumber="+2348135964992",
            role="admin",
        )
        db.session.add(admin)
        db.session.commit()

    # Create default agent if none exists.
    if not User.query.filter_by(role="agent").first():
        agent = User(
            username="agent",
            password="agent",
            email="agent@example.com",
            firstname="Agent",
            lastname="User",
            phonenumber="111-111-1111",
            role="agent",
        )
        db.session.add(agent)
        db.session.commit()

# Start background tasks.
start_notification_monitor()      # Monitors new detection logs and sends notifications
start_chat_cleanup_thread()         # Cleans up old chat logs periodically
start_detection_cleanup_thread()    # Cleans up old detection logs periodically

if __name__ == "__main__":
    # Run the Flask application on all interfaces at port 5000.
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
