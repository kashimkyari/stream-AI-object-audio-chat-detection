#!/usr/bin/env python
import os
import cv2
import time
import numpy as np
import threading
import logging
from datetime import datetime
from ultralytics import YOLO
from models import ChatKeyword, FlaggedObject, DetectionLog
from config import app
from extensions import db

# Global YOLOv8 model variable and thread lock
_yolo_model = None
_yolo_lock = threading.Lock()

def load_yolov8_model():
    """
    Loads the YOLOv8 model (using the nano version for speed) in a thread‐safe way.
    """
    global _yolo_model
    with _yolo_lock:
        if _yolo_model is None:
            try:
                _yolo_model = YOLO('yolov8n.pt')
                logging.info("YOLOv8 model loaded successfully.")
            except Exception as e:
                logging.error("Error loading YOLOv8 model: %s", e)
                _yolo_model = None
    return _yolo_model

def detect_frame_yolov8(frame):
    """
    Runs inference on the given frame using YOLOv8 and returns a list of detections.
    Each detection is a dict with keys: "class", "confidence", and "bbox" ([x, y, w, h]).
    """
    model = load_yolov8_model()
    if model is None:
        return []
    results = model(frame)
    detections = []
    for result in results:
        for box in result.boxes:
            bbox = box.xyxy.cpu().numpy()[0]  # [x1, y1, x2, y2]
            confidence = box.conf.cpu().numpy()[0]
            class_id = int(box.cls.cpu().numpy()[0])
            label = model.names[class_id] if class_id in model.names else str(class_id)
            # Convert bbox to [x, y, width, height]
            x1, y1, x2, y2 = bbox
            bbox_xywh = [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]
            detections.append({
                "class": label.lower(),
                "confidence": float(confidence),
                "bbox": bbox_xywh
            })
    return detections

def update_flagged_objects():
    """
    Retrieves flagged objects from the database along with their confidence thresholds.
    """
    with app.app_context():
        objects = FlaggedObject.query.all()
        return [
            {"name": obj.object_name.lower(), "threshold": float(obj.confidence_threshold)}
            for obj in objects
        ]

def filter_detections(detections):
    """
    Checks which detections match a flagged object (and meet the confidence threshold).
    """
    flagged_objs = update_flagged_objects()
    flagged_results = []
    for detection in detections:
        for flagged in flagged_objs:
            if detection["class"] == flagged["name"] and detection["confidence"] >= flagged["threshold"]:
                flagged_results.append(detection)
    return flagged_results

def annotate_frame(frame, detections):
    """
    Draws bounding boxes and labels on the frame for each detection.
    """
    annotated = frame.copy()
    for detection in detections:
        x, y, w, h = detection["bbox"]
        label = f'{detection["class"]} ({detection["confidence"]*100:.1f}%)'
        cv2.rectangle(annotated, (x, y), (x+w, y+h), (0, 0, 255), 2)
        cv2.putText(annotated, label, (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,0,255), 2)
    return annotated

def log_detection(detections, stream_url, annotated_image, captured_image):
    """
    Logs a detection event into the database.
    Note: DetectionLog should be defined in your models. Here detections are stringified 
    (consider serializing as JSON in a real-world app).
    """
    timestamp = datetime.utcnow().isoformat()
    with app.app_context():
        log_entry = DetectionLog(
            stream_url=stream_url,
            detections=str(detections),  # Replace with JSON serialization if desired.
            timestamp=timestamp,
            annotated_image=annotated_image,
            captured_image=captured_image
        )
        db.session.add(log_entry)
        db.session.commit()
    logging.info("Detection logged at %s for stream %s", timestamp, stream_url)

def process_stream(stream_url):
    """
    Continuously captures frames from the livestream, runs YOLOv8 object detection,
    filters flagged detections, annotates the frame, and logs the event if detections occur.
    """
    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        logging.error("Failed to open stream: %s", stream_url)
        return
    logging.info("Started processing stream: %s", stream_url)
    notification_cooldown = 10  # seconds
    last_notification_time = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            logging.warning("Failed to grab frame from stream: %s", stream_url)
            time.sleep(1)
            continue

        detections = detect_frame_yolov8(frame)
        flagged = filter_detections(detections)
        if flagged:
            current_time = time.time()
            if current_time - last_notification_time >= notification_cooldown:
                annotated = annotate_frame(frame, flagged)
                # Encode images as JPEG before logging
                ret1, annotated_buffer = cv2.imencode('.jpg', annotated)
                ret2, captured_buffer = cv2.imencode('.jpg', frame)
                if ret1 and ret2:
                    annotated_image = annotated_buffer.tobytes()
                    captured_image = captured_buffer.tobytes()
                    log_detection(flagged, stream_url, annotated_image, captured_image)
                    last_notification_time = current_time
        time.sleep(1)  # Process one frame per second

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python yolov8_stream_processor.py <stream_url>")
        sys.exit(1)
    stream_url = sys.argv[1]
    logging.basicConfig(level=logging.INFO)
    process_stream(stream_url)
