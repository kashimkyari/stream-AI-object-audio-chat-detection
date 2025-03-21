from datetime import datetime
from extensions import db

class User(db.Model):
    """
    User model represents an application user, such as agents or administrators.
    """
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    firstname = db.Column(db.String(80), nullable=False)
    lastname = db.Column(db.String(80), nullable=False)
    phonenumber = db.Column(db.String(20), nullable=False)
    staffid = db.Column(db.String(20), index=True)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(10), nullable=False, default="agent", index=True)

    # Relationship with Assignment
    assignments = db.relationship('Assignment', back_populates='agent', lazy='selectin', cascade="all, delete")

    def __repr__(self):
        return f"<User {self.username}>"

    def serialize(self, include_relationships=True):
        """Serialize the User model into a dictionary."""
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "phonenumber": self.phonenumber,
            "staffid": self.staffid,
            "role": self.role,
        }
        
        # Only include assignments if explicitly requested and prevent circular references
        if include_relationships and hasattr(self, 'assignments'):
            data["assignments"] = [assignment.serialize(include_relationships=False) for assignment in self.assignments]
            
        return data


class Stream(db.Model):
    """
    Stream model serves as a base class for different streaming platforms.
    Uses polymorphic identity to distinguish between Chaturbate and Stripchat streams.
    """
    __tablename__ = "streams"
    id = db.Column(db.Integer, primary_key=True)
    room_url = db.Column(db.String(300), unique=True, nullable=False, index=True)
    streamer_username = db.Column(db.String(100), index=True)
    type = db.Column(db.String(50), index=True)  # Discriminator column for polymorphic identity

    # Relationship with Assignment
    assignments = db.relationship('Assignment', back_populates='stream', lazy='selectin', cascade="all, delete")

    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': 'stream',
    }

    def __repr__(self):
        return f"<Stream {self.room_url}>"

    def serialize(self, include_relationships=True):
        """Serialize the Stream model into a dictionary."""
        data = {
            "id": self.id,
            "room_url": self.room_url,
            "streamer_username": self.streamer_username,
            "platform": self.type.capitalize() if self.type else None,
        }
        
        # Only include assignments if explicitly requested and prevent circular references
        if include_relationships and hasattr(self, 'assignments'):
            data["assignments"] = [assignment.serialize(include_relationships=False) for assignment in self.assignments]
            
        return data


class ChaturbateStream(Stream):
    """
    ChaturbateStream model extends Stream for Chaturbate-specific streams.
    Stores the m3u8 URL for Chaturbate.
    """
    __tablename__ = "chaturbate_streams"
    id = db.Column(db.Integer, db.ForeignKey("streams.id"), primary_key=True)
    chaturbate_m3u8_url = db.Column(db.String(300), nullable=True, index=True)

    __mapper_args__ = {
        'polymorphic_identity': 'chaturbate'
    }

    def __repr__(self):
        return f"<ChaturbateStream {self.room_url}>"

    def serialize(self, include_relationships=True):
        """Serialize the ChaturbateStream model into a dictionary."""
        data = super().serialize(include_relationships=include_relationships)
        data.update({
            "platform": "Chaturbate",
            "chaturbate_m3u8_url": self.chaturbate_m3u8_url,
        })
        return data


class StripchatStream(Stream):
    """
    StripchatStream model extends Stream for Stripchat-specific streams.
    Stores the m3u8 URL for Stripchat.
    """
    __tablename__ = "stripchat_streams"
    id = db.Column(db.Integer, db.ForeignKey("streams.id"), primary_key=True)
    stripchat_m3u8_url = db.Column(db.String(300), nullable=True, index=True)

    __mapper_args__ = {
        'polymorphic_identity': 'stripchat'
    }

    def __repr__(self):
        return f"<StripchatStream {self.room_url}>"

    def serialize(self, include_relationships=True):
        """Serialize the StripchatStream model into a dictionary."""
        data = super().serialize(include_relationships=include_relationships)
        data.update({
            "platform": "Stripchat",
            "stripchat_m3u8_url": self.stripchat_m3u8_url,
        })
        return data


