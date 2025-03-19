import time
import cv2
import threading
import logging
import numpy as np
import json
import base64
import wave
import subprocess
from datetime import datetime, timedelta
import av  # PyAV: for handling HLS streams
from ultralytics import YOLO
from flask import Flask, request, jsonify
from config import app
from models import FlaggedObject, Log, ChatKeyword, DetectionLog, Stream
from extensions import db
from notifications import send_notifications
from PIL import Image
import pytesseract
from io import BytesIO
from vosk import Model as VoskModel, KaldiRecognizer
from urllib.parse import urlparse

# Global variables and locks
_yolo_model = None
_yolo_lock = threading.Lock()
_vosk_model = None
_vosk_lock = threading.Lock()
# Global dictionary to track when an alert was last sent.
# Keys: (streamer, alert_type, object_or_keyword) and value: datetime of last alert.
last_alerts = {}
ALERT_INTERVAL = timedelta(minutes=10)  # One alert per object/keyword per streamer every 10 minutes

# Global dictionary to store stream info.
# Keys: stream_url, values: (platform, streamer_name)
stream_info = {}

def update_stream_info(stream_url, platform, streamer_name):
    """
    Called by the detection trigger endpoint to update the global mapping of stream info.
    This allows the detection code to use the real platform and streamer name.
    """
    global stream_info
    stream_info[stream_url] = (platform, streamer_name)
    logging.info("Updated stream info for %s: platform=%s, streamer=%s", stream_url, platform, streamer_name)

def should_send_alert(streamer, alert_type, obj):
    """
    Return True if an alert should be sent for the given streamer, alert type, and object (or keyword),
    i.e. if no alert has been sent within ALERT_INTERVAL.
    """
    key = (streamer, alert_type, obj)
    now = datetime.utcnow()
    if key in last_alerts:
        if now - last_alerts[key] < ALERT_INTERVAL:
            return False
    last_alerts[key] = now
    return True

def load_yolov8_model():
    """Load the YOLOv8 model if not already loaded."""
    global _yolo_model
    with _yolo_lock:
        if _yolo_model is None:
            try:
                _yolo_model = YOLO("yolo11n.pt")
                logging.info("YOLO11 model loaded successfully.")
            except Exception as e:
                logging.error("Error loading YOLO model: %s", e)
                _yolo_model = None
    return _yolo_model

def load_vosk_model():
    """Load the Vosk model if not already loaded."""
    global _vosk_model
    with _vosk_lock:
        if _vosk_model is None:
            try:
                _vosk_model = VoskModel("vosk-model-small-en-us-0.15")
                logging.info("Vosk model loaded successfully.")
            except Exception as e:
                logging.error("Error loading Vosk model: %s", e)
                _vosk_model = None
    return _vosk_model

def update_flagged_objects():
    """Retrieve flagged objects and their confidence thresholds from the database."""
    with app.app_context():
        objects = FlaggedObject.query.all()
        return {obj.object_name.lower(): float(obj.confidence_threshold) for obj in objects}

def refresh_keywords():
    """Placeholder for any keyword refresh logic if needed."""
    pass

def detect_frame_yolov8(frame):
    """Run YOLO detection on the provided frame and filter detections based on flagged objects."""
    model = load_yolov8_model()
    if model is None:
        return []
    results = model(frame)
    all_detections = []
    for result in results:
        for box in result.boxes:
            bbox = box.xyxy.cpu().numpy()[0]
            confidence = box.conf.cpu().numpy()[0]
            class_id = int(box.cls.cpu().numpy()[0])
            label = model.names.get(class_id, str(class_id)).lower()
            x1, y1, x2, y2 = bbox
            detection = {
                "class": label,
                "confidence": float(confidence),
                "bbox": [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]
            }
            all_detections.append(detection)
    flagged = update_flagged_objects()
    return [det for det in all_detections if det["class"] in flagged and det["confidence"] >= flagged[det["class"]]]

