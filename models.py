from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Join table for group membership
group_members = db.Table(
    "group_members",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("group_id", db.Integer, db.ForeignKey("chat_group.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    avatar_url = db.Column(db.String(256), default="")
    about = db.Column(db.String(140), default="Hey there! I'm using WhatsClone.")
    is_online = db.Column(db.Boolean, default=False)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "avatar_url": self.avatar_url,
            "about": self.about,
            "is_online": self.is_online,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }


class ChatGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    avatar_url = db.Column(db.String(256), default="")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship("User", secondary=group_members, backref="groups")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "members": [u.to_dict() for u in self.members],
        }


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Either recipient_id (1-on-1) OR group_id (group chat) is set, not both
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    group_id = db.Column(db.Integer, db.ForeignKey("chat_group.id"), nullable=True)

    body = db.Column(db.Text, nullable=True)
    media_url = db.Column(db.String(256), nullable=True)
    media_type = db.Column(db.String(20), nullable=True)  # image, video, audio, file

    status = db.Column(db.String(10), default="sent")  # sent, delivered, read
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    sender = db.relationship("User", foreign_keys=[sender_id])

    def room_name(self):
        """Deterministic room name for a 1-on-1 or group conversation."""
        if self.group_id:
            return f"group_{self.group_id}"
        ids = sorted([self.sender_id, self.recipient_id])
        return f"dm_{ids[0]}_{ids[1]}"

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_username": self.sender.username if self.sender else None,
            "recipient_id": self.recipient_id,
            "group_id": self.group_id,
            "body": self.body,
            "media_url": self.media_url,
            "media_type": self.media_type,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
        }


def dm_room_name(user_a_id, user_b_id):
    ids = sorted([user_a_id, user_b_id])
    return f"dm_{ids[0]}_{ids[1]}"
