/**
 * app.js —— 聊天室前端的全部逻辑（原生 JavaScript，无框架、无构建）。
 *
 * 主流程：
 *   登录 → 拉用户列表 / 会话列表 → 进入会话 → 拉最近消息
 *        → 每 2 秒轮询新消息 → 发送消息
 *
 * 收消息用轮询而不是 WebSocket：实现最简单，代价是固定的 2 秒延迟。
 */

// 后端地址。分两类入口：
//   1) 5173 是专门的前端端口（本机另开的那个前端窗口）→ 页面和接口不同源，要显式指向后端的 8000；
//   2) 其他任何入口（后端 8000、局域网的 http://192.168.x.x:8000、内网穿透的 https://xxx 域名），
//      页面都是后端发出来的 → 留空走相对路径：同源不会触发跨域，
//      https 页面也不会去请求 http 接口（浏览器会直接拦掉那种混合内容）。
const API_BASE = location.port === "5173" ? "http://" + location.hostname + ":8000" : "";

// 轮询间隔（毫秒）。PRD 要求新消息 2 秒内可见，所以取 2000。
const POLL_INTERVAL = 2000;

// 断线后最长等多久再重试一次（退避重试的上限）
const MAX_RETRY_DELAY = 10000;

// ==================== 全局状态 ====================
let token = localStorage.getItem("token") || "";
let me = JSON.parse(localStorage.getItem("user") || "null");
let currentConversation = null;  // 当前打开的会话 { id, peer }
let lastMessageId = 0;           // 轮询游标：已经收到的最大消息 id
let pollTimer = null;            // setTimeout 的编号，用来取消下一次轮询
let failedCount = 0;             // 连续失败次数，决定下次退避多久
let wantPolling = false;         // 用户是否希望自动刷新（切到后台时临时暂停）

// ==================== 页面元素 ====================
const el = (id) => document.getElementById(id);
const statusBar = el("status");
const loginView = el("login-view");
const chatView = el("chat-view");
const loginHint = el("login-hint");
const notice = el("notice");
const userList = el("user-list");
const conversationList = el("conversation-list");
const messageList = el("message-list");
const chatTitle = el("chat-title");
const inputBox = el("input");
const sendButton = el("btn-send");

// ==================== 一、和后端通信 ====================

/**
 * 统一的后端请求函数：自动带上登录 token，并把响应解析成 JSON。
 * 失败时抛出的异常带 status 字段，调用方据此区分三种情况：
 *   status === 401 -> 登录过期，要重新登录
 *   status === 其他数字 -> 业务错误，把 detail 显示给用户
 *   status === undefined -> fetch 本身失败，即后端没启动或网络断了
 */
async function api(path, { method = "GET", body = null } = {}) {
  const options = { method, headers: {} };
  if (token) options.headers.Authorization = "Bearer " + token;
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(API_BASE + path, options);
  } catch (fetchError) {
    throw new Error("连不上后端（" + API_BASE + "），请确认后端已启动");
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const error = new Error(data.detail || "请求失败（HTTP " + response.status + "）");
    error.status = response.status;
    throw error;
  }
  return response.json();
}

/** 把「通 / 不通」反映到顶部状态条上 */
function setOnline(online) {
  statusBar.textContent = online ? "已连接" : "断线重连中…";
  statusBar.className = "status " + (online ? "online" : "offline");
}

/** 统一的错误处理：401 要求重新登录，连不上后端则标记为断线 */
function handleError(error, prefix) {
  if (error.status === 401) {
    handle401();
    return;
  }
  if (error.status === undefined) setOnline(false);
  notice.textContent = prefix + "：" + error.message;
}

// ==================== 二、登录 / 注册 / 退出 ====================

/** 保存登录态。放在 localStorage 里，刷新页面后还能自动恢复 */
function saveLogin(newToken, user) {
  token = newToken;
  me = user;
  localStorage.setItem("token", token);
  localStorage.setItem("user", JSON.stringify(user));
}

/** 清空登录态与聊天状态 */
function clearLogin() {
  token = "";
  me = null;
  currentConversation = null;
  lastMessageId = 0;
  localStorage.removeItem("token");
  localStorage.removeItem("user");
  stopPolling();
  wantPolling = false;
}

/** mode 取 "login" 或 "register"：两个接口的请求体略有不同 */
async function loginOrRegister(mode) {
  const username = el("username").value.trim();
  const password = el("password").value;
  const nickname = el("nickname").value.trim();

  if (username.length < 2) {
    loginHint.textContent = "登录名至少 2 个字符";
    return;
  }
  if (!password) {
    loginHint.textContent = "请输入密码";
    return;
  }
  if (mode === "register" && password.length < 6) {
    loginHint.textContent = "密码至少 6 位";
    return;
  }

  const isRegister = mode === "register";
  loginHint.textContent = "请求中…";
  try {
    const data = await api(isRegister ? "/api/auth/register" : "/api/auth/login", {
      method: "POST",
      body: isRegister ? { username, password, nickname: nickname || null } : { username, password },
    });
    saveLogin(data.token, data.user);
    loginHint.textContent = "";
    enterChatView();
  } catch (error) {
    loginHint.textContent = error.message;
  }
}

