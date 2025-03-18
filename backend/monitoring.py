import time
import threading
import concurrent.futures
import logging
from datetime import datetime, timedelta
from config import app
from extensions import db
from models import Stream, Log, Assignment
from notifications import send_notifications

# Thread pool for monitoring tasks
monitoring_executor = concurrent.futures.ThreadPoolExecutor(max_workers=20)

def monitor_stream(stream_url):
    while True:
        with app.app_context():
            stream = Stream.query.filter_by(room_url=stream_url).first()
            if not stream:
                logging.info("Stream %s not found. Exiting monitor.", stream_url)
                return
            logging.info("Backend object detection is disabled for stream: %s", stream_url)
        time.sleep(10)

def start_monitoring():
    with app.app_context():
        streams = Stream.query.all()
        if len(streams) > 20:
            logging.warning("Number of streams (%s) exceeds max concurrent limit (20).", len(streams))
        for stream in streams:
            monitoring_executor.submit(monitor_stream, stream.room_url)
            logging.info("Submitted monitoring task for %s", stream.room_url)

def start_notification_monitor():
    def monitor_notifications():
        # Start with a timestamp slightly in the past
        last_notified_time = datetime.utcnow() - timedelta(seconds=5)
        while True:
            try:
                with app.app_context():
                    # Monitor for all event types coming from videoplayer.js
                    logs = Log.query.filter(
                        Log.timestamp > last_notified_time,
                        Log.event_type.in_(["object_detection", "audio_detection", "chat_detection", "video_notification"])
                    ).all()
                    for log in logs:
                        # For object detection, pass detections; for other events, pass None
                        detections = log.details.get("detections", []) if log.event_type == "object_detection" else None
                        send_notifications(log, detections)
                    if logs:
                        # Update the last notified time to the latest log's timestamp
                        last_notified_time = max(log.timestamp for log in logs)
            except Exception as e:
                logging.error("Notification monitor error: %s", e)
            time.sleep(2)
    threading.Thread(target=monitor_notifications, daemon=True).start()
