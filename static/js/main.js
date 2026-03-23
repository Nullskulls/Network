(function () {
    var HEARTBEAT_INTERVAL = 8000;
    var ACTIVE_USERS_INTERVAL = 6000;
    var csrfToken = window.CSRF_TOKEN || "";

    var themeToggle = document.getElementById("themeToggle");
    if (themeToggle) {
        themeToggle.addEventListener("click", function () {
            var root = document.documentElement;
            var isDark = root.classList.toggle("dark");
            localStorage.setItem("darkMode", isDark ? "1" : "0");
        });
    }
    if (window.matchMedia && localStorage.getItem("darkMode") === null) {
        window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
            if (localStorage.getItem("darkMode") === null) {
                if (e.matches) document.documentElement.classList.add("dark");
                else document.documentElement.classList.remove("dark");
            }
        });
    }

    function scrollMessagesToBottom() {
        var container = document.querySelector(".messages-container");
        if (container) {
            requestAnimationFrame(function () {
                container.scrollTop = container.scrollHeight;
            });
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scrollMessagesToBottom);
    } else {
        requestAnimationFrame(scrollMessagesToBottom);
    }

    var sidebar = document.querySelector(".sidebar");
    var toggle = document.querySelector(".sidebar-toggle");
    if (toggle && sidebar) {
        toggle.addEventListener("click", function () {
            sidebar.classList.toggle("open");
        });
    }

    function ping() {
        fetch("/api/users/heartbeat", {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRF-Token": csrfToken }
        }).catch(function () {});
    }

    function loadActiveUsers() {
        fetch("/api/users/active", { credentials: "same-origin" })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var list = document.getElementById("dm-live-list");
                var title = document.getElementById("dm-live-title");
                if (!list) return;
                var users = data.users || [];
                list.innerHTML = "";
                if (users.length) {
                    if (title) title.style.display = "block";
                    users.forEach(function (u) {
                        var id = u.id;
                        var name = u.name || "?";
                        var avatarUrl = u.avatar_url;
                        var li = document.createElement("li");
                        li.className = "dm dm-live";
                        if (window.CURRENT_LIVE_DM_ID && id === window.CURRENT_LIVE_DM_ID) li.classList.add("active");
                        var a = document.createElement("a");
                        a.href = "/app/dm/live/" + encodeURIComponent(id);
                        a.className = "dm-name";
                        a.textContent = name;
                        var avatar = document.createElement(avatarUrl ? "img" : "span");
                        avatar.className = "dm-avatar dm-avatar-live" + (avatarUrl ? " dm-avatar-img" : " dm-avatar-initial");
                        if (avatarUrl) {
                            avatar.src = avatarUrl;
                            avatar.alt = "";
                        } else {
                            avatar.textContent = (name && name !== "?") ? name[0].toUpperCase() : "?";
                        }
                        li.appendChild(avatar);
                        li.appendChild(a);
                        list.appendChild(li);
                    });
                } else {
                    if (title) title.style.display = "none";
                }
            })
            .catch(function () {});
    }

    ping();
    loadActiveUsers();
    setInterval(ping, HEARTBEAT_INTERVAL);
    setInterval(loadActiveUsers, ACTIVE_USERS_INTERVAL);
})();
