// Support chat client. Message text is always inserted with textContent (never innerHTML).
(function () {
  var log = document.getElementById("chatLog");
  var form = document.getElementById("chatForm");
  var input = document.getElementById("chatInput");
  var sendBtn = document.getElementById("chatSend");
  if (!log || !form) return;

  var csrf = document.querySelector('meta[name="csrf-token"]').content;
  var chatUrl = log.dataset.chatUrl;
  var clearUrl = log.dataset.clearUrl;

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  function addMessage(role, text, opts) {
    opts = opts || {};
    var row = document.createElement("div");
    row.className = "msg " + role + (opts.crisis ? " crisis" : "") + (opts.typing ? " typing" : "");
    var bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.textContent = text;
    if (opts.actions && opts.actions.length) {
      var wrap = document.createElement("div");
      wrap.className = "msg-actions";
      opts.actions.forEach(function (a) {
        var link = document.createElement("a");
        link.className = "btn btn-sm " + (opts.crisis ? "btn-danger" : "btn-outline-primary");
        link.href = a.url;
        link.textContent = a.label;
        wrap.appendChild(link);
      });
      bubble.appendChild(wrap);
    }
    row.appendChild(bubble);
    log.appendChild(row);
    scrollDown();
    return row;
  }

  function send(text) {
    text = text.trim();
    if (!text) return;
    addMessage("user", text);
    input.value = "";
    sendBtn.disabled = true;
    var typing = addMessage("bot", "Typing...", { typing: true });

    fetch(chatUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: JSON.stringify({ message: text }),
    })
      .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
      .then(function (res) {
        typing.remove();
        if (!res.ok) {
          addMessage("bot", res.data.error || "Sorry, something went wrong. Please try again.");
          return;
        }
        addMessage("bot", res.data.reply, { crisis: res.data.crisis, actions: res.data.actions });
      })
      .catch(function () {
        typing.remove();
        addMessage("bot", "I couldn't reach the server. Please check your connection and try again.");
      })
      .finally(function () { sendBtn.disabled = false; input.focus(); });
  }

  form.addEventListener("submit", function (e) { e.preventDefault(); send(input.value); });

  document.querySelectorAll("[data-prompt]").forEach(function (btn) {
    btn.addEventListener("click", function () { send(btn.getAttribute("data-prompt")); });
  });

  document.getElementById("clearChat").addEventListener("click", function () {
    if (!window.confirm("Delete this conversation?")) return;
    fetch(clearUrl, { method: "POST", headers: { "X-CSRF-Token": csrf } }).then(function () {
      log.innerHTML = "";
      addMessage("bot", "Chat cleared. How are you feeling right now?");
    });
  });

  scrollDown();
})();