class Assignment(db.Model):
    """
    Assignment model links a User (agent) with a Stream.
    """
    __tablename__ = "assignments"
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    stream_id = db.Column(db.Integer, db.ForeignKey('streams.id'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationships: load agent eagerly so it is available immediately on creation.
    agent = db.relationship('User', back_populates='assignments', lazy='joined')
    stream = db.relationship('Stream', back_populates='assignments', lazy='selectin')

    __table_args__ = (
        db.Index('idx_assignment_agent_stream', 'agent_id', 'stream_id'),
    )

    def __repr__(self):
        # Use a safe fallback in case agent is not loaded
        agent_username = self.agent.username if self.agent else "Unassigned"
        return f"<Assignment Agent:{agent_username} Stream:{self.stream_id}>"

    def serialize(self, include_relationships=True):
        """Serialize the Assignment model into a dictionary."""
        data = {
            "id": self.id,
            "agent_id": self.agent_id,
            "stream_id": self.stream_id,
            "created_at": self.created_at.isoformat(),
        }
        
        # Only include related objects if explicitly requested; provide safe fallbacks
        if include_relationships:
            data["agent"] = self.agent.serialize(include_relationships=False) if self.agent else None
            data["stream"] = self.stream.serialize(include_relationships=False) if self.stream else None
                
        return data


class Log(db.Model):
    """
    Log model records events such as detections, video notifications, and chat events.
    """
    __tablename__ = "logs"
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime(timezone=True), default=datetime.utcnow, index=True)
    room_url = db.Column(db.String(300), index=True)
    event_type = db.Column(db.String(50), index=True)
    details = db.Column(db.JSON)  # Stores detection details, images, etc.
    read = db.Column(db.Boolean, default=False, index=True)

    __table_args__ = (
        db.Index('idx_logs_room_event', 'room_url', 'event_type'),
        db.Index('idx_logs_timestamp_read', 'timestamp', 'read'),
    )

    def __repr__(self):
        return f"<Log {self.event_type} @ {self.room_url}>"

    def serialize(self):
        """Serialize the Log model into a dictionary."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "room_url": self.room_url,
            "event_type": self.event_type,
            "details": self.details,
            "read": self.read,
        }


class ChatKeyword(db.Model):
    """
    ChatKeyword model stores keywords for flagging chat messages.
    """
    __tablename__ = "chat_keywords"
    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(100), unique=True, nullable=False, index=True)

    def __repr__(self):
        return f"<ChatKeyword {self.keyword}>"

    def serialize(self):
        """Serialize the ChatKeyword model into a dictionary."""
        return {"id": self.id, "keyword": self.keyword}


class FlaggedObject(db.Model):
    """
    FlaggedObject model stores objects to be flagged during detection,
    along with their confidence thresholds.
    """
    __tablename__ = "flagged_objects"
    id = db.Column(db.Integer, primary_key=True)
    object_name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    confidence_threshold = db.Column(db.Numeric(3, 2), default=0.8)

    def __repr__(self):
        return f"<FlaggedObject {self.object_name}>"

    def serialize(self):
        """Serialize the FlaggedObject model into a dictionary."""
        return {
            "id": self.id,
            "object_name": self.object_name,
            "confidence_threshold": float(self.confidence_threshold),
        }


class TelegramRecipient(db.Model):
    """
    TelegramRecipient model stores Telegram user information for notifications.
    """
    __tablename__ = "telegram_recipients"
    id = db.Column(db.Integer, primary_key=True)
    telegram_username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    chat_id = db.Column(db.String(50), nullable=False, index=True)

    def __repr__(self):
        return f"<TelegramRecipient {self.telegram_username}>"

    def serialize(self):
        """Serialize the TelegramRecipient model into a dictionary."""
        return {
            "id": self.id,
            "telegram_username": self.telegram_username,
            "chat_id": self.chat_id,
        }


class DetectionLog(db.Model):
    """
    DetectionLog model stores detection events, including the annotated image.
    """
    __tablename__ = "detection_logs"
    id = db.Column(db.Integer, primary_key=True)
    room_url = db.Column(db.String(255), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    details = db.Column(db.JSON, nullable=True)
    detection_image = db.Column(db.LargeBinary, nullable=True)  # JPEG image bytes
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    read = db.Column(db.Boolean, default=False)

    def serialize(self):
        return {
            "id": self.id,
            "room_url": self.room_url,
            "event_type": self.event_type,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "read": self.read,
        }


# New model for realtime messaging
class ChatMessage(db.Model):
    """
    ChatMessage model stores messages exchanged between users (admin/agent).
    """
    __tablename__ = "chat_messages"
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read = db.Column(db.Boolean, default=False, index=True)

    def serialize(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'receiver_id': self.receiver_id,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'read': self.read,
        }