/** 页面打开时调用：如果本地有 token，就问后端「这通行证还有效吗」 */
async function restoreLogin() {
  if (!token) return false;
  try {
    saveLogin(token, await api("/api/auth/me"));
    return true;
  } catch (error) {
    clearLogin();
    return false;
  }
}

function logout() {
  clearLogin();
  showLoginView("已退出登录。");
}

/** 进入聊天页：显示左栏、清空消息区，然后拉用户和会话 */
function enterChatView() {
  loginView.classList.add("hidden");
  chatView.classList.remove("hidden");
  el("me-name").textContent = me.nickname + "（" + me.username + "）";
  messageList.replaceChildren();
  chatTitle.textContent = "请从左侧选择一个聊天对象";
  notice.textContent = "";
  inputBox.value = "";
  sendButton.disabled = true;
  loadUsers();
  loadConversations();
}

function showLoginView(hintText) {
  chatView.classList.add("hidden");
  loginView.classList.remove("hidden");
  loginHint.textContent = hintText || "";
}

/** 任何接口返回 401 都走这里：登录失效，回登录页 */
function handle401() {
  clearLogin();
  showLoginView("登录已过期，请重新登录。");
}

// ==================== 三、左栏：用户列表 / 会话列表 ====================

/** 生成一行灰色提示，列表为空时用 */
function emptyHint(text) {
  const div = document.createElement("div");
  div.className = "empty";
  div.textContent = text;
  return div;
}

/** 拉所有用户（后端已排除我自己），点一个就开始聊天 */
async function loadUsers() {
  try {
    const users = await api("/api/users");
    userList.replaceChildren();
    if (users.length === 0) {
      userList.append(emptyHint("还没有其他用户，用另一个浏览器注册一个账号试试。"));
    }
    for (const user of users) {
      const item = document.createElement("div");
      item.className = "item";
      item.textContent = user.nickname + "（" + user.username + "）";
      item.onclick = () => openConversation(user.id);
      userList.append(item);
    }
    setOnline(true);
  } catch (error) {
    handleError(error, "拉用户列表失败");
  }
}

/** 拉我的会话列表，最近聊过的排最前面（后端已按 last_message_at 倒序） */
async function loadConversations() {
  try {
    const conversations = await api("/api/conversations");
    conversationList.replaceChildren();
    if (conversations.length === 0) {
      conversationList.append(emptyHint("还没有会话，点下边的人开始聊天。"));
    }
    for (const conversation of conversations) {
      const item = document.createElement("div");
      const active = currentConversation && currentConversation.id === conversation.id;
      item.className = "item" + (active ? " active" : "");

      const peer = document.createElement("div");
      peer.className = "peer";
      peer.textContent = conversation.peer.nickname;

      const preview = document.createElement("div");
      preview.className = "preview";
      preview.textContent = conversation.last_message || "还没有消息";

      item.append(peer, preview);
      item.onclick = () => enterConversation(conversation.id, conversation.peer);
      conversationList.append(item);
    }
  } catch (error) {
    handleError(error, "拉会话列表失败");
  }
}

// ==================== 四、右栏：聊天窗口 ====================

/** 点左栏的用户：先让后端给出「我和他」的会话（已聊过就直接复用），再进去 */
async function openConversation(peerId) {
  try {
    const conversation = await api("/api/conversations", {
      method: "POST",
      body: { peer_id: peerId },
    });
    await enterConversation(conversation.id, conversation.peer);
  } catch (error) {
    handleError(error, "建立会话失败");
  }
}

/** 进入会话：换标题、清空气泡、重置游标，然后拉历史消息并开始轮询 */
async function enterConversation(conversationId, peer) {
  currentConversation = { id: conversationId, peer: peer };
  lastMessageId = 0;
  messageList.replaceChildren();
  chatTitle.textContent = "与 " + peer.nickname + " 聊天";
  notice.textContent = "";
  sendButton.disabled = false;

  // 手机端是上下布局，点完人要把聊天区滚到眼前
  if (window.innerWidth <= 768) chatTitle.scrollIntoView({ behavior: "smooth" });

  await loadMessages();
  startPolling();
  loadConversations();   // 刷新左栏，顺便把当前会话标成选中状态
}

/** 首屏：after_id=0 表示「我要最近的一批消息」 */
async function loadMessages() {
  try {
    const messages = await api(messagesUrl(0));
    for (const message of messages) addBubble(message);
    setOnline(true);
  } catch (error) {
    handleError(error, "拉历史消息失败");
  }
}

