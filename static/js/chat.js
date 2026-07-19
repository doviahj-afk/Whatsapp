const appEl = document.getElementById("app");
const currentUserId = parseInt(appEl.dataset.userId);
const currentUsername = appEl.dataset.username;

const socket = io();

let activeConv = null; // { type: 'dm'|'group', id, name }
let typingTimeout = null;

const chatEmpty = document.getElementById("chatEmpty");
const chatActive = document.getElementById("chatActive");
const messagesEl = document.getElementById("messages");
const chatTitle = document.getElementById("chatTitle");
const chatSubtitle = document.getElementById("chatSubtitle");
const chatAvatar = document.getElementById("chatAvatar");
const typingIndicator = document.getElementById("typingIndicator");
const composerForm = document.getElementById("composerForm");
const messageInput = document.getElementById("messageInput");
const fileInput = document.getElementById("fileInput");

function roomForConv(conv) {
  if (conv.type === "group") return `group_${conv.id}`;
  const ids = [currentUserId, conv.id].sort((a, b) => a - b);
  return `dm_${ids[0]}_${ids[1]}`;
}

function openConversation(type, id, name) {
  activeConv = { type, id, name };
  chatEmpty.style.display = "none";
  chatActive.style.display = "flex";
  chatTitle.textContent = name;
  chatSubtitle.textContent = type === "group" ? "Group chat" : "";
  chatAvatar.textContent = name[0].toUpperCase();
  messagesEl.innerHTML = "";
  typingIndicator.textContent = "";

  document.querySelectorAll(".conv-item").forEach((el) => el.classList.remove("active"));
  const sel = document.querySelector(`.conv-item[data-type="${type}"][data-id="${id}"]`);
  if (sel) sel.classList.add("active");

  socket.emit("join", { room: roomForConv(activeConv) });

  const endpoint = type === "group"
    ? `/api/messages/group/${id}`
    : `/api/messages/dm/${id}`;

  fetch(endpoint)
    .then((r) => r.json())
    .then((msgs) => msgs.forEach(renderMessage));
}

function renderMessage(msg) {
  const bubble = document.createElement("div");
  const isOut = msg.sender_id === currentUserId;
  bubble.className = `bubble ${isOut ? "out" : "in"}`;

  let html = "";
  if (activeConv && activeConv.type === "group" && !isOut) {
    html += `<div class="sender">${escapeHtml(msg.sender_username)}</div>`;
  }
  if (msg.body) {
    html += `<div class="text">${escapeHtml(msg.body)}</div>`;
  }
  if (msg.media_url) {
    if (msg.media_type === "image") {
      html += `<img src="${msg.media_url}" alt="photo">`;
    } else if (msg.media_type === "video") {
      html += `<video src="${msg.media_url}" controls></video>`;
    } else if (msg.media_type === "audio") {
      html += `<audio src="${msg.media_url}" controls></audio>`;
    } else {
      html += `<a href="${msg.media_url}" target="_blank">📄 Download file</a>`;
    }
  }
  const time = new Date(msg.created_at);
  html += `<div class="time">${time.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>`;

  bubble.innerHTML = html;
  messagesEl.appendChild(bubble);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- Sending messages ----------

composerForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const body = messageInput.value.trim();
  if (!body || !activeConv) return;

  const payload = { body };
  if (activeConv.type === "group") payload.group_id = activeConv.id;
  else payload.recipient_id = activeConv.id;

  socket.emit("send_message", payload);
  messageInput.value = "";
});

messageInput.addEventListener("input", () => {
  if (!activeConv) return;
  socket.emit("typing", { room: roomForConv(activeConv) });
});

fileInput.addEventListener("change", async () => {
  if (!fileInput.files.length || !activeConv) return;
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  const res = await fetch("/api/upload", { method: "POST", body: formData });
  const data = await res.json();
  if (data.error) {
    alert(data.error);
    return;
  }

  const payload = { media_url: data.media_url, media_type: data.media_type };
  if (activeConv.type === "group") payload.group_id = activeConv.id;
  else payload.recipient_id = activeConv.id;

  socket.emit("send_message", payload);
  fileInput.value = "";
});

// ---------- Conversation list clicks ----------

document.querySelectorAll(".conv-item").forEach((el) => {
  el.addEventListener("click", () => {
    openConversation(el.dataset.type, parseInt(el.dataset.id), el.dataset.name);
  });
});

// ---------- Socket events ----------

socket.on("new_message", (msg) => {
  if (!activeConv) return;
  const belongsToActive =
    (activeConv.type === "group" && msg.group_id === activeConv.id) ||
    (activeConv.type === "dm" &&
      ((msg.sender_id === activeConv.id && msg.recipient_id === currentUserId) ||
       (msg.sender_id === currentUserId && msg.recipient_id === activeConv.id)));

  if (belongsToActive) renderMessage(msg);
});

socket.on("typing", (data) => {
  if (!activeConv) return;
  typingIndicator.textContent = `${data.username} is typing…`;
  clearTimeout(typingTimeout);
  typingTimeout = setTimeout(() => { typingIndicator.textContent = ""; }, 2000);
});

socket.on("presence", (data) => {
  const statusEl = document.querySelector(`.status-${data.user_id}`);
  if (statusEl) statusEl.textContent = data.is_online ? "online" : "offline";
});

// ---------- New group modal ----------

const groupModal = document.getElementById("groupModal");
document.getElementById("newGroupBtn").addEventListener("click", () => {
  groupModal.style.display = "flex";
});
document.getElementById("cancelGroupBtn").addEventListener("click", () => {
  groupModal.style.display = "none";
});
document.getElementById("createGroupBtn").addEventListener("click", async () => {
  const name = document.getElementById("groupNameInput").value.trim();
  if (!name) return;
  const memberIds = Array.from(
    document.querySelectorAll("#memberPicker input:checked")
  ).map((el) => parseInt(el.value));

  const res = await fetch("/api/groups", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, member_ids: memberIds }),
  });
  if (res.ok) {
    location.reload();
  } else {
    const data = await res.json();
    alert(data.error || "Could not create group");
  }
});
