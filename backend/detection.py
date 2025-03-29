import time
import cv2
import threading
import logging
import numpy as np
import json
import base64
import subprocess
from datetime import datetime, timedelta
import av  # PyAV for handling HLS streams
from ultralytics import YOLO
from flask import current_app
import requests
import whisper
from whisper import load_model
from PIL import Image
import pytesseract
from io import BytesIO
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from scipy import signal
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # Added for sentiment analysis

from config import app
from models import FlaggedObject, Log, ChatKeyword, DetectionLog, Stream, ChaturbateStream, StripchatStream, TelegramRecipient
from extensions import db
from notifications import send_notifications, send_text_message

# Global variables and locks
_yolo_model = None
_yolo_lock = threading.Lock()

# Global dictionaries to store stream info and last alerted objects to avoid duplicate alerts.
stream_info = {}
last_video_alerted_objects = {}  # Key: stream_url, Value: set of detected object classes

# Global for audio alert deduplication with cooldown period.
last_audio_alerted_transcript = {}  # Key: stream_url, Value: (transcript, timestamp)
ALERT_COOLDOWN_SECONDS = 60  # Cooldown period in seconds for audio alerts

# New global for per-stream rate limiting of audio alerts.
audio_alert_timestamps = {}  # Key: stream_url, Value: list of datetime objects for recent alerts

def extract_stream_info_from_db(stream_url):
    with app.app_context():
        chaturbate_stream = ChaturbateStream.query.filter_by(chaturbate_m3u8_url=stream_url).first()
        if chaturbate_stream:
            return chaturbate_stream.type, chaturbate_stream.streamer_username
        stripchat_stream = StripchatStream.query.filter_by(stripchat_m3u8_url=stream_url).first()
        if stripchat_stream:
            return stripchat_stream.type, stripchat_stream.streamer_username
        stream_record = Stream.query.filter_by(room_url=stream_url).first()
        if stream_record:
            return stream_record.type, stream_record.streamer_username
    return None, None

def update_stream_info(stream_url, platform, streamer_name):
    global stream_info
    stream_info[stream_url] = (platform, streamer_name)
    logging.info("Updated stream info for %s: platform=%s, streamer=%s", stream_url, platform, streamer_name)

def load_yolov8_model():
    global _yolo_model
    with _yolo_lock:
        if _yolo_model is None:
            try:
                _yolo_model = YOLO("yolov9c.pt", verbose=False)
                _yolo_model.verbose = False
                logging.info("YOLO11 model loaded successfully.")
            except Exception as e:
                logging.error("Error loading YOLO model: %s", e)
                _yolo_model = None
    return _yolo_model

def update_flagged_objects():
    with app.app_context():
        objects = FlaggedObject.query.all()
        return {obj.object_name.lower(): float(obj.confidence_threshold) for obj in objects}

def refresh_keywords():
    """
    Retrieve and return a list of lowercase chat keywords from the database for audio detection.
    """
    with app.app_context():
        keywords = [kw.keyword.lower() for kw in ChatKeyword.query.all()]
    logging.info("Audio keywords retrieved: %s", keywords)
    return keywords