/** 轮询：只要比游标更新的消息 */
async function fetchNewMessages() {
  const messages = await api(messagesUrl(lastMessageId));
  for (const message of messages) addBubble(message);
}

/** 消息接口的地址：拉消息要带游标 after_id，发消息不带 */
function messagesUrl(afterId) {
  const base = "/api/conversations/" + currentConversation.id + "/messages";
  return afterId === null ? base : base + "?after_id=" + afterId;
}

/** 生成一个随机串，作为 client_msg_id（防止重复提交）传给后端 */
function randomId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

/** 画一个消息气泡：自己发的靠右（绿色），别人发的靠左（白色） */
function addBubble(message) {
  if (message.id <= lastMessageId) return;   // 兜底去重，同一句话不会画两遍

  const bubble = document.createElement("div");
  bubble.className = "bubble " + (message.sender_id === me.id ? "mine" : "theirs");

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = message.sender_nickname + " · " + formatTime(message.created_at);

  const text = document.createElement("div");
  text.className = "text";
  text.textContent = message.content;   // 用 textContent 而不是 innerHTML，避免消息里的标签被执行

  bubble.append(meta, text);
  messageList.append(bubble);

  lastMessageId = message.id;                          // 游标往前走
  messageList.scrollTop = messageList.scrollHeight;    // 自动滚到底部
}

/** 后端给的是 UTC 时间（如 2026-10-07T08:12:33.123456），补上 Z 再按本地时间显示 */
function formatTime(utcText) {
  const date = new Date(utcText + "Z");
  return date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

// ==================== 五、自动收新消息（轮询） ====================

function startPolling() {
  wantPolling = true;
  failedCount = 0;
  scheduleNextPoll(0);   // 立刻先拉一次，不让用户干等 2 秒
}

/** 用 setTimeout 而不是 setInterval：这样才能在断线时改下一次的间隔（退避重试） */
function scheduleNextPoll(delay) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(pollOnce, delay);
}

function stopPolling() {
  clearTimeout(pollTimer);
  pollTimer = null;
}

/**
 * 一次轮询。
 *  成功 -> 状态条显示「已连接」，2 秒后再来
 *  失败 -> 状态条显示「断线重连中…」，按 2s、4s、8s… 逐步拉长间隔重试（最多 10 秒）
 */
async function pollOnce() {
  if (!currentConversation) return;
  try {
    await fetchNewMessages();
    failedCount = 0;
    setOnline(true);
    scheduleNextPoll(POLL_INTERVAL);
  } catch (error) {
    if (error.status === 401) {
      handle401();   // 登录都失效了，再问下去只会一路 401
      return;
    }
    failedCount += 1;
    setOnline(false);
    scheduleNextPoll(Math.min(POLL_INTERVAL * 2 ** failedCount, MAX_RETRY_DELAY));
  }
}

// ==================== 六、发送消息 ====================

async function sendMessage() {
  if (!currentConversation) {
    notice.textContent = "请先从左侧选择一个聊天对象。";
    return;
  }
  const content = inputBox.value.trim();
  if (!content) return;

  sendButton.disabled = true;
  try {
    const message = await api(messagesUrl(null), {
      method: "POST",
      // client_msg_id 每次都不同；网络抖动导致重复提交时，后端靠它只存一条
      body: { content, client_msg_id: randomId() },
    });
    addBubble(message);
    inputBox.value = "";
    setOnline(true);
    loadConversations();
  } catch (error) {
    handleError(error, "发送失败");
  } finally {
    sendButton.disabled = false;
    inputBox.focus();
  }
}

// ==================== 七、事件绑定 ====================

el("btn-login").onclick = () => loginOrRegister("login");
el("btn-register").onclick = () => loginOrRegister("register");
el("btn-logout").onclick = logout;
el("btn-refresh-users").onclick = loadUsers;
sendButton.onclick = sendMessage;

// 密码框里按回车 = 登录
el("password").addEventListener("keydown", (event) => {
  if (event.key === "Enter") loginOrRegister("login");
});

// 输入框里按回车 = 发送，Shift + 回车 = 换行
inputBox.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
});

// 浏览器自己就知道网络通不通，可以立刻反映到状态条
window.addEventListener("offline", () => setOnline(false));
window.addEventListener("online", () => {
  setOnline(true);
  if (currentConversation && wantPolling) scheduleNextPoll(0);
});

// 切到后台暂停轮询（浏览器会限速，不如自己停干净），切回来立刻补拉一次
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopPolling();
  } else if (currentConversation && wantPolling) {
    failedCount = 0;
    scheduleNextPoll(0);
  }
});

// ==================== 八、页面启动 ====================

(async function start() {
  if (await restoreLogin()) {
    enterChatView();
  } else {
    showLoginView("");
  }
})();
