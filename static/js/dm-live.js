(function () {
    var otherId = window.DM_OTHER_ID;
    var otherName = window.DM_OTHER_NAME;
    var currentUser = window.CURRENT_USER || "You";
    var messagesEl = document.getElementById("dm-messages");
    var containerEl = document.getElementById("dm-messages-container");
    var form = document.getElementById("dm-form");
    var input = document.getElementById("dm-input");

    if (!otherId || !form || !messagesEl) return;

    function scrollToBottom() {
        if (!containerEl) return;
        requestAnimationFrame(function () {
            containerEl.scrollTop = containerEl.scrollHeight;
            var last = messagesEl.lastElementChild;
            if (last) last.scrollIntoView({ block: "end", behavior: "auto" });
        });
    }

    function addMessage(from, text) {
        var wrap = document.createElement("div");
        wrap.className = "message-wrapper " + (from === currentUser ? "you" : "orpheus");
        var msg = document.createElement("div");
        msg.className = "message visible";
        var body = document.createElement("div");
        body.className = "message-body";
        var span = document.createElement("span");
        span.className = "message-sender";
        span.textContent = from;
        var p = document.createElement("p");
        p.className = "message-text";
        p.textContent = text;
        body.appendChild(span);
        body.appendChild(p);
        msg.appendChild(body);
        wrap.appendChild(msg);
        messagesEl.appendChild(wrap);
    }

    function loadMessages() {
        fetch("/api/dm/live/" + encodeURIComponent(otherId))
            .then(function (r) { return r.json(); })
            .then(function (data) {
                messagesEl.innerHTML = "";
                (data.messages || []).forEach(function (m) {
                    addMessage(m.from, m.message);
                });
                scrollToBottom();
            });
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        var text = (input && input.value || "").trim();
        if (!text) return;
        input.value = "";
        fetch("/api/dm/live/" + encodeURIComponent(otherId), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: text })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.message) {
                    addMessage(data.message.from, data.message.message);
                    scrollToBottom();
                }
            });
    });

    loadMessages();
    setInterval(loadMessages, 2000);
})();
