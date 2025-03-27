import os
import json
import logging
import base64
from config import app
from models import Log, TelegramRecipient
from extensions import db
from telegram import Bot, InputFile
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
import asyncio
from io import BytesIO

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
executor = ThreadPoolExecutor(max_workers=5)  # Adjust max_workers as needed

def get_bot(token=None):
    """Return a Telegram Bot instance."""
    if token is None:
        token = TELEGRAM_TOKEN
    return Bot(token=token)

async def send_text_message_async(msg, chat_id, token=None):
    """Send a text message asynchronously."""
    try:
        bot = get_bot(token)
        await bot.send_message(chat_id=chat_id, text=msg)
        logging.info(f"Telegram text message sent to chat_id {chat_id}.")
        return True
    except Exception as e:
        logging.error(f"Failed to send Telegram message to chat_id {chat_id}: {e}")
        return False

async def send_telegram_image_async(photo_file, caption, chat_id, token=None):
    """
    Send an image message asynchronously.
    photo_file should be a file-like object (e.g. BytesIO).
    """
    try:
        bot = get_bot(token)
        await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=caption)
        logging.info(f"Telegram image sent to chat_id {chat_id}.")
        return True
    except Exception as e:
        logging.error(f"Failed to send Telegram image to chat_id {chat_id}: {e}")
        return False

def send_text_message(msg, chat_id, token=None):
    """Wrapper to run the async function in a synchronous context."""
    return asyncio.run(send_text_message_async(msg, chat_id, token))

def send_telegram_image(photo_file, caption, chat_id, token=None):
    """Wrapper to run the async function in a synchronous context."""
    return asyncio.run(send_telegram_image_async(photo_file, caption, chat_id, token))

def send_notifications(log_entry, platform_name=None, streamer_name=None):
    """
    Sends notifications based on the log_entry from the unified detection API.
    For object detection events, if a stored annotated image is available, it is sent as an image.
    For chat detection events, a Telegram text message is sent with details about the flagged chat message.
    """
    try:
        with app.app_context():
            details = log_entry.details or {}
            platform = platform_name if platform_name is not None else details.get('platform', 'Unknown Platform')
            streamer = streamer_name if streamer_name is not None else details.get('streamer_name', 'Unknown Streamer')

            # For object detection.
            detections_list = details.get('detections') or []
            confidence = None
            if detections_list and isinstance(detections_list, list):
                confidence = detections_list[0].get('confidence')
            conf_str = f"{(confidence * 100):.1f}%" if isinstance(confidence, (int, float)) else "N/A"

            recipients = TelegramRecipient.query.all()
            if not recipients:
                logging.warning("No Telegram recipients found; skipping notification.")
                return

            if log_entry.event_type == 'object_detection':
                detected_objects = ", ".join([d["class"] for d in detections_list]) if detections_list else "No details"
                message = (
                    f"🚨 **Object Detection Alert**\n"
                    f"🎥 Platform: {platform}\n"
                    f"📡 Streamer: {streamer}\n"
                    f"📌 Objects Detected: {detected_objects}\n"
                    f"🔍 Confidence: {conf_str}"
                )
                if log_entry.detection_image:
                    for recipient in recipients:
                        photo_file = BytesIO(log_entry.detection_image)
                        photo_file.seek(0)
                        executor.submit(send_telegram_image, photo_file, message, recipient.chat_id, None)
                else:
                    for recipient in recipients:
                        executor.submit(send_text_message, message, recipient.chat_id, None)

            elif log_entry.event_type == 'audio_detection':
                keyword = details.get('keyword', 'N/A')
                transcript = details.get('transcript', 'No transcript available.')
                message = (
                    f"🔊 **Audio Detection Alert**\n"
                    f"🎥 Platform: {platform}\n"
                    f"📡 Streamer: {streamer}\n"
                    f"🔑 Keyword: {keyword}\n"
                    f"📝 Transcript: {transcript[:300]}..."
                )
                for recipient in recipients:
                    executor.submit(send_text_message, message, recipient.chat_id, None)

            # Modify the chat detection notification message
            elif log_entry.event_type == 'chat_detection':
                detections = details.get('detections', [{}])
                first_detection = detections[0] if detections else {}
                
                message = (
                    f"💬 **Chat Detection Alert**\n"
                    f"🎥 Platform: {platform}\n"
                    f"📡 Streamer: {streamer}\n"
                    f"👤 Sender: {first_detection.get('sender', 'Unknown')}\n"
                    f"🔍 Keywords: {', '.join(first_detection.get('keywords', []))}\n"
                    f"📝 Message: {first_detection.get('message', '')[:300]}..."
                
                )
                for recipient in recipients:
                    executor.submit(send_text_message, message, recipient.chat_id, None)

            elif log_entry.event_type == 'video_notification':
                msg_detail = details.get('message', 'No additional details.')
                message = (
                    f"🎥 **Video Notification**\n"
                    f"🎥 Platform: {platform}\n"
                    f"📡 Streamer: {streamer}\n"
                    f"📝 Message: {msg_detail}"
                )
                for recipient in recipients:
                    executor.submit(send_text_message, message, recipient.chat_id, None)

            else:
                message = (
                    f"🔔 **{log_entry.event_type.replace('_', ' ').title()}**\n"
                    f"🎥 Platform: {platform}\n"
                    f"📡 Streamer: {streamer}\n"
                    f"📌 Details: {json.dumps(details, indent=2)[:500]}..."
                )
                for recipient in recipients:
                    executor.submit(send_text_message, message, recipient.chat_id, None)
    except Exception as e:
        logging.error(f"Notification error: {str(e)}")
