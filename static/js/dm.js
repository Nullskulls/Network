(function () {
    var userId = window.DM_USER_ID;
    var currentUser = window.CURRENT_USER || "You";
    var messagesEl = document.getElementById("dm-messages");
    var form = document.getElementById("dm-form");
    var input = document.getElementById("dm-input");
    var csrfToken = window.CSRF_TOKEN || "";

    if (!userId || !form) return;

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

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        var text = (input && input.value || "").trim();
        if (!text) return;
        input.value = "";
        fetch("/api/dm/" + encodeURIComponent(userId), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken
            },
            credentials: "same-origin",
            body: JSON.stringify({ message: text })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.message) {
                    addMessage(data.message.from, data.message.message);
                }
            });
    });
})();
