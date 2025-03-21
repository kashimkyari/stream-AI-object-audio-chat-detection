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
from bs4 import BeautifulSoup

# Global variables and locks
_yolo_model = None
_yolo_lock = threading.Lock()
_vosk_model = None
_vosk_lock = threading.Lock()

# Global dictionaries for alerts and detections
last_alerts = {}
ALERT_INTERVAL = timedelta(minutes=10)
consecutive_detection_counts = {}
stream_info = {}

def update_stream_info(stream_url, platform, streamer_name):
    global stream_info
    stream_info[stream_url] = (platform, streamer_name)
    logging.info("Updated stream info for %s: platform=%s, streamer=%s", stream_url, platform, streamer_name)

def should_send_alert(streamer, alert_type, obj):
    key = (streamer, alert_type, obj)
    now = datetime.utcnow()
    if key in last_alerts and (now - last_alerts[key] < ALERT_INTERVAL):
        return False
    last_alerts[key] = now
    return True

def load_yolov8_model():
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
    with app.app_context():
        objects = FlaggedObject.query.all()
        return {obj.object_name.lower(): float(obj.confidence_threshold) for obj in objects}

def refresh_keywords():
    # Placeholder for keyword refresh logic if needed.
    pass

def detect_frame_yolov8(frame):
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
    annotated_frame = frame.copy()
    for det in detections:
        x, y, w, h = det["bbox"]
        label = f'{det["class"]} ({det["confidence"]*100:.1f}%)'
        cv2.rectangle(annotated_frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.putText(annotated_frame, label, (x, y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    return annotated_frame

def async_send_notifications(log_id, platform_name, streamer_name):
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            with app.app_context():
                log_entry = DetectionLog.query.get(log_id)
                if log_entry is None:
                    logging.error("Log entry with id %s not found.", log_id)
                    return
                send_notifications(log_entry, platform_name, streamer_name)
            logging.info("Notification sent for %s on %s", streamer_name, platform_name)
            return
        except Exception as e:
            logging.error("Notification attempt %d failed: %s", attempt+1, e)
            time.sleep(2)
    logging.error("Failed to send notification after %d attempts", max_attempts)

def log_detection(detections, stream_url, annotated_image, platform_name, streamer_name):
    global consecutive_detection_counts
    filtered_detections = []
    for det in detections:
        if should_send_alert(streamer_name, "object_detection", det["class"]):
            filtered_detections.append(det)
            key = (streamer_name, det["class"])
            count = consecutive_detection_counts.get(key, 0) + 1
            consecutive_detection_counts[key] = count
            if count >= 3:
                logging.info("Detected %s three times for %s. Sleeping...", det["class"], streamer_name)
                time.sleep(120)
                consecutive_detection_counts[key] = 0
        else:
            key = (streamer_name, det["class"])
            consecutive_detection_counts[key] = 0

    if not filtered_detections:
        logging.info("No new video alert for %s", streamer_name)
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

        notification_thread = threading.Thread(
            target=async_send_notifications, args=(log_id, platform_name, streamer_name)
        )
        notification_thread.start()

def extract_stream_info_from_db(stream_url):
    with app.app_context():
        stream_record = Stream.query.filter_by(room_url=stream_url).first()
        if stream_record:
            return stream_record.type, stream_record.streamer_username
    return None, None

def process_stream(stream_url, cancel_event):
    platform_name, streamer_name = extract_stream_info_from_db(stream_url)
    if not platform_name or not streamer_name:
        logging.error("Stream %s not found. Aborting video detection.", stream_url)
        return

    try:
        container = av.open(stream_url)
    except Exception as e:
        logging.error("Failed to open stream %s: %s", stream_url, e)
        return

    logging.info("Video detection started for %s", stream_url)
    video_stream = next((s for s in container.streams if s.type == 'video'), None)
    if not video_stream:
        logging.error("No video stream in %s", stream_url)
        container.close()
        return

    for frame in container.decode(video=video_stream.index):
        if cancel_event.is_set():
            logging.info("Video detection stopped for %s", stream_url)
            break

        img = frame.to_ndarray(format='bgr24')
        detections = detect_frame_yolov8(img)
        if detections:
            annotated = annotate_frame(img, detections)
            log_detection(detections, stream_url, annotated, platform_name, streamer_name)
        else:
            for key in list(consecutive_detection_counts.keys()):
                if key[0] == streamer_name:
                    consecutive_detection_counts[key] = 0

        time.sleep(1)
    
    container.close()
    logging.info("Video detection ended for %s", stream_url)

def process_audio_stream(stream_url, cancel_event):
    platform_name, streamer_name = extract_stream_info_from_db(stream_url)
    if not platform_name or not streamer_name:
        logging.error("Stream %s not found. Aborting audio detection.", stream_url)
        return

    try:
        container = av.open(stream_url, timeout=10)
    except Exception as e:
        logging.error("Audio stream open failed for %s: %s", stream_url, e)
        return

    audio_stream = None
    for s in container.streams:
        if s.type == 'audio':
            audio_stream = s
            break
    if not audio_stream:
        logging.error("No audio track in stream %s", stream_url)
        container.close()
        return

    resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)
    model = load_vosk_model()
    if model is None:
        logging.error("Vosk model not loaded. Aborting audio detection.")
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
                logging.error("Error resampling audio frame: %s", e)
                continue

            if not resampled_frames:
                continue

            for resampled_frame in resampled_frames:
                try:
                    audio_array = resampled_frame.to_ndarray()
                    audio_buffer.append(audio_array)
                except Exception as e:
                    logging.error("Error converting audio frame: %s", e)
                    continue

            if time.time() - last_process_time >= chunk_duration and audio_buffer:
                try:
                    concatenated = np.concatenate(audio_buffer)
                    if concatenated.dtype != np.int16:
                        audio_data = (concatenated * 32767).astype(np.int16).tobytes()
                    else:
                        audio_data = concatenated.tobytes()
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
                    logging.error("Speech recognition error: %s", e)
                    audio_buffer = []
                    last_process_time = time.time()
                    continue

                text = result.get("text", "").lower()
                if text:
                    logging.info("Audio transcription: %s", text)
                    with app.app_context():
                        keywords = [kw.keyword.lower() for kw in ChatKeyword.query.all()]
                        detected = [kw for kw in keywords if kw in text]
                        if detected:
                            new_keywords = [kw for kw in detected if should_send_alert(streamer_name, "audio_detection", kw)]
                            if new_keywords:
                                log_entry = Log(
                                    room_url=stream_url,
                                    event_type='audio_detection',
                                    details={
                                        'keywords': new_keywords,
                                        'transcript': text,
                                        'platform': platform_name,
                                        'streamer_name': streamer_name,
                                        'timestamp': datetime.utcnow().isoformat()
                                    }
                                )
                                db.session.add(log_entry)
                                db.session.commit()
                                log_id = log_entry.id
                                threading.Thread(target=async_send_notifications, args=(log_id, platform_name, streamer_name)).start()
                audio_buffer = []
                last_process_time = time.time()
    except Exception as e:
        logging.error("Audio decoding error for %s: %s", stream_url, e)
    finally:
        container.close()

# ----------------------------
# NEW: Chat Detection Functions
# ----------------------------

def parse_chat_messages(html_content, platform):
    """
    Parse the HTML content of a chat container and extract messages.
    Returns a list of dictionaries with keys 'username' and 'message'.
    Supports both Stripchat and Chaturbate formats.
    """
    messages = []
    soup = BeautifulSoup(html_content, "html.parser")
    if platform.lower() == "stripchat":
        for msg_div in soup.find_all("div", class_="message-body"):
            username_span = msg_div.find("span", class_="user-levels-username-text")
            if username_span:
                username = username_span.get_text(strip=True)
                username_span.extract()
            else:
                username = "Unknown"
            message_text = msg_div.get_text(separator=" ", strip=True)
            if message_text:
                messages.append({"username": username, "message": message_text})
    elif platform.lower() == "chaturbate":
        username_elements = soup.select('[data-testid="username"]')
        message_elements = soup.select('[data-testid="chat-message-text"]')
        for user_elem, msg_elem in zip(username_elements, message_elements):
            username = user_elem.get_text(strip=True)
            message_text = msg_elem.get_text(separator=" ", strip=True)
            messages.append({"username": username, "message": message_text})
    return messages

def detect_chat_stream(stream_url, cancel_event):
    """
    Check if the livestream is online, then construct the chat URL for the platform.
    For both Stripchat and Chaturbate, first try to parse chat messages via BeautifulSoup.
    If no messages are found, fallback to screenshot OCR.
    If flagged keywords are detected, a Telegram notification is sent.
    """
    platform, streamer_name = extract_stream_info_from_db(stream_url)
    if not platform or not streamer_name:
        logging.error("Stream %s not found. Aborting chat detection.", stream_url)
        return

    if platform.lower() == "chaturbate":
        chat_url = f"https://chaturbate.com/{streamer_name}"
    elif platform.lower() == "stripchat":
        chat_url = f"https://stripchat.com/{streamer_name}"
    else:
        logging.error("Unsupported platform: %s", platform)
        return

    try:
        from scraping import fetch_m3u8_from_page
        m3u8_url = fetch_m3u8_from_page(chat_url, timeout=30)
    except Exception as e:
        logging.error("Error checking livestream status: %s", e)
        return

    if not m3u8_url:
        logging.info("Livestream offline for %s. Skipping chat detection.", chat_url)
        return

    try:
        from seleniumwire import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(chat_url)
        time.sleep(5)
    except Exception as e:
        logging.error("Selenium initialization error: %s", e)
        return

    messages = []
    try:
        html_content = driver.page_source
        messages = parse_chat_messages(html_content, platform)
        if not messages:
            logging.info("No messages parsed via HTML. Falling back to screenshot OCR.")
            try:
                chat_container = driver.find_element("id", "ChatTabContainer")
                screenshot = chat_container.screenshot_as_png
                image = Image.open(BytesIO(screenshot))
                ocr_text = pytesseract.image_to_string(image)
                if ocr_text.strip():
                    messages = [{"username": "Unknown", "message": ocr_text.strip()}]
            except Exception as e:
                logging.error("Error during screenshot OCR fallback: %s", e)
    except Exception as e:
        logging.error("Chat message parsing error: %s", e)
    finally:
        driver.quit()

    if messages:
        with app.app_context():
            flagged_keywords = [kw.keyword.lower() for kw in ChatKeyword.query.all()]
        for msg in messages:
            text_lower = msg["message"].lower()
            detected = [kw for kw in flagged_keywords if kw in text_lower]
            if detected:
                logging.info("Flagged chat message detected from '%s': %s", msg["username"], msg["message"])
                with app.app_context():
                    log_entry = Log(
                        room_url=chat_url,
                        event_type="chat_detection",
                        details={
                            "keywords": detected,
                            "username": msg["username"],
                            "ocr_text": msg["message"],
                            "streamer_name": streamer_name,
                            "platform": platform,
                        },
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(log_entry)
                    db.session.commit()
                    send_notifications(log_entry)
    else:
        logging.info("No chat messages detected on %s", chat_url)

def chat_detection_loop(stream_url, cancel_event, interval=60):
    while not cancel_event.is_set():
        detect_chat_stream(stream_url, cancel_event)
        time.sleep(interval)

# ----------------------------
# Main Entry Point
# ----------------------------
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python detection.py <stream_url>")
        sys.exit(1)
    
    stream_url = sys.argv[1]
    cancel_event = threading.Event()
    logging.basicConfig(level=logging.INFO)
    # Uncomment to test chat detection loop alone:
    # chat_detection_loop(stream_url, cancel_event, interval=30)
    process_stream(stream_url, cancel_event)
