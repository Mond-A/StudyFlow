/** Standalone admin login page. No SPA modules are needed here. */
(function () {
  "use strict";

  var form = document.getElementById("login-form");
  var password = document.getElementById("password");
  var toggle = document.getElementById("toggle-password");
  var submit = document.getElementById("login-submit");
  var errorBox = document.getElementById("login-error");
  var nextInput = document.getElementById("login-next");

  if (!form || !password || !submit || !errorBox) return;

  var params = new URLSearchParams(window.location.search);
  var requestedNext = params.get("next") || "/";
  if (nextInput) nextInput.value = requestedNext;

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  function clearError() {
    errorBox.textContent = "";
    errorBox.hidden = true;
  }

  if (params.get("error") === "rate") {
    showError("登录尝试过于频繁，请稍后再试。");
  } else if (params.get("error") === "invalid") {
    showError("密码错误，请重试。");
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      var revealing = password.type === "password";
      password.type = revealing ? "text" : "password";
      toggle.textContent = revealing ? "隐藏" : "显示";
      toggle.setAttribute("aria-pressed", String(revealing));
      password.focus();
    });
  }

  password.addEventListener("input", clearError);

  form.addEventListener("submit", async function (event) {
    // The native POST /login path remains a no-JS fallback. With JS enabled,
    // the JSON auth endpoint gives us explicit 401/429 feedback.
    if (!window.fetch) return;
    event.preventDefault();
    clearError();

    var value = password.value;
    if (!value) {
      showError("请输入管理员密码。");
      password.focus();
      return;
    }

    submit.disabled = true;
    submit.textContent = "正在登录…";

    try {
      var response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Accept": "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password: value, next: requestedNext }),
      });
      var payload = await response.json().catch(function () { return null; });

      if (response.ok && payload && payload.ok) {
        var destination = payload.data && payload.data.redirect ? payload.data.redirect : requestedNext;
        if (typeof destination !== "string" || destination.charAt(0) !== "/" || destination.indexOf("//") === 0) {
          destination = "/";
        }
        window.location.assign(destination);
        return;
      }

      if (response.status === 429) {
        showError("登录尝试过于频繁，请稍后再试。");
      } else if (response.status === 401) {
        showError("密码错误，请重试。");
      } else {
        showError(
          (payload && payload.error && payload.error.message) ||
          "登录失败，请稍后重试。"
        );
      }
    } catch (_) {
      showError("无法连接 StudyFlow 服务，请稍后重试。");
    } finally {
      submit.disabled = false;
      submit.textContent = "登录";
      password.focus();
      password.select();
    }
  });
})();
