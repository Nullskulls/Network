(function () {
    var rawReplies = window.NETWORK_REPLIES || [];
    var firstQuestionOptions = window.NETWORK_FIRST_QUESTION_OPTIONS || [];
    var user = window.CURRENT_USER || "You";
    var pool = [];
    rawReplies.forEach(function (r) {
        (r.questions || []).forEach(function (q) {
            pool.push({ question: q, reply: r.reply });
        });
    });
    var replyArea = document.getElementById("network-reply-area");
    var conversation = document.getElementById("network-conversation");
    var messagesContainer = document.querySelector(".messages-container");

    function pickRandom(arr, n) {
        var copy = arr.slice();
        var out = [];
        n = Math.min(n, copy.length);
        while (out.length < n && copy.length) {
            var i = Math.floor(Math.random() * copy.length);
            out.push(copy.splice(i, 1)[0]);
        }
        return out;
    }

    function scrollToBottom() {
        if (!messagesContainer) return;
        requestAnimationFrame(function () {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        });
    }

    function showReplyButtons(choices) {
        if (!choices.length) return;
        replyArea.style.display = "";
        replyArea.innerHTML = "";
        var wrap = document.createElement("div");
        wrap.className = "network-reply-buttons network-reply-buttons-reveal";
        choices.forEach(function (item) {
            var btn = document.createElement("button");
            btn.type = "button";
            btn.className = "network-reply-btn";
            btn.textContent = item.question;
            btn.addEventListener("click", function () {
                var question = item.question;
                var reply = item.reply;
                replyArea.innerHTML = "";
                replyArea.style.display = "none";
                addMessage(user, question, "you");
                setTimeout(function () {
                    scrollToBottom();
                    addMessage("Orpheus", reply, "orpheus");
                    pool = pool.filter(function (r) { return r.question !== question; });
                    var next = pickRandom(pool, 4);
                    setTimeout(function () {
                        if (next.length) {
                            showReplyButtons(next);
                        }
                        scrollToBottom();
                    }, 1500);
                }, 1500);
            });
            wrap.appendChild(btn);
        });
        replyArea.appendChild(wrap);
        requestAnimationFrame(function () {
            requestAnimationFrame(function () {
                wrap.classList.add("revealed");
            });
        });
        scrollToBottom();
    }

    function addMessage(sender, text, role) {
        var wrap = document.createElement("div");
        wrap.className = "message-wrapper message-reveal " + role;
        var msg = document.createElement("div");
        msg.className = "message";
        var body = document.createElement("div");
        body.className = "message-body";
        var span = document.createElement("span");
        span.className = "message-sender";
        span.textContent = sender;
        var p = document.createElement("p");
        p.className = "message-text";
        p.textContent = text;
        body.appendChild(span);
        body.appendChild(p);
        msg.appendChild(body);
        wrap.appendChild(msg);
        conversation.appendChild(wrap);
        scrollToBottom();
        setTimeout(function () {
            wrap.classList.add("revealed");
            scrollToBottom();
        }, 1000);
    }

    var initial = firstQuestionOptions.length ? firstQuestionOptions : pickRandom(pool, 4);
    if (initial.length) {
        showReplyButtons(initial);
    }
    requestAnimationFrame(function () {
        scrollToBottom();
    });
})();