def add_stream_to_db(stream_url, platform_type, streamer_username):
    with app.app_context():
        existing_stream = Stream.query.filter_by(room_url=stream_url).first()
        if existing_stream:
            existing_stream.type = platform_type
            existing_stream.streamer_username = streamer_username
            db.session.commit()
            stream = existing_stream
            print(f"Updated existing stream: {stream_url} for {streamer_username} on {platform_type}")
        else:
            if platform_type.lower() == "chaturbate":
                stream = ChaturbateStream(
                    room_url=stream_url,
                    streamer_username=streamer_username,
                    type="chaturbate",
                    chaturbate_m3u8_url=stream_url
                )
            elif platform_type.lower() == "stripchat":
                stream = StripchatStream(
                    room_url=stream_url,
                    streamer_username=streamer_username,
                    type="stripchat",
                    stripchat_m3u8_url=stream_url
                )
            else:
                stream = Stream(
                    room_url=stream_url,
                    streamer_username=streamer_username,
                    type=platform_type
                )
            db.session.add(stream)
            db.session.commit()
            print(f"Created new stream: {stream_url} for {streamer_username} on {platform_type}")
            
        log_entry = Log(
            room_url=stream_url,
            event_type="stream_added",
            details={
                "message": "Stream added manually",
                "streamer_username": streamer_username,
                "platform": platform_type.lower()
            }
        )
        db.session.add(log_entry)
        db.session.commit()
        return stream

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
            if "Timed out" in str(e):
                logging.error("Timeout sending Telegram image, trying fallback text message.")
                try:
                    fallback_msg = f"🚨 Object Detection Alert\nPlatform: {platform_name}\nStreamer: {streamer_name}\nImage failed to send due to timeout."
                    with app.app_context():
                        recipients = TelegramRecipient.query.all()
                    for recipient in recipients:
                        send_text_message(fallback_msg, recipient.chat_id, None)
                    logging.info("Fallback text notification sent for %s on %s", streamer_name, platform_name)
                    return
                except Exception as e2:
                    logging.error("Fallback text notification failed: %s", e2)
            logging.error("Notification attempt %d failed: %s", attempt+1, e)
            time.sleep(2)
    logging.error("Failed to send notification after %d attempts", max_attempts)

def log_detection(detections, stream_url, annotated_image, platform_name, streamer_name):
    """
    Immediately log and send notifications for flagged object detections.
    Avoid sending duplicate alerts for the same set of objects.
    """
    detected_set = set(det["class"] for det in detections)
    last_set = last_video_alerted_objects.get(stream_url)
    if last_set is not None and detected_set == last_set:
        logging.info("Duplicate detection for %s; skipping alert.", streamer_name)
        return

    last_video_alerted_objects[stream_url] = detected_set

    timestamp = datetime.utcnow()
    ret, buffer = cv2.imencode('.jpg', annotated_image)
    image_data = buffer.tobytes() if ret else None

    assigned_agent = "Unassigned"
    assignment_id = None

    # Retrieve the stream from the database to extract its assignment and agent.
    with app.app_context():
        stream = Stream.query.filter_by(room_url=stream_url).first()
        if stream and stream.assignments and len(stream.assignments) > 0:
            assignment = stream.assignments[0]
            if assignment.agent:
                assigned_agent = assignment.agent.username
                assignment_id = assignment.id

    details = {
        "detections": detections,
        "timestamp": timestamp.isoformat(),
        "streamer_name": streamer_name,
        "platform": platform_name,
        "annotated_image": base64.b64encode(image_data).decode('utf-8') if image_data else None,
        "assigned_agent": assigned_agent
    }

    with app.app_context():
        log_entry = DetectionLog(
            room_url=stream_url,
            event_type="object_detection",
            details=details,
            detection_image=image_data,
            timestamp=timestamp,
            read=False,
            assigned_agent=assigned_agent,
            assignment_id=assignment_id
        )
        db.session.add(log_entry)
        db.session.commit()
        
        threading.Thread(target=async_send_notifications, args=(log_entry.id, platform_name, streamer_name)).start()

def update_latest_visual_log_with_audio(stream_url, transcript, detected_keywords):
    """Check if there's a recent visual detection log (object_detection) for this stream and update it with audio info."""
    with app.app_context():
        latest_log = Log.query.filter_by(room_url=stream_url, event_type='object_detection').order_by(Log.timestamp.desc()).first()
        if latest_log and (datetime.utcnow() - latest_log.timestamp) < timedelta(seconds=5):
            details = latest_log.details or {}
            details['audio_transcript'] = transcript
            details['audio_keywords'] = detected_keywords
            latest_log.details = details
            db.session.commit()
            logging.info("Updated visual detection log with audio info for stream %s", stream_url)
            return True
    return False

