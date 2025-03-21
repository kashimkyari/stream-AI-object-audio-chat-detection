import datetime
from flask import session, request
from flask_socketio import SocketIO, emit
from models import db, User, ChatMessage
from config import app

# Initialize Flask-SocketIO with CORS settings as needed.
socketio = SocketIO(app, cors_allowed_origins="*")

# Dictionary to keep track of online users.
# Maps user_id to their Socket.IO session id.
online_users = {}

@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    # If the user is not authenticated, disconnect immediately.
    if not user_id:
        return False  # Disconnect unauthorized client.
    online_users[user_id] = request.sid
    # Notify all clients about the updated online users.
    emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    # Remove the user from the online users list.
    user_id = None
    for uid, sid in online_users.items():
        if sid == request.sid:
            user_id = uid
            break
    if user_id:
        online_users.pop(user_id, None)
        emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    """
    Expected data:
      {
          "receiver_id": <int>,
          "message": "<message text>"
      }
    """
    sender_id = session.get('user_id')
    if not sender_id:
        emit('error', {'error': 'User not authenticated.'})
        return
    receiver_id = data.get('receiver_id')
    message_text = data.get('message')
    if not receiver_id or not message_text:
        emit('error', {'error': 'Missing receiver_id or message.'})
        return
    try:
        # Create and save the message in the database.
        msg = ChatMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=message_text,
            timestamp=datetime.datetime.utcnow(),
            read=False
        )
        db.session.add(msg)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        emit('error', {'error': str(e)})
        return

    serialized_msg = msg.serialize()
    # If the receiver is online, send the message directly.
    if receiver_id in online_users:
        emit('receive_message', serialized_msg, room=online_users[receiver_id])
    # Also send the message back to the sender to confirm sending.
    emit('receive_message', serialized_msg, room=request.sid)

@socketio.on('typing')
def handle_typing(data):
    """
    Expected data:
      {
          "receiver_id": <int>,
          "typing": <bool>
      }
    """
    sender_id = session.get('user_id')
    receiver_id = data.get('receiver_id')
    is_typing = data.get('typing', False)
    if not sender_id or not receiver_id:
        return
    # Notify the receiver if they are online.
    if receiver_id in online_users:
        emit('typing', {'sender_id': sender_id, 'typing': is_typing}, room=online_users[receiver_id])

# Additional events such as message read receipts can be implemented similarly.
if __name__ == '__main__':
    # Run the SocketIO server; adjust host/port as necessary.
    socketio.run(app, debug=True)
