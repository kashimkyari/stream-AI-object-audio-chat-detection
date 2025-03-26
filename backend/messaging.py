import datetime
from flask import session
from flask_socketio import SocketIO, emit, join_room
from models import db, User, ChatMessage, DetectionLog
from config import app

socketio = SocketIO(app, cors_allowed_origins="*")
online_users = {}  # {user_id: {sid: string, role: string}}


@socketio.on('connect')
def handle_connect():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            user.online = True
            user.last_active = datetime.now(timezone.utc)
            db.session.commit()
            online_users[user_id] = request.sid
            emit('user_status', {'userId': user_id, 'online': True}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    user_id = session.get('user_id')
    if user_id and user_id in online_users:
        user = User.query.get(user_id)
        if user:
            user.online = False
            db.session.commit()
            del online_users[user_id]
            emit('user_status', {'userId': user_id, 'online': False}, broadcast=True)

@socketio.on('user_activity')
def handle_activity():
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            user.last_active = datetime.now(timezone.utc)
            db.session.commit()

@socketio.on('forward_notification')
def handle_forward_notification(data):
    notification_id = data.get('notification_id')
    agent_id = data.get('agent_id')
    
    notification = DetectionLog.query.get(notification_id)
    agent = User.query.filter_by(id=agent_id, role='agent').first()
    
    if not notification or not agent:
        emit('error', {'message': 'Invalid notification or agent'})
        return
    
    # Create system message
    sys_msg = ChatMessage(
        sender_id=session['user_id'],
        receiver_id=agent.id,
        message=f"🚨 Forwarded Alert: {notification.details.get('message', 'New detection')}",
        details=notification.details,
        is_system=True,
        timestamp=datetime.datetime.utcnow()
    )
    db.session.add(sys_msg)
    db.session.commit()
    
    # Send to agent if online
    if agent.id in online_users:
        emit('receive_message', sys_msg.serialize(), room=online_users[agent.id]['sid'])
    
    # Send to admin UI
    emit('notification_forwarded', {
        'notification_id': notification.id,
        'agent_id': agent.id,
        'timestamp': datetime.datetime.utcnow().isoformat()
    }, room='admin')

@socketio.on('admin_subscribe')
def handle_admin_subscribe():
    if online_users.get(session.get('user_id'), {}).get('role') == 'admin':
        join_room('admin')


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