def process_combined_detection(stream_url, cancel_event):
    """
    Use a single PyAV container to process both video and audio detection.
    Video frames are processed immediately for object detection.
    Audio packets are accumulated in a buffer and processed in 5-second chunks for faster transcription.
    If the connection is lost or an error occurs during packet pull/decoding, attempt to reconnect.
    """
    platform_name, streamer_name = extract_stream_info_from_db(stream_url)
    if not platform_name or not streamer_name:
        logging.error("Stream %s not found. Aborting combined detection.", stream_url)
        return

    # Initialize sentiment analyzer (VADER)
    sentiment_analyzer = SentimentIntensityAnalyzer()

    while not cancel_event.is_set():
        if not check_stream_online(stream_url):
            logging.error("Stream %s appears offline. Aborting combined detection.", stream_url)
            return

        try:
            container = av.open(stream_url)
            logging.info("Connected to stream %s", stream_url)
        except Exception as e:
            logging.error("Failed to open stream %s: %s", stream_url, e)
            time.sleep(5)
            continue

        video_stream = next((s for s in container.streams if s.type == 'video'), None)
        audio_stream = next((s for s in container.streams if s.type == 'audio'), None)

        if not video_stream:
            logging.error("No video stream in %s", stream_url)
            container.close()
            return

        logging.info("Combined detection started for %s", stream_url)
        required_audio_bytes = 16000 * 2 * 10  # 5 seconds of audio (mono, 16-bit, 16kHz)
        audio_buffer = b""

        try:
            whisper_model = load_model("base")
            logging.info("Whisper model loaded for combined detection.")
        except Exception as e:
            logging.error("Error loading Whisper model: %s", e)
            whisper_model = None

        try:
            for packet in container.demux(video_stream, audio_stream):
                if cancel_event.is_set():
                    logging.info("Combined detection stopped for %s", stream_url)
                    break
                try:
                    for frame in packet.decode():
                        if cancel_event.is_set():
                            logging.info("Combined detection stopped for %s", stream_url)
                            break
                        if frame.__class__.__name__ == "VideoFrame":
                            img = frame.to_ndarray(format='bgr24')
                            detections = detect_frame_yolov8(img)
                            if detections:
                                annotated = annotate_frame(img, detections)
                                log_detection(detections, stream_url, annotated, platform_name, streamer_name)
                        elif frame.__class__.__name__ == "AudioFrame" and whisper_model is not None:
                            try:
                                audio_data = frame.to_ndarray().tobytes()
                                audio_buffer += audio_data
                            except Exception as e:
                                logging.error("Error converting audio frame: %s", e)
                                continue

                            if len(audio_buffer) >= required_audio_bytes:
                                try:
                                    # Convert audio to float32 and normalize
                                    audio_int16 = np.frombuffer(audio_buffer, dtype=np.int16)
                                    audio_float = audio_int16.astype(np.float32) / 32768.0

                                    # Resample to 16kHz if needed
                                    if audio_float.shape[0] != 16000 * 5:
                                        audio_float = signal.resample(audio_float, 16000 * 5)

                                    # Ensure mono channel
                                    if len(audio_float.shape) > 1:
                                        audio_float = audio_float.mean(axis=1)

                                    # Pad or trim to exact 5 seconds
                                    audio_input = whisper.pad_or_trim(audio_float)
                                    # Improved Whisper decoding config:
                                    # Using beam search with best_of sampling and a fixed temperature to enhance transcription quality.
                                    mel = whisper.log_mel_spectrogram(audio_input, n_mels=80).to(whisper_model.device)
                                    options = whisper.DecodingOptions(
                                        fp16=False,
                                        task="transcribe",  # Explicitly set transcription mode
                                        without_timestamps=True,  # Disable timestamp generation
                                        beam_size=5,
                                        temperature=0.0
                                    )
                                    result = whisper.decode(whisper_model, mel, options)
                                    text = result.text.strip().lower()
                                    logging.info("Combined audio transcription: '%s'", text)
                                    
                                    # Skip empty transcriptions.
                                    if not text:
                                        audio_buffer = b""
                                        continue

                                    current_time = datetime.utcnow()
                                    # Check for duplicate alerts using previous transcript and cooldown.
                                    if stream_url in last_audio_alerted_transcript:
                                        last_text, last_time = last_audio_alerted_transcript[stream_url]
                                        if text == last_text and (current_time - last_time).total_seconds() < ALERT_COOLDOWN_SECONDS:
                                            logging.info("Duplicate or cooldown audio alert for %s; skipping alert.", stream_url)
                                            audio_buffer = b""
                                            continue
                                    last_audio_alerted_transcript[stream_url] = (text, current_time)

                                    # New rate limiting: allow only one audio alert per cooldown period per stream.
                                    if stream_url not in audio_alert_timestamps:
                                        audio_alert_timestamps[stream_url] = []
                                    # Remove outdated timestamps.
                                    audio_alert_timestamps[stream_url] = [
                                        t for t in audio_alert_timestamps[stream_url]
                                        if (current_time - t).total_seconds() < ALERT_COOLDOWN_SECONDS
                                    ]
                                    if len(audio_alert_timestamps[stream_url]) >= 1:
                                        logging.info("Rate limit reached for audio alerts on %s; skipping alert.", stream_url)
                                        audio_buffer = b""
                                        continue
                                    # Record the new alert timestamp.
                                    audio_alert_timestamps[stream_url].append(current_time)

                                    # Perform sentiment analysis on the transcription.
                                    sentiment = sentiment_analyzer.polarity_scores(text)
                                    logging.info("Sentiment analysis for audio: %s", sentiment)

                                    # Process keywords detection.
                                    with app.app_context():
                                        keywords = [kw.keyword.lower() for kw in ChatKeyword.query.all()]
                                    detected = [kw for kw in keywords if kw in text]
                                    if detected:
                                        logging.info("Combined flagged audio keywords detected: %s", detected)
                                        # If there's a recent visual detection, update it with audio info.
                                        if not update_latest_visual_log_with_audio(stream_url, text, detected):
                                            with app.app_context():
                                                # Log the audio detection in DetectionLog so it shows up in notifications.
                                                log_entry = DetectionLog(
                                                    room_url=stream_url,
                                                    event_type='audio_detection',
                                                    details={
                                                        'keywords': detected,
                                                        'transcript': text,
                                                        'sentiment': sentiment,  # Sentiment analysis result included.
                                                        'platform': platform_name,
                                                        'streamer_name': streamer_name,
                                                        'timestamp': datetime.utcnow().isoformat()
                                                    },
                                                    read=False
                                                )
                                                db.session.add(log_entry)
                                                db.session.commit()
                                                threading.Thread(target=async_send_notifications, args=(log_entry.id, platform_name, streamer_name)).start()
                                except Exception as e:
                                    logging.error("Combined Whisper transcription error: %s", e)
                                audio_buffer = b""
                except Exception as e:
                    logging.error("Error decoding packet: %s", e)
                    break
        except Exception as e:
            logging.error("Error during demuxing: %s", e)
        finally:
            container.close()
            logging.info("Container closed for %s", stream_url)
            if cancel_event.is_set():
                break
            time.sleep(5)
    logging.info("Combined detection ended for %s", stream_url)

