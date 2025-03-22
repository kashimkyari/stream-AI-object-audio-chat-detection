import datetime
from flask import session, request
from flask_socketio import SocketIO, emit
from models import db, User, ChatMessage
from config import app

# Initialize Flask-SocketIO with CORS settings as needed.
socketio = SocketIO(app, cors_allowed_origins="*")

# Dictionary to store online users (username -> Socket.IO session id)
online_users = {}

@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    if not user_id:
        return False  # Disconnect unauthorized client.
    user = User.query.get(user_id)
    if not user:
        return False
    # Store online user using the username as key.
    online_users[user.username] = request.sid
    # Notify all clients about the updated online users (usernames).
    emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    username = None
    # Find the username based on the Socket.IO session id.
    for uname, sid in online_users.items():
        if sid == request.sid:
            username = uname
            break
    if username:
        online_users.pop(username, None)
        emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('send_message')
def handle_send_message(data):
    """
    Expected data:
    {
        "receiver_username": "<str>",
        "message": "<message text>"
    }
    """
    sender_id = session.get('user_id')
    if not sender_id:
        emit('error', {'error': 'User not authenticated.'})
        return

    receiver_username = data.get('receiver_username')
    message_text = data.get('message')

    if not receiver_username or not message_text:
        emit('error', {'error': 'Missing receiver_username or message.'})
        return

    # Look up the receiver by username.
    receiver = User.query.filter_by(username=receiver_username).first()
    if not receiver:
        emit('error', {'error': f'User {receiver_username} not found.'})
        return

    try:
        # Create and save the chat message in the database.
        msg = ChatMessage(
            sender_id=sender_id,
            receiver_id=receiver.id,
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
    # If the receiver is online (by username), send the message directly.
    if receiver.username in online_users:
        emit('receive_message', serialized_msg, room=online_users[receiver.username])
    # Also send the message back to the sender to confirm sending.
    emit('receive_message', serialized_msg, room=request.sid)

@socketio.on('typing')
def handle_typing(data):
    """
    Expected data:
    {
        "receiver_username": "<str>",
        "typing": <bool>
    }
    """
    sender_id = session.get('user_id')
    receiver_username = data.get('receiver_username')
    is_typing = data.get('typing', False)

    if not sender_id or not receiver_username:
        return

    # If the receiver is online, notify them of the typing status.
    if receiver_username in online_users:
        sender = User.query.get(sender_id)
        emit('typing', {'sender_username': sender.username, 'typing': is_typing},
             room=online_users[receiver_username])

if __name__ == '__main__':
    socketio.run(app, debug=True)
