import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user,
)
from flask_socketio import SocketIO, join_room, emit
from werkzeug.utils import secure_filename

from config import Config
from models import db, User, ChatGroup, Message, dm_room_name

app = Flask(__name__)
app.config.from_object(Config)

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# threading async_mode avoids needing eventlet/gevent native extensions,
# which is friendlier for Termux/aarch64 builds.
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
    )


# ---------- Auth routes ----------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        phone = request.form.get("phone", "").strip() or None

        if not username or not password:
            flash("Username and password are required.")
            return redirect(url_for("register"))

        if User.query.filter_by(username=username).first():
            flash("Username already taken.")
            return redirect(url_for("register"))

        user = User(username=username, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            flash("Invalid username or password.")
            return redirect(url_for("login"))

        login_user(user)
        user.is_online = True
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    current_user.is_online = False
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    logout_user()
    return redirect(url_for("login"))


# ---------- Main app routes ----------

@app.route("/")
@login_required
def index():
    contacts = User.query.filter(User.id != current_user.id).all()
    groups = current_user.groups
    return render_template("index.html", contacts=contacts, groups=groups)


@app.route("/api/messages/dm/<int:other_user_id>")
@login_required
def get_dm_history(other_user_id):
    room = dm_room_name(current_user.id, other_user_id)
    msgs = (
        Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.recipient_id == other_user_id))
            | ((Message.sender_id == other_user_id) & (Message.recipient_id == current_user.id))
        )
        .order_by(Message.created_at.asc())
        .all()
    )
    return jsonify([m.to_dict() for m in msgs])


@app.route("/api/messages/group/<int:group_id>")
@login_required
def get_group_history(group_id):
    msgs = (
        Message.query.filter_by(group_id=group_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return jsonify([m.to_dict() for m in msgs])


@app.route("/api/groups", methods=["POST"])
@login_required
def create_group():
    data = request.get_json()
    name = data.get("name", "").strip()
    member_ids = data.get("member_ids", [])

    if not name:
        return jsonify({"error": "Group name is required"}), 400

    group = ChatGroup(name=name, created_by=current_user.id)
    group.members.append(current_user)
    for uid in member_ids:
        u = User.query.get(uid)
        if u:
            group.members.append(u)

    db.session.add(group)
    db.session.commit()
    return jsonify(group.to_dict()), 201


@app.route("/api/upload", methods=["POST"])
@login_required
def upload_media():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Invalid or missing file"}), 400

    filename = secure_filename(file.filename)
    unique_name = f"{datetime.utcnow().timestamp()}_{filename}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    file.save(filepath)

    ext = filename.rsplit(".", 1)[1].lower()
    if ext in {"png", "jpg", "jpeg", "gif", "webp"}:
        media_type = "image"
    elif ext in {"mp4", "mov"}:
        media_type = "video"
    elif ext in {"mp3", "wav", "ogg", "m4a"}:
        media_type = "audio"
    else:
        media_type = "file"

    return jsonify({
        "media_url": url_for("static", filename=f"uploads/{unique_name}"),
        "media_type": media_type,
    })


# ---------- SocketIO events ----------

@socketio.on("connect")
def handle_connect():
    if current_user.is_authenticated:
        current_user.is_online = True
        db.session.commit()
        emit("presence", {"user_id": current_user.id, "is_online": True}, broadcast=True)


@socketio.on("disconnect")
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.is_online = False
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        emit("presence", {"user_id": current_user.id, "is_online": False}, broadcast=True)


@socketio.on("join")
def handle_join(data):
    """Join a DM or group room so messages route correctly."""
    room = data.get("room")
    if room:
        join_room(room)


@socketio.on("send_message")
def handle_send_message(data):
    """
    data = {
      recipient_id: int (for DM) OR group_id: int (for group),
      body: str,
      media_url: str (optional),
      media_type: str (optional)
    }
    """
    if not current_user.is_authenticated:
        return

    recipient_id = data.get("recipient_id")
    group_id = data.get("group_id")

    msg = Message(
        sender_id=current_user.id,
        recipient_id=recipient_id,
        group_id=group_id,
        body=data.get("body"),
        media_url=data.get("media_url"),
        media_type=data.get("media_type"),
    )
    db.session.add(msg)
    db.session.commit()

    room = msg.room_name()
    emit("new_message", msg.to_dict(), room=room)


@socketio.on("typing")
def handle_typing(data):
    room = data.get("room")
    if room:
        emit("typing", {
            "user_id": current_user.id,
            "username": current_user.username,
        }, room=room, include_self=False)


@socketio.on("mark_read")
def handle_mark_read(data):
    message_id = data.get("message_id")
    msg = Message.query.get(message_id)
    if msg:
        msg.status = "read"
        db.session.commit()
        room = msg.room_name()
        emit("message_status", {"message_id": message_id, "status": "read"}, room=room)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    # host 0.0.0.0 so it's reachable from other devices on your local network
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
