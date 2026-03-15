(function () {
    var container = document.getElementById("faq-messages");
    var messagesContainer = document.querySelector(".messages-container");
    var extraEl = document.getElementById("faq-extra-messages");
    var replyArea = document.getElementById("faq-reply-area");
    var buttons = document.getElementById("faq-buttons");

    var REVEAL_DELAY_MS = 400;
    var REVEAL_TRANSITION_MS = 500;
    var extraRenderedCount = 0;

    function scrollToBottom() {
        if (messagesContainer) messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    function revealReplyArea() {
        if (replyArea) replyArea.classList.remove("faq-reply-area-hidden");
        scrollToBottom();
    }

    function staggerRevealMessages(wrappers, onComplete) {
        if (!wrappers.length) {
            if (onComplete) onComplete();
            return;
        }
        wrappers.forEach(function (wrap, i) {
            setTimeout(function () {
                wrap.classList.add("revealed");
            }, i * REVEAL_DELAY_MS);
        });
        var totalMs = wrappers.length * REVEAL_DELAY_MS + REVEAL_TRANSITION_MS;
        if (onComplete) setTimeout(onComplete, totalMs);
    }

    function runInitialReveal() {
        var wrappers = [];
        if (container) {
            var children = container.querySelectorAll(".message-wrapper.message-reveal");
            for (var i = 0; i < children.length; i++) {
                if (!extraEl || !extraEl.contains(children[i])) wrappers.push(children[i]);
            }
        }
        staggerRevealMessages(wrappers, revealReplyArea);
    }

    function drawMessage(m) {
        var wrap = document.createElement("div");
        wrap.className = "message-wrapper message-reveal " + (m.from === "Heidi" ? "orpheus" : "you");
        var msg = document.createElement("div");
        msg.className = "message";
        var body = document.createElement("div");
        body.className = "message-body";
        var span = document.createElement("span");
        span.className = "message-sender";
        span.textContent = m.from;
        var p = document.createElement("p");
        p.className = "message-text";
        p.textContent = m.message;
        body.appendChild(span);
        body.appendChild(p);
        msg.appendChild(body);
        wrap.appendChild(msg);
        return wrap;
    }

    function loadExtra() {
        fetch("/api/network-faq/extra", { credentials: "same-origin" })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (!extraEl) return;
                var messages = data.messages || [];
                var newMessages = messages.slice(extraRenderedCount);
                var wrappers = [];
                newMessages.forEach(function (m) {
                    var w = drawMessage(m);
                    extraEl.appendChild(w);
                    wrappers.push(w);
                });
                extraRenderedCount = messages.length;
                staggerRevealMessages(wrappers, scrollToBottom);
            })
            .catch(function () {});
    }

    if (buttons) {
        buttons.addEventListener("click", function (e) {
            var btn = e.target.closest(".faq-question-btn");
            if (!btn) return;
            var question = btn.getAttribute("data-question");
            var reply = btn.getAttribute("data-reply");
            if (!question) return;
            fetch("/api/network-faq", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: question, reply: reply || "" }),
                credentials: "same-origin"
            })
                .then(function (r) {
                    if (r.ok) loadExtra();
                    else return r.json().then(function (d) { throw new Error(d.error || "Request failed"); });
                })
                .catch(function (err) {
                    if (extraEl) {
                        extraEl.appendChild(drawMessage({ from: "System", message: "Could not send: " + (err.message || "Try again") + "." }));
                    }
                });
        });
    }

    runInitialReveal();
    loadExtra();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", runInitialReveal);
    }
    window.addEventListener("load", function () {
        scrollToBottom();
    });
})();
