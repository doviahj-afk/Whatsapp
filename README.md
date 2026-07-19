# WhatsClone — Real-time Chat App (Flask + SocketIO)

A WhatsApp-style messaging app: 1-on-1 chats, group chats, media sharing (images/audio/video/files),
typing indicators, online/offline presence, and read status.

Built to run cleanly in **Termux** — uses SQLite (no separate DB server) and SocketIO's
`threading` async mode (no eventlet/gevent, so no native compilation headaches on aarch64).

## 1. Install in Termux

```bash
pkg update && pkg install python -y
cd whatsapp_clone
pip install -r requirements.txt
```

## 2. Run it

```bash
python app.py
```

This starts the server on `http://0.0.0.0:5000`. On first run it auto-creates `chat.db` (SQLite).

- On your phone: open `http://localhost:5000` in the browser.
- From another device on the same Wi-Fi: find your phone's local IP (`ip addr` in Termux)
  and visit `http://<that-ip>:5000` from the other device.

## 3. Try it out

1. Go to `/register`, create two accounts (e.g. in two browser tabs, or incognito for the 2nd).
2. Log in as each, click a contact in the sidebar, and start chatting — messages arrive live via WebSocket.
3. Click **+ New Group** to create a group chat with multiple members.
4. Click the 📎 icon to send a photo, voice note, or file.

## 4. Turn it into an installable Android app (PWA)

Right now it's a mobile-friendly web app. To make it installable like a real app without
needing Android Studio:

1. Deploy it somewhere reachable (or keep running it locally + use Cloudflare Tunnel,
   which you're already set up with, to expose it over HTTPS).
2. Add a `manifest.json` and service worker (I can generate these next) so Chrome on
   Android shows "Add to Home Screen" / "Install app".
3. Alternative: wrap it with **Capacitor** to produce a real `.apk` — this needs a one-time
   Node/Android SDK setup, which is heavier than Termux alone can do, but doable via a
   cloud build service if you don't want to install Android Studio.

## Project structure

```
whatsapp_clone/
├── app.py              # Flask app, routes, SocketIO events
├── models.py            # User, ChatGroup, Message (SQLAlchemy)
├── config.py             # App config
├── requirements.txt
├── templates/            # login, register, chat UI
└── static/
    ├── css/style.css
    ├── js/chat.js
    └── uploads/           # uploaded media lands here
```

## What's implemented vs. what's next

**Done:** auth, 1-on-1 messaging, group messaging, media upload, typing indicators,
online/offline presence, read status, message history.

**Not yet (real WhatsApp has these too):** end-to-end encryption (Signal Protocol — a
significant separate build), push notifications when the app is closed, voice/video
calls, message deletion/editing, multi-device sync.

## Security note before you deploy this anywhere public

- Change `SECRET_KEY` in `config.py` — don't ship the default.
- This uses session-based auth suited for a single web app; if you build a separate
  native Android client later, you'll want token-based auth (JWT) instead.
- File uploads are capped at 25MB and restricted to known-safe extensions, but you should
  still run this behind a reverse proxy (e.g. nginx or your Cloudflare Tunnel) in production.
