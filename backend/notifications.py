import os
import json
import logging
from config import app
from models import Log, TelegramRecipient, Stream, Assignment, User
from extensions import db
from telegram import Bot
from concurrent.futures import ThreadPoolExecutor

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
executor = ThreadPoolExecutor(max_workers=5)  # Thread pool for notifications

def get_bot(token=None):
    """Return a Telegram Bot instance."""
    if token is None:
        token = TELEGRAM_TOKEN
    return Bot(token=token)

def send_text_message(msg, chat_id, token=None):
    try:
        bot = Bot(TELEGRAM_TOKEN)
        bot.sendMessage(chat_id=chat_id, text=msg)
        logging.info(f"Telegram text message sent to chat_id {chat_id}.")
        return True
    except Exception as e:
        logging.error(f"Failed to send Telegram message to chat_id {chat_id}: {e}")
        return False

def send_telegram_image(image_url, caption, log_id, token=None):
    """
    Send an image message to Telegram.
    Assumes `image_url` is a URL or a data URL that Telegram accepts.
    """
    try:
        bot = Bot(token or TELEGRAM_TOKEN)
        bot.send_photo(chat_id=chat_id, photo=image_url, caption=caption)
        logging.info(f"Telegram image sent for log id {log_id}.")
        return True
    except Exception as e:
        logging.error(f"Failed to send Telegram image for log id {log_id}: {e}")
        return False

def send_notifications(log_entry, detections=None):
    """
    Sends notifications from videoplayer.js to all Telegram recipients.
    Iterates over all recipients and uses the thread pool executor to send messages.
    """
    try:
        details = log_entry.details
        streamer = details.get('streamer_name', 'Unknown Streamer')
        platform = details.get('platform', 'Unknown Platform').capitalize()
        confidence = details.get('confidence', 0)
        
        # Get all Telegram recipients
        recipients = TelegramRecipient.query.all()
        if not recipients:
            logging.warning("No Telegram recipients found; skipping notification.")
            return

        if log_entry.event_type == 'object_detection':
            message = f"🚨 Visual Detection on {platform}\n"
            message += f"Streamer: {streamer}\n"
            message += f"Detected {len(detections)} objects\n"
            message += f"Confidence: {confidence:.0%}"
            if details.get('annotated_image'):
                # Send image-based notification to all recipients
                for recipient in recipients:
                    executor.submit(send_telegram_image, details['annotated_image'], message, log_entry.id, None)
            else:
                for recipient in recipients:
                    executor.submit(send_text_message, message, recipient.chat_id, None)
                    
        elif log_entry.event_type == 'audio_detection':
            message = f"🔊 Audio Detection on {platform}\n"
            message += f"Streamer: {streamer}\n"
            message += f"Keyword: {details.get('keyword', 'N/A')}\n"
            message += f"Confidence: {confidence:.0%}"
            for recipient in recipients:
                executor.submit(send_text_message, message, recipient.chat_id, None)
                    
        elif log_entry.event_type == 'chat_detection':
            message = f"💬 Chat Detection on {platform}\n"
            message += f"Streamer: {streamer}\n"
            keywords = details.get('keywords', [])
            message += f"Keywords: {', '.join(keywords) if keywords else 'None'}\n"
            ocr_excerpt = details.get('ocr_text', '')
            message += f"OCR Excerpt: {ocr_excerpt[:200]}..."  # Truncate long text
            for recipient in recipients:
                executor.submit(send_text_message, message, recipient.chat_id, None)
                    
        elif log_entry.event_type == 'video_notification':
            message = f"🎥 Video Alert on {platform}\n"
            message += f"Streamer: {streamer}\n"
            message += f"Message: {details.get('message', 'Video event detected')}"
            for recipient in recipients:
                executor.submit(send_text_message, message, recipient.chat_id, None)
                    
        else:  # Handle unknown event types
            message = f"🔔 {log_entry.event_type.replace('_', ' ').title()} on {platform}\n"
            message += f"Streamer: {streamer}\n"
            message += f"Details: {json.dumps(details, indent=2)[:500]}..."  # Limit message length
            for recipient in recipients:
                executor.submit(send_text_message, message, recipient.chat_id, None)
            
    except Exception as e:
        logging.error(f"Notification error: {str(e)}")