def check_stream_online(m3u8_url, timeout=10):
    try:
        response = requests.get(m3u8_url, timeout=timeout)
        return response.status_code == 200
    except Exception as e:
        logging.error("Stream check failed for %s: %s", m3u_url, e)
        return False

def parse_chat_messages(html_content, platform):
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
        response = requests.get(chat_url, timeout=10)
        if response.status_code != 200:
            logging.info("Livestream offline for %s. Skipping chat detection.", chat_url)
            return
    except Exception as e:
        logging.error("Error checking livestream status: %s", e)
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
                    with app.app_context():
                        log_entry = Log(
                            room_url=chat_url,
                            event_type="chat_detection",
                            details={
                                "keywords": [],
                                "username": "Unknown",
                                "ocr_text": ocr_text.strip(),
                                "streamer_name": streamer_name,
                                "platform": platform,
                            },
                            timestamp=datetime.utcnow()
                        )
                        db.session.add(log_entry)
                        db.session.commit()
            except Exception as e:
                logging.error("Error during screenshot processing: %s", e)
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

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python detection.py <stream_url>")
        sys.exit(1)
    
    stream_url = sys.argv[1]
    cancel_event = threading.Event()
    logging.basicConfig(level=logging.INFO)
    
    process_combined_detection(stream_url, cancel_event)
