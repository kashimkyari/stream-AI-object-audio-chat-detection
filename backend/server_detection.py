import os
import base64
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
import cv2
import logging
from flask import request, jsonify
from config import app
from extensions import db
from models import Log, Stream
from notifications import send_notifications

# Load COCO‑SSD (SSD MobileNet V2) from TensorFlow Hub once on startup.
MODEL_URL = "https://tfhub.dev/tensorflow/ssd_mobilenet_v2/2"
model = hub.load(MODEL_URL)
logging.info("COCO‑SSD model loaded from TensorFlow Hub.")

# COCO class labels (index 0 is background)
COCO_LABELS = [
    'background', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
    'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'stop sign',
    'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
    'elephant', 'bear', 'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag',
    'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball', 'kite',
    'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
    'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana',
    'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
    'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'dining table',
    'toilet', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
    'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'book', 'clock',
    'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
]

def detect_objects_in_image(image_np, threshold=0.6):
    """
    Run object detection on an RGB image (as a NumPy array) using the COCO‑SSD model.
    Returns a list of detections with class label, confidence, and bounding box.
    """
    input_tensor = tf.convert_to_tensor(image_np)
    input_tensor = tf.image.convert_image_dtype(input_tensor, tf.float32)
    input_tensor = tf.expand_dims(input_tensor, 0)  # shape: [1, height, width, 3]
    result = model(input_tensor)
    result = {key: value.numpy() for key, value in result.items()}
    detections = []
    num_detections = int(result["num_detections"][0])
    for i in range(num_detections):
        score = result["detection_scores"][0][i]
        if score < threshold:
            continue
        class_id = int(result["detection_classes"][0][i])
        if class_id >= len(COCO_LABELS):
            continue
        label = COCO_LABELS[class_id]
        # Detection box: normalized coordinates [ymin, xmin, ymax, xmax]
        box = result["detection_boxes"][0][i]
        h, w, _ = image_np.shape
        ymin, xmin, ymax, xmax = box
        bbox = [int(xmin * w), int(ymin * h), int((xmax - xmin) * w), int((ymax - ymin) * h)]
        detections.append({
            "class": label,
            "confidence": float(score),
            "bbox": bbox
        })
    return detections

@app.route("/api/server-detect", methods=["POST"])
def server_detect():
    """
    Endpoint to perform server‑side object detection.
    Expects a JSON payload with:
      - "image": a base64‑encoded JPEG (data URL format accepted)
      - "stream_url": URL of the stream
      - "timestamp": ISO timestamp string
    Detected objects are logged and notifications are sent.
    """
    try:
        data = request.get_json(force=True)
        image_data = data.get("image")
        stream_url = data.get("stream_url")
        timestamp = data.get("timestamp")

        if not image_data or not stream_url:
            return jsonify({"message": "Missing required fields"}), 400

        # Remove the data URL prefix if present
        if image_data.startswith("data:image"):
            image_data = image_data.split(",")[1]
        image_bytes = base64.b64decode(image_data)
        image_array = np.frombuffer(image_bytes, dtype=np.uint8)
        bgr_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        detections = detect_objects_in_image(rgb_image, threshold=0.6)

        # Get stream details (if available)
        stream = Stream.query.filter_by(room_url=stream_url).first()
        platform = stream.type if stream else "unknown"
        streamer_name = stream.streamer_username if stream else "unknown"

        # Create a log entry for the detection event
        log_entry = Log(
            room_url=stream_url,
            event_type="object_detection",
            details={
                "detections": detections,
                "timestamp": timestamp,
                "streamer_name": streamer_name,
                "platform": platform
            }
        )
        db.session.add(log_entry)
        db.session.commit()

        # Send notifications based on detected objects
        send_notifications(log_entry, detections)

        return jsonify({
            "message": "Detection logged",
            "detections": detections
        }), 200

    except Exception as e:
        logging.exception("Error in server detection:")
        return jsonify({"message": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
