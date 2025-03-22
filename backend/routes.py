import os
import time
import json
import uuid
import base64
import shutil
import threading
from collections import defaultdict
from datetime import datetime, timedelta
import cv2
import numpy as np
from PIL import Image
import m3u8
import requests
from flask import request, jsonify, session, send_from_directory, current_app, Response
from sqlalchemy.orm import joinedload  # Added for eager loading
from config import app
from extensions import db
from models import (
    User, Stream, Assignment, Log, ChatKeyword, FlaggedObject, 
    TelegramRecipient, ChaturbateStream, StripchatStream
)
from utils import allowed_file, login_required
from notifications import send_notifications
from scraping import (
    scrape_stripchat_data, scrape_chaturbate_data, run_scrape_job, scrape_jobs,
    stream_creation_jobs, run_stream_creation_job
)
from detection import process_combined_detection, chat_detection_loop
import speech_recognition as sr
from werkzeug.utils import secure_filename
from threading import Condition
import queue

# Global dictionary to store detection threads and their cancellation events keyed by stream_url.
detection_threads = {}
sse_clients = []
sse_queue = queue.Queue()
sse_condition = Condition()

# --------------------------------------------------------------------
# Authentication Endpoints
# --------------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    user = User.query.filter(
        (User.username == username) | (User.email == username)
    ).filter_by(password=data.get("password")).first()
    if user:
        session.permanent = True
        session["user_id"] = user.id
        return jsonify({"message": "Login successful", "role": user.role})
    return jsonify({"message": "Invalid credentials"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    return jsonify({"message": "Logged out"})

@app.route("/api/session", methods=["GET"])
def check_session():
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        if user is None:
            return jsonify({"logged_in": False}), 401
        return jsonify({"logged_in": True, "user": user.serialize()})
    return jsonify({"logged_in": False}), 401

# --------------------------------------------------------------------
# Agent Management Endpoints
# --------------------------------------------------------------------
@app.route("/api/agents", methods=["GET"])
@login_required(role="admin")
def get_agents():
    agents = User.query.filter_by(role="agent").all()
    return jsonify([agent.serialize() for agent in agents])

@app.route("/api/agents", methods=["POST"])
@login_required(role="admin")
def create_agent():
    data = request.get_json()
    required_fields = ["username", "password", "firstname", "lastname", "email", "phonenumber"]
    if any(field not in data for field in required_fields):
        return jsonify({"message": "Missing required fields"}), 400
    if User.query.filter((User.username == data["username"]) | (User.email == data["email"])).first():
        return jsonify({"message": "Username or email exists"}), 400
    agent = User(
        username=data["username"],
        password=data["password"],
        firstname=data["firstname"],
        lastname=data["lastname"],
        email=data["email"],
        phonenumber=data["phonenumber"],
        staffid=data.get("staffid"),
        role="agent",
    )
    db.session.add(agent)
    db.session.commit()
    return jsonify({"message": "Agent created", "agent": agent.serialize()}), 201

@app.route("/api/agents/<int:agent_id>", methods=["PUT"])
@login_required(role="admin")
def update_agent(agent_id):
    agent = User.query.filter_by(id=agent_id, role="agent").first()
    if not agent:
        return jsonify({"message": "Agent not found"}), 404
    data = request.get_json()
    updates = {}
    if "username" in data and (new_uname := data["username"].strip()):
        agent.username = new_uname
        updates["username"] = new_uname
    if "password" in data and (new_pwd := data["password"].strip()):
        agent.password = new_pwd
        updates["password"] = "updated"
    db.session.commit()
    return jsonify({"message": "Agent updated", "updates": updates})

@app.route("/api/agents/<int:agent_id>", methods=["DELETE"])
@login_required(role="admin")
def delete_agent(agent_id):
    agent = User.query.filter_by(id=agent_id, role="agent").first()
    if not agent:
        return jsonify({"message": "Agent not found"}), 404
    db.session.delete(agent)
    db.session.commit()
    return jsonify({"message": "Agent deleted"})

# --------------------------------------------------------------------
# Stream Management Endpoints
# --------------------------------------------------------------------
@app.route("/api/streams", methods=["GET"])
@login_required(role="admin")
def get_streams():
    platform = request.args.get("platform", "").strip().lower()
    streamer = request.args.get("streamer", "").strip().lower()
    if platform == "chaturbate":
        streams = ChaturbateStream.query.options(
            joinedload(ChaturbateStream.assignments).joinedload(Assignment.agent)
        ).filter(ChaturbateStream.streamer_username.ilike(f"%{streamer}%")).all()
    elif platform == "stripchat":
        streams = StripchatStream.query.options(
            joinedload(StripchatStream.assignments).joinedload(Assignment.agent)
        ).filter(StripchatStream.streamer_username.ilike(f"%{streamer}%")).all()
    else:
        streams = Stream.query.options(
            joinedload(Stream.assignments).joinedload(Assignment.agent)
        ).all()
    return jsonify([stream.serialize() for stream in streams])

@app.route("/api/streams", methods=["POST"])
@login_required(role="admin")
def create_stream():
    data = request.get_json()
    room_url = data.get("room_url", "").strip().lower()
    platform = data.get("platform", "Chaturbate").strip()
    if not room_url:
        return jsonify({"message": "Room URL required"}), 400
    if platform.lower() == "chaturbate" and "chaturbate.com/" not in room_url:
        return jsonify({"message": "Invalid Chaturbate URL"}), 400
    if platform.lower() == "stripchat" and "stripchat.com/" not in room_url:
        return jsonify({"message": "Invalid Stripchat URL"}), 400
    if Stream.query.filter_by(room_url=room_url).first():
        return jsonify({"message": "Stream exists"}), 400
    streamer_username = room_url.rstrip("/").split("/")[-1]
    if platform.lower() == "chaturbate":
        scraped_data = scrape_chaturbate_data(room_url)
        if not scraped_data:
            return jsonify({"message": "Failed to scrape Chaturbate details"}), 500
        stream = ChaturbateStream(
            room_url=room_url,
            streamer_username=streamer_username,
            type="chaturbate",
            chaturbate_m3u8_url=scraped_data["chaturbate_m3u8_url"],
        )
    elif platform.lower() == "stripchat":
        scraped_data = scrape_stripchat_data(room_url)
        if not scraped_data:
            return jsonify({"message": "Failed to scrape Stripchat details"}), 500
        stream = StripchatStream(
            room_url=room_url,
            streamer_username=streamer_username,
            type="stripchat",
            stripchat_m3u8_url=scraped_data["stripchat_m3u8_url"],
        )
    else:
        return jsonify({"message": "Invalid platform"}), 400
    db.session.add(stream)
    db.session.commit()
    log_entry = Log(
        room_url=room_url,
        event_type="stream_added",
        details={
            "message": "Stream added",
            "streamer_username": streamer_username,
            "platform": platform.lower()
        }
    )
    db.session.add(log_entry)
    db.session.commit()
    return jsonify({"message": "Stream created", "stream": stream.serialize()}), 201

@app.route("/api/streams/<int:stream_id>", methods=["DELETE"])
@login_required(role="admin")
def delete_stream(stream_id):
    stream = Stream.query.get(stream_id)
    if not stream:
        return jsonify({"message": "Stream not found"}), 404

    if stream.type == 'chaturbate':
        child_stream = ChaturbateStream.query.get(stream_id)
    elif stream.type == 'stripchat':
        child_stream = StripchatStream.query.get(stream_id)
    else:
        child_stream = None

    if child_stream:
        db.session.delete(child_stream)

    db.session.delete(stream)
    db.session.commit()
    return jsonify({"message": "Stream deleted"}), 200

# --------------------------------------------------------------------
# Interactive Stream Creation Endpoints
# --------------------------------------------------------------------
@app.route("/api/streams/interactive", methods=["POST"])
@login_required(role="admin")
def interactive_create_stream():
    data = request.get_json()
    room_url = data.get("room_url", "").strip().lower()
    platform = data.get("platform", "Chaturbate").strip().lower()
    agent_id = data.get("agent_id")
    
    # Convert agent_id to integer if provided and non-empty.
    if agent_id and str(agent_id).strip() != "":
        try:
            agent_id = int(agent_id)
        except ValueError:
            return jsonify({"message": "Invalid agent ID"}), 400
    else:
        agent_id = None
    
    if not room_url:
        return jsonify({"message": "Room URL required"}), 400
    if platform == "chaturbate" and "chaturbate.com/" not in room_url:
        return jsonify({"message": "Invalid Chaturbate URL"}), 400
    if platform == "stripchat" and "stripchat.com/" not in room_url:
        return jsonify({"message": "Invalid Stripchat URL"}), 400
    if Stream.query.filter_by(room_url=room_url).first():
        return jsonify({"message": "Stream exists"}), 400
    
    job_id = str(uuid.uuid4())
    stream_creation_jobs[job_id] = {"progress": 0, "message": "Job initialized"}
    
    threading.Thread(
        target=run_stream_creation_job, 
        args=(job_id, room_url, platform, agent_id),
        daemon=True
    ).start()
    
    return jsonify({"message": "Stream creation job started", "job_id": job_id}), 202

@app.route("/api/streams/interactive/sse")
@login_required(role="admin")
def stream_creation_sse():
    job_id = request.args.get("job_id")
    if not job_id:
        return jsonify({"message": "Job id required"}), 400
    def event_stream():
        from scraping import stream_creation_jobs
        while True:
            job_status = stream_creation_jobs.get(job_id)
            if job_status:
                data = json.dumps(job_status)
                yield f"data: {data}\n\n"
                if job_status.get("progress", 0) >= 100:
                    break
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")

# --------------------------------------------------------------------
# Assignment Endpoints
# --------------------------------------------------------------------
@app.route("/api/assign", methods=["POST"])
@login_required(role="admin")
def assign_agent_to_stream():
    data = request.get_json()
    agent_id = data.get("agent_id")
    stream_id = data.get("stream_id")
    if not agent_id or not stream_id:
        return jsonify({"message": "Both agent_id and stream_id are required."}), 400
    try:
        assignment = Assignment(agent_id=agent_id, stream_id=stream_id)
        db.session.add(assignment)
        db.session.commit()
        return jsonify({"message": "Assignment created successfully."}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": "Assignment creation failed", "error": str(e)}), 500

# --------------------------------------------------------------------
# Keyword, Object, and Telegram Routes
# --------------------------------------------------------------------
@app.route("/api/keywords", methods=["GET"])
@login_required(role="admin")
def get_keywords():
    keywords = ChatKeyword.query.all()
    return jsonify([kw.serialize() for kw in keywords])

@app.route("/api/keywords", methods=["POST"])
@login_required(role="admin")
def create_keyword():
    data = request.get_json()
    keyword = data.get("keyword", "").strip()
    if not keyword:
        return jsonify({"message": "Keyword required"}), 400
    if ChatKeyword.query.filter_by(keyword=keyword).first():
        return jsonify({"message": "Keyword exists"}), 400
    kw = ChatKeyword(keyword=keyword)
    db.session.add(kw)
    db.session.commit()
    refresh_keywords()
    return jsonify({"message": "Keyword added", "keyword": kw.serialize()}), 201

@app.route("/api/keywords/<int:keyword_id>", methods=["PUT"])
@login_required(role="admin")
def update_keyword(keyword_id):
    kw = ChatKeyword.query.get(keyword_id)
    if not kw:
        return jsonify({"message": "Keyword not found"}), 404
    data = request.get_json()
    new_kw = data.get("keyword", "").strip()
    if not new_kw:
        return jsonify({"message": "New keyword required"}), 400
    kw.keyword = new_kw
    db.session.commit()
    refresh_keywords()
    return jsonify({"message": "Keyword updated", "keyword": kw.serialize()})

@app.route("/api/keywords/<int:keyword_id>", methods=["DELETE"])
@login_required(role="admin")
def delete_keyword(keyword_id):
    kw = ChatKeyword.query.get(keyword_id)
    if not kw:
        return jsonify({"message": "Keyword not found"}), 404
    db.session.delete(kw)
    db.session.commit()
    refresh_keywords()
    return jsonify({"message": "Keyword deleted"})

@app.route("/api/objects", methods=["GET"])
@login_required(role="admin")
def get_objects():
    objects = FlaggedObject.query.all()
    return jsonify([obj.serialize() for obj in objects])

@app.route("/api/objects", methods=["POST"])
@login_required(role="admin")
def create_object():
    data = request.get_json()
    obj_name = data.get("object_name", "").strip()
    if not obj_name:
        return jsonify({"message": "Object name required"}), 400
    if FlaggedObject.query.filter_by(object_name=obj_name).first():
        return jsonify({"message": "Object exists"}), 400
    obj = FlaggedObject(object_name=obj_name)
    db.session.add(obj)
    db.session.commit()
    return jsonify({"message": "Object added", "object": obj.serialize()}), 201

@app.route("/api/objects/<int:object_id>", methods=["PUT"])
@login_required(role="admin")
def update_object(object_id):
    obj = FlaggedObject.query.get(object_id)
    if not obj:
        return jsonify({"message": "Object not found"}), 404
    data = request.get_json()
    new_name = data.get("object_name", "").strip()
    if not new_name:
        return jsonify({"message": "New name required"}), 400
    obj.object_name = new_name
    db.session.commit()
    return jsonify({"message": "Object updated", "object": obj.serialize()})

@app.route("/api/objects/<int:object_id>", methods=["DELETE"])
@login_required(role="admin")
def delete_object(object_id):
    obj = FlaggedObject.query.get(object_id)
    if not obj:
        return jsonify({"message": "Object not found"}), 404
    db.session.delete(obj)
    db.session.commit()
    return jsonify({"message": "Object deleted"})

@app.route("/api/telegram_recipients", methods=["GET"])
@login_required(role="admin")
def get_telegram_recipients():
    recipients = TelegramRecipient.query.all()
    return jsonify([r.serialize() for r in recipients])

@app.route("/api/telegram_recipients", methods=["POST"])
@login_required(role="admin")
def create_telegram_recipient():
    data = request.get_json()
    username = data.get("telegram_username")
    chat_id = data.get("chat_id")
    if not username or not chat_id:
        return jsonify({"message": "Telegram username and chat_id required"}), 400
    if TelegramRecipient.query.filter_by(telegram_username=username).first():
        return jsonify({"message": "Recipient exists"}), 400
    recipient = TelegramRecipient(telegram_username=username, chat_id=chat_id)
    db.session.add(recipient)
    db.session.commit()
    return jsonify({"message": "Recipient added", "recipient": recipient.serialize()}), 201

@app.route("/api/telegram_recipients/<int:recipient_id>", methods=["DELETE"])
@login_required(role="admin")
def delete_telegram_recipient(recipient_id):
    recipient = TelegramRecipient.query.get(recipient_id)
    if not recipient:
        return jsonify({"message": "Recipient not found"}), 404
    db.session.delete(recipient)
    db.session.commit()
    return jsonify({"message": "Recipient deleted"})

# --------------------------------------------------------------------
# Dashboard Endpoints
# --------------------------------------------------------------------
@app.route("/api/dashboard", methods=["GET"])
@login_required(role="admin")
def get_dashboard():
    streams = Stream.query.options(joinedload(Stream.assignments).joinedload(Assignment.agent)).all()
    data = []
    for stream in streams:
        assignment = stream.assignments[0] if stream.assignments else None
        data.append({
            **stream.serialize(),
            "agent": assignment.agent.serialize() if assignment and assignment.agent else None,
            "confidence": 0.8
        })
    return jsonify({"ongoing_streams": len(data), "streams": data})

@app.route("/api/agent/dashboard", methods=["GET"])
@login_required(role="agent")
def get_agent_dashboard():
    agent_id = session["user_id"]
    assignments = Assignment.query.filter_by(agent_id=agent_id).all()
    return jsonify({
        "ongoing_streams": len(assignments),
        "assignments": [a.stream.serialize() for a in assignments if a.stream]
    })

# --------------------------------------------------------------------
# Detection and Notification Endpoints
# --------------------------------------------------------------------
@app.route("/detection-images/<filename>")
def serve_detection_image(filename):
    return send_from_directory("detections", filename)

@app.route("/api/detect", methods=["POST"])
def unified_detect():
    data = request.get_json()
    text = data.get("text", "")
    visual_frame = data.get("visual_frame", None)
    audio_flag = None
    visual_results = []
    if visual_frame:
        visual_results = detect_frame(np.array(visual_frame))
    chat_results = detect_chat(text)
    return jsonify({
        "audio": audio_flag,
        "chat": chat_results,
        "visual": visual_results
    })

def sse_notify(data):
    """Notify all SSE clients with new data"""
    with sse_condition:
        sse_queue.put(data)
        sse_condition.notify_all()

@app.route("/api/notification-events")
def notification_events():
    """SSE endpoint for real-time notifications"""
    def event_stream():
        while True:
            with sse_condition:
                sse_condition.wait(timeout=10)
                try:
                    while True:
                        data = sse_queue.get_nowait()
                        yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    pass

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={'Cache-Control': 'no-cache'}
    )

@app.route("/api/livestream", methods=["POST"])
def get_livestream():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"error": "Missing M3U8 URL"}), 400
    m3u8_url = data["url"]
    try:
        response = requests.get(m3u8_url, timeout=10)
        if response.status_code != 200:
            return jsonify({"error": "Failed to fetch M3U8 file"}), 500
        playlist = m3u8.loads(response.text)
        if not playlist.playlists:
            return jsonify({"error": "No valid streams found"}), 400
        stream_url = playlist.playlists[0].uri
        return jsonify({"stream_url": stream_url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/trigger-detection", methods=["POST"])
def trigger_detection():
    data = request.get_json()
    stream_url = data.get("stream_url")
    if not stream_url:
        return jsonify({"error": "Missing stream_url"}), 400

    try:
        response = requests.get(stream_url, timeout=10)
        if response.status_code != 200:
            return jsonify({"error": "Stream appears offline"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Use the combined detection function for audio and video detection
    try:
        from detection import process_combined_detection, chat_detection_loop
    except ImportError as e:
        return jsonify({"error": f"Detection module not available: {str(e)}"}), 500

    if stream_url in detection_threads:
        return jsonify({"message": "Detection already running for this stream"}), 200

    cancel_event = threading.Event()
    unified_thread = threading.Thread(
        target=process_combined_detection,
        args=(stream_url, cancel_event),
        daemon=True
    )
    unified_thread.start()
    # Chat detection still runs separately every 60 seconds
    chat_thread = threading.Thread(
        target=chat_detection_loop,
        args=(stream_url, cancel_event, 60),
        daemon=True
    )
    chat_thread.start()

    detection_threads[stream_url] = (unified_thread, chat_thread, cancel_event)

    return jsonify({"message": "Detection started"}), 200

@app.route("/api/detect-advanced", methods=["POST"])
def advanced_detect():
    try:
        if 'audio' in request.files:
            audio_file = request.files['audio']
            stream_url = request.form.get('stream_url')
            timestamp = request.form.get('timestamp')
            audio_bytes = audio_file.read()
            try:
                wf = wave.open(BytesIO(audio_bytes), "rb")
            except Exception as e:
                return jsonify({"message": "Error processing audio file", "error": str(e)}), 500
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
                return jsonify({"message": "Audio file must be mono, 16-bit, 16kHz WAV"}), 400
            model = load_vosk_model()
            if model is None:
                return jsonify({"message": "Vosk model not loaded"}), 500
            recognizer = KaldiRecognizer(model, 16000)
            recognizer.SetWords(True)
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                recognizer.AcceptWaveform(data)
            final_result = json.loads(recognizer.FinalResult())
            text = final_result.get("text", "").lower()
            keywords = [kw.keyword.lower() for kw in ChatKeyword.query.all()]
            detected_keywords = [kw for kw in keywords if kw in text]
            if detected_keywords:
                audio_file_data = base64.b64encode(audio_bytes).decode('utf-8')
                log_entry = Log(
                    room_url=stream_url,
                    event_type='audio_detection',
                    details={
                        'keywords': detected_keywords,
                        'transcript': text,
                        'audio_file_data': audio_file_data,
                        'timestamp': timestamp
                    }
                )
                db.session.add(log_entry)
                db.session.commit()
                send_notifications(log_entry, {"keywords": detected_keywords})
                return jsonify({"message": "Audio keywords detected", "keywords": detected_keywords}), 200
            return jsonify({"message": "No audio keywords detected"}), 200
        if 'chat_image' in request.files:
            file = request.files["chat_image"]
            stream_url = request.form.get("stream_url")
            image_bytes = file.read()
            image_stream = BytesIO(image_bytes)
            image = Image.open(image_stream)
            ocr_text = pytesseract.image_to_string(image)
            refresh_keywords()
            flagged_keywords = [kw.keyword for kw in ChatKeyword.query.all()]
            detected_keywords = [kw for kw in flagged_keywords if kw.lower() in ocr_text.lower()]
            if detected_keywords:
                flagged_image_data = base64.b64encode(image_bytes).decode('utf-8')
                stream = Stream.query.filter_by(room_url=stream_url).first() if stream_url else None
                log_entry = Log(
                    room_url=stream_url or "chat",
                    event_type="chat_detection",
                    details={
                        'keywords': detected_keywords,
                        'ocr_text': ocr_text,
                        'streamer_name': stream.streamer_username if stream else "Unknown",
                        'platform': stream.type if stream else "Unknown",
                    }
                )
                db.session.add(log_entry)
                db.session.commit()
                send_notifications(log_entry)
                return jsonify({"message": "Chat keywords detected", "keywords": detected_keywords}), 200
            else:
                return jsonify({"message": "No chat keywords detected"}), 200
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"message": "No valid JSON or files provided"}), 400
        if "type" in data:
            event_type = data.get('type')
            stream_url = data.get('stream_url')
            timestamp_str = data.get('timestamp')
            timestamp_obj = datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.utcnow()
            log_entry = Log(
                room_url=stream_url,
                timestamp=timestamp_obj,
                read=False
            )
            if event_type == 'visual':
                log_entry.event_type = 'object_detection'
                log_entry.details = {
                    'detections': data.get('detections'),
                    'annotated_image': data.get('annotated_image'),
                    'confidence': data.get('confidence'),
                    'streamer_name': data.get('streamer_name'),
                    'platform': data.get('platform')
                }
            elif event_type == 'audio':
                log_entry.event_type = 'audio_detection'
                log_entry.details = {
                    'keyword': data.get('keyword'),
                    'confidence': data.get('confidence'),
                    'streamer_name': data.get('streamer_name'),
                    'platform': data.get('platform')
                }
            else:
                return jsonify({"error": "Invalid event type"}), 400
            db.session.add(log_entry)
            db.session.commit()
            send_notifications(log_entry)
            return jsonify({"message": "JSON-based detection logged"}), 201
        if "keyword" in data:
            keyword = data.get("keyword")
            timestamp = data.get("timestamp")
            stream_url = data.get("stream_url")
            if not keyword or not timestamp or not stream_url:
                return jsonify({"message": "Missing required fields"}), 400
            log_entry = Log(
                room_url=stream_url,
                event_type="audio_detection",
                details={
                    "keyword": keyword,
                    "timestamp": timestamp,
                }
            )
            db.session.add(log_entry)
            db.session.commit()
            send_notifications(log_entry, {"keyword": keyword})
            return jsonify({"message": "Keyword detection logged successfully"}), 201
        if "detections" in data:
            stream_url = data.get("stream_url")
            detections = data.get("detections", [])
            annotated_image = data.get("annotated_image")
            captured_image = data.get("captured_image")
            timestamp = data.get("timestamp")
            if not stream_url or not detections:
                return jsonify({"message": "Missing required fields"}), 400
            stream = Stream.query.filter_by(room_url=stream_url).first()
            platform = stream.type if stream else "unknown"
            streamer_name = stream.streamer_username if stream else "unknown"
            # Safely determine the assigned agent username
            assigned_agent = "Unassigned"
            if stream and stream.assignments and len(stream.assignments) > 0 and stream.assignments[0].agent:
                assigned_agent = stream.assignments[0].agent.username
            log_entry = Log(
                room_url=stream_url,
                event_type="object_detection",
                details={
                    "detections": detections,
                    "annotated_image": annotated_image,
                    "captured_image": captured_image,
                    "timestamp": timestamp,
                    "streamer_name": streamer_name,
                    "platform": platform,
                    "assigned_agent": assigned_agent
                }
            )
            db.session.add(log_entry)
            db.session.commit()
            event_data = {**log_entry.details, "event_type": log_entry.event_type}
            send_notifications(event_data)
            return jsonify({
                "message": "Object detection logged",
                "detections": detections
            }), 200
        return jsonify({"message": "No valid detection type provided"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/stop-detection", methods=["POST"])
def stop_detection_route():
    data = request.get_json()
    stream_url = data.get("stream_url")
    if not stream_url:
        return jsonify({"error": "Missing stream_url"}), 400
    if stream_url not in detection_threads:
        return jsonify({"message": "No detection running for this stream"}), 404
    threads, chat_thread, cancel_event = detection_threads.pop(stream_url)
    cancel_event.set()
    threads.join(timeout=5)
    chat_thread.join(timeout=5)
    return jsonify({"message": "Detection stopped"}), 200

# --------------------------------------------------------------------
# Health Check
# --------------------------------------------------------------------
@app.route("/health")
def health():
    return "OK", 200

@app.route("/api/logs", methods=["GET"])
@login_required(role="admin")
def get_logs():
    logs = Log.query.order_by(Log.timestamp.desc()).limit(100).all()
    return jsonify([{
        "id": log.id,
        "event_type": log.event_type,
        "timestamp": log.timestamp.isoformat(),
        "details": log.details,
        "read": log.read
    } for log in logs])
