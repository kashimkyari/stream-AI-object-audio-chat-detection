import logging
import os

from config import app
from extensions import db
from models import User
from routes import *
from cleanup import start_chat_cleanup_thread, start_detection_cleanup_thread
from monitoring import start_notification_monitor
from flask_cors import CORS

# Enable CORS with credentials support
CORS(app, supports_credentials=True)

# Configure logging for production-grade diagnostics
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

def create_default_users():
    """
    Create default admin and agent users if they do not exist.
    Uses environment variables for credentials if provided.
    """
    try:
        # Create default admin if none exists.
        if not User.query.filter_by(role="admin").first():
            admin = User(
                username=os.environ.get("DEFAULT_ADMIN_USERNAME", "admin"),
                password=os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin"),
                email=os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@example.com"),
                firstname="Admin",
                lastname="User",
                phonenumber="+2348135964992",
                role="admin",
            )
            db.session.add(admin)
            db.session.commit()
            logger.info("Default admin user created.")
        else:
            logger.info("Admin user already exists.")

        # Create default agent if none exists.
        if not User.query.filter_by(role="agent").first():
            agent = User(
                username=os.environ.get("DEFAULT_AGENT_USERNAME", "agent"),
                password=os.environ.get("DEFAULT_AGENT_PASSWORD", "agent"),
                email=os.environ.get("DEFAULT_AGENT_EMAIL", "agent@example.com"),
                firstname="Agent",
                lastname="User",
                phonenumber="111-111-1111",
                role="agent",
            )
            db.session.add(agent)
            db.session.commit()
            logger.info("Default agent user created.")
        else:
            logger.info("Agent user already exists.")
    except Exception as e:
        logger.error("Error creating default users: %s", e)
        db.session.rollback()

def initialize_app():
    """
    Initialize the application:
    - Create all database tables.
    - Create default users.
    """
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully.")
        except Exception as e:
            logger.error("Error creating database tables: %s", e)
        create_default_users()

def start_background_tasks():
    """
    Start background tasks for monitoring and cleanup.
    Each task is wrapped in error handling to ensure issues are logged.
    """
    try:
        start_notification_monitor()      # Monitors new detection logs and sends notifications
        logger.info("Notification monitor started.")
    except Exception as e:
        logger.error("Error starting notification monitor: %s", e)
    try:
        start_chat_cleanup_thread()         # Cleans up old chat logs periodically
        logger.info("Chat cleanup thread started.")
    except Exception as e:
        logger.error("Error starting chat cleanup thread: %s", e)
    try:
        start_detection_cleanup_thread()    # Cleans up old detection logs periodically
        logger.info("Detection cleanup thread started.")
    except Exception as e:
        logger.error("Error starting detection cleanup thread: %s", e)

if __name__ == "__main__":
    # Initialize the database and default users.
    initialize_app()
    # Start background monitoring and cleanup tasks.
    start_background_tasks()

    # Optional SSL configuration:
    # If environment variables SSL_CERT_PATH and SSL_KEY_PATH are set,
    # Flask will run with HTTPS.
    ssl_cert = "/home/ec2-user/certs/fullchain2.pem"
    ssl_key = "/home/ec2-user/certs/privkey2.pem"
    ssl_context = (ssl_cert, ssl_key) if ssl_cert and ssl_key else None
    if ssl_context:
        logger.info("Starting app with SSL context.")
    else:
        logger.info("Starting app without SSL context.")

    # Run the Flask application on all interfaces at a port defined by the PORT environment variable (default 5000).
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True, debug=False, ssl_context=ssl_context)
