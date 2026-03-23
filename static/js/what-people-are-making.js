(function () {
    var messagesContainer = document.querySelector(".messages-container");
    if (messagesContainer) {
        function scrollToBottom() {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        scrollToBottom();
        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", scrollToBottom);
        }
        window.addEventListener("load", scrollToBottom);
    }

    var modal = document.getElementById("makingModal");
    var backdrop = document.getElementById("makingModalBackdrop");
    var form = document.getElementById("makingForm");
    var submitBtn = document.getElementById("makingSubmitBtn");
    var cancelBtn = document.getElementById("makingCancelBtn");
    var messageEl = document.getElementById("makingFormMessage");
    var submitUrl = window.MAKING_SUBMIT_URL;
    var csrfToken = window.CSRF_TOKEN || "";

    function openModal() {
        if (modal) modal.removeAttribute("hidden");
    }

    function closeModal() {
        if (modal) modal.setAttribute("hidden", "");
        if (messageEl) {
            messageEl.textContent = "";
            messageEl.className = "making-form-message";
        }
    }

    function showMessage(text, isError) {
        if (!messageEl) return;
        messageEl.textContent = text;
        messageEl.className = "making-form-message " + (isError ? "error" : "success");
    }

    if (submitBtn) submitBtn.addEventListener("click", openModal);
    if (cancelBtn) cancelBtn.addEventListener("click", closeModal);
    if (backdrop) backdrop.addEventListener("click", closeModal);

    var fileInput = document.getElementById("makingScreenshot");
    var fileNameEl = document.getElementById("makingFileName");
    if (fileInput && fileNameEl) {
        fileInput.addEventListener("change", function () {
            fileNameEl.textContent = fileInput.files.length && fileInput.files[0].name ? fileInput.files[0].name : "No file chosen";
        });
    }

    function setLoading(loading) {
        if (!messageEl) return;
        if (loading) {
            messageEl.textContent = "Uploading…";
            messageEl.className = "making-form-message making-form-message-loading";
        } else {
            messageEl.classList.remove("making-form-message-loading");
        }
    }

    if (form && submitUrl) {
        form.addEventListener("submit", function (e) {
            e.preventDefault();
            var btn = form.querySelector('button[type="submit"]');
            if (btn) btn.disabled = true;
            setLoading(true);

            var fd = new FormData(form);

            fetch(submitUrl, {
                method: "POST",
                body: fd,
                credentials: "same-origin",
                headers: { "X-CSRF-Token": csrfToken }
            })
                .then(function (res) {
                    var ct = res.headers.get("Content-Type") || "";
                    if (ct.indexOf("application/json") !== 0) {
                        return res.text().then(function (text) {
                            throw new Error(text || "Server returned non-JSON. Try again.");
                        });
                    }
                    return res.json().then(function (data) {
                        if (!res.ok) {
                            var msg = data.error || "Something went wrong";
                            if (data.detail) msg += " (" + data.detail + ")";
                            throw new Error(msg);
                        }
                        return data;
                    });
                })
                .then(function (data) {
                    setLoading(false);
                    showMessage(data.message || "Submitted! You'll get stickers once it's approved.", false);
                    form.reset();
                    if (fileNameEl) fileNameEl.textContent = "No file chosen";
                    setTimeout(closeModal, 3000);
                })
                .catch(function (err) {
                    setLoading(false);
                    showMessage(err.message || "Failed to submit. Try again.", true);
                })
                .finally(function () {
                    if (btn) btn.disabled = false;
                });
        });
    }
})();
