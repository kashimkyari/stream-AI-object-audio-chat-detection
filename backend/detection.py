import os
import cv2
import numpy as np
import spacy
from spacy.matcher import Matcher
import threading
import logging
from models import ChatKeyword, FlaggedObject
from config import app
from extensions import db

# ----------------------------
# Chat Detection Functions
# ----------------------------

# Load the spaCy language model and initialize the matcher for chat detection
nlp = spacy.load("en_core_web_sm")
matcher = Matcher(nlp.vocab)

def refresh_keywords():
    """
    Refresh the keyword matcher with flagged chat keywords from the database.
    Reinitializes the global matcher based on current keywords.
    """
    with app.app_context():
        keywords = [kw.keyword.lower() for kw in ChatKeyword.query.all()]
    global matcher
    matcher = Matcher(nlp.vocab)
    for word in keywords:
        pattern = [{"LOWER": word}]
        matcher.add(word, [pattern])
    logging.info("Chat keywords refreshed: %s", keywords)

def detect_chat(message):
    """
    Detect flagged keywords in a given chat message.
    
    Args:
        message (str): The chat message to analyze.
    
    Returns:
        dict: A dictionary with detection status, keywords (if flagged), and the original message.
    """
    refresh_keywords()
    doc = nlp(message.lower())
    matches = matcher(doc)
    detected = set()
    for match_id, start, end in matches:
        span = doc[start:end]
        detected.add(span.text)
    if detected:
        return {
            "status": "flagged",
            "keywords": list(detected),
            "message": message,
        }
    return {"status": "clean"}

def update_flagged_objects():
    """
    Return the list of flagged objects from the database along with their thresholds.
    
    Returns:
        list: A list of dictionaries, each containing the object name and threshold.
    """
    with app.app_context():
        objects = FlaggedObject.query.all()
        return [
            {"name": obj.object_name.lower(), "threshold": float(obj.confidence_threshold)}
            for obj in objects
        ]

# ----------------------------
# Object Detection Functions
# ----------------------------

# Global variables for MobileNetSSD model
_model_lock = threading.Lock()
_net = None

# Pre-defined class labels for MobileNetSSD
CLASS_NAMES = [
    "background", "aeroplane", "bicycle", "bird", "boat", "bottle",
    "bus", "car", "cat", "chair", "cow", "diningtable", "dog", "horse",
    "motorbike", "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"
]

def load_detector():
    """
    Load and return the MobileNetSSD model for object detection.
    This function ensures that the model is loaded only once.
    
    Returns:
        cv2.dnn_Net: The loaded DNN model, or None if model files are missing.
    """
    global _net
    with _model_lock:
        if _net is None:
            prototxt = os.path.join(app.root_path, "models", "MobileNetSSD_deploy.prototxt")
            model = os.path.join(app.root_path, "models", "MobileNetSSD_deploy.caffemodel")
            if not os.path.exists(prototxt) or not os.path.exists(model):
                logging.error("Model files not found in the models directory.")
                return None
            _net = cv2.dnn.readNetFromCaffe(prototxt, model)
            logging.info("MobileNetSSD model loaded.")
    return _net

def detect_frame(frame):
    """
    Perform object detection on a given frame using MobileNetSSD.
    
    Args:
        frame (numpy.ndarray): The input image frame in BGR format.
    
    Returns:
        list: A list of detections, each a dict with keys 'class', 'confidence', and 'bbox'
              where bbox is [x, y, width, height] in pixel coordinates.
    """
    net = load_detector()
    if net is None:
        return []
    
    (h, w) = frame.shape[:2]
    # Preprocess the frame: resize to 300x300 and create a blob
    blob = cv2.dnn.blobFromImage(cv2.resize(frame, (300, 300)), 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    detections = net.forward()
    
    results = []
    # Loop over the detections
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        # Filter out weak detections; threshold set at 0.6 (60%)
        if confidence > 0.6:
            idx = int(detections[0, 0, i, 1])
            # Ensure the detected class index is within bounds
            if idx >= len(CLASS_NAMES):
                continue
            label = CLASS_NAMES[idx]
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (startX, startY, endX, endY) = box.astype("int")
            bbox = [startX, startY, endX - startX, endY - startY]
            results.append({
                "class": label,
                "confidence": float(confidence),
                "bbox": bbox
            })
    return results