def annotate_frame(frame, detections):
    """Draw bounding boxes and labels on the frame."""
    annotated_frame = frame.copy()
    for det in detections:
        x, y, w, h = det["bbox"]
        label = f'{det["class"]} ({det["confidence"]*100:.1f}%)'
        cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.putText(annotated_frame, label, (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    return annotated_frame

def async_send_notifications(log_id, platform_name, streamer_name):
    """
    In a separate thread, re-query the log entry by its ID and then send notifications.
    This function includes a simple retry mechanism.
    """
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            with app.app_context():
                log_entry = DetectionLog.query.get(log_id)
                if log_entry is None:
                    logging.error("Log entry with id %s not found.", log_id)
                    return
                send_notifications(log_entry, platform_name, streamer_name)
            logging.info("Notification sent successfully for streamer: %s on platform: %s", streamer_name, platform_name)
            return
        except Exception as e:
            logging.error("Error sending notifications (attempt %d): %s", attempt+1, e)
            time.sleep(2)
    logging.error("Failed to send notification after %d attempts", max_attempts)

def log_detection(detections, stream_url, annotated_image, platform_name, streamer_name):
    """
    Log video detections into the database and send notifications.
    Only detections that pass the throttling check trigger an alert.
    """
    filtered_detections = []
    for det in detections:
        if should_send_alert(streamer_name, "object_detection", det["class"]):
            filtered_detections.append(det)
    if not filtered_detections:
        logging.info("Skipping duplicate video alert for streamer: %s", streamer_name)
        return

    timestamp = datetime.utcnow()
    ret, buffer = cv2.imencode('.jpg', annotated_image)
    image_data = buffer.tobytes() if ret else None
    details = {"detections": filtered_detections, "timestamp": timestamp.isoformat()}
    
    with app.app_context():
        log_entry = DetectionLog(
            room_url=stream_url,
            event_type="object_detection",
            details=details,
            detection_image=image_data,
            timestamp=timestamp,
            read=False
        )
        db.session.add(log_entry)
        db.session.commit()
        db.session.refresh(log_entry)
        log_id = log_entry.id

        notification_thread = threading.Thread(target=async_send_notifications, args=(log_id, platform_name, streamer_name))
        notification_thread.start()

def extract_stream_info(stream_url):
    """
    Extract platform and streamer name from the stream URL.
    First check if the global stream_info mapping contains this stream URL;
    if not, then if the URL contains "edge-hls.doppiocdn.live", platform is Stripchat;
    otherwise, assume Chaturbate. The streamer name is taken as the last URL segment.
    """
    if stream_url in stream_info:
        return stream_info[stream_url]
    if "edge-hls.doppiocdn.live" in stream_url:
        platform = "Stripchat"
    else:
        platform = "Chaturbate"
    streamer = stream_url.split('/')[-1].split('?')[0]
    return platform, streamer

def process_stream(stream_url, cancel_event):
    """Process a live video stream for object detection using YOLO."""
    try:
        container = av.open(stream_url)
    except Exception as e:
        logging.error("Failed to open stream: %s", e)
        return

    logging.info("Processing stream: %s", stream_url)
    platform_name, streamer_name = extract_stream_info(stream_url)
    
    video_stream = next((s for s in container.streams if s.type == 'video'), None)
    if not video_stream:
        logging.error("No video stream found in: %s", stream_url)
        container.close()
        return
    
    for frame in container.decode(video=video_stream.index):
        if cancel_event.is_set():
            logging.info("Stopping video detection for stream: %s", stream_url)
            break

        img = frame.to_ndarray(format='bgr24')
        detections = detect_frame_yolov8(img)
        if detections:
            annotated = annotate_frame(img, detections)
            log_detection(detections, stream_url, annotated, platform_name, streamer_name)
        
        time.sleep(1)
    
    container.close()
    logging.info("Video detection stopped for: %s", stream_url)

def process_audio_stream(stream_url, cancel_event):
    """
    Process a live audio stream using Vosk for transcription and keyword detection.
    For each transcribed chunk, detected keywords trigger notifications only if they haven't been alerted
    for that keyword (per streamer) in the last ALERT_INTERVAL.
    """
    try:
        container = av.open(stream_url, timeout=10)
    except Exception as e:
        logging.error(f"Audio stream open failed: {str(e)}")
        return

    audio_stream = None
    for s in container.streams:
        if s.type == 'audio':
            audio_stream = s
            break
    if not audio_stream:
        logging.error("No audio track found in stream")
        container.close()
        return

    resampler = av.AudioResampler(
        format='s16',
        layout='mono',
        rate=16000
    )

    model = load_vosk_model()
    if model is None:
        logging.error("Vosk model is not loaded.")
        container.close()
        return

    recognizer = KaldiRecognizer(model, 16000)
    recognizer.SetWords(True)
    audio_buffer = []
    chunk_duration = 10  # seconds
    last_process_time = time.time()

    try:
        for frame in container.decode(audio=audio_stream.index):
            if cancel_event.is_set():
                break

            try:
                resampled_frames = resampler.resample(frame)
            except Exception as e:
                logging.error("Error resampling frame: %s", e)
                continue

            if not resampled_frames:
                continue

            for resampled_frame in resampled_frames:
                try:
                    audio_array = resampled_frame.to_ndarray()
                    audio_buffer.append(audio_array)
                except Exception as e:
                    logging.error("Error converting frame to ndarray: %s", e)
                    continue

            if time.time() - last_process_time >= chunk_duration and audio_buffer:
                try:
                    concatenated = np.concatenate(audio_buffer)
                    audio_data = (concatenated * 32767).astype(np.int16).tobytes()
                except Exception as e:
                    logging.error("Error concatenating audio buffer: %s", e)
                    audio_buffer = []
                    last_process_time = time.time()
                    continue

                try:
                    if recognizer.AcceptWaveform(audio_data):
                        result = json.loads(recognizer.Result())
                    else:
                        result = json.loads(recognizer.PartialResult())
                except Exception as e:
                    logging.error("Error in speech recognition: %s", e)
                    audio_buffer = []
                    last_process_time = time.time()
                    continue

                text = result.get("text", "").lower()
                if text:
                    logging.info("Vosk result: %s", text)
                    with app.app_context():
                        keywords = [kw.keyword.lower() for kw in ChatKeyword.query.all()]
                        detected = [kw for kw in keywords if kw in text]
                        if detected:
                            platform, streamer = extract_stream_info(stream_url)
                            new_keywords = []
                            for kw in detected:
                                if should_send_alert(streamer, "audio_detection", kw):
                                    new_keywords.append(kw)
                            if new_keywords:
                                log_entry = Log(
                                    room_url=stream_url,
                                    event_type='audio_detection',
                                    details={
                                        'keywords': new_keywords,
                                        'transcript': text,
                                        'platform': platform,
                                        'streamer_name': streamer,
                                        'timestamp': datetime.utcnow().isoformat()
                                    }
                                )
                                db.session.add(log_entry)
                                db.session.commit()
                                log_id = log_entry.id
                                notification_thread = threading.Thread(target=async_send_notifications, args=(log_id, platform, streamer))
                                notification_thread.start()
                audio_buffer = []
                last_process_time = time.time()
    except Exception as e:
        logging.error(f"Audio decoding error: {str(e)}")
    finally:
        container.close()

# Traditional main entry point for command-line based detection processing.
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python detection_advanced.py <stream_url>")
        sys.exit(1)
    
    stream_url = sys.argv[1]
    cancel_event = threading.Event()
    logging.basicConfig(level=logging.INFO)
    # Start video processing
    process_stream(stream_url, cancel_event)
    # Process audio detection
    process_audio_stream(stream_url, cancel_event)
