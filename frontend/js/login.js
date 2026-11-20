/** Email login and registration for the standalone login page. */
(function () {
  "use strict";

  var loginForm = document.getElementById("login-form");
  var registerForm = document.getElementById("register-form");
  var email = document.getElementById("email");
  var password = document.getElementById("password");
  var toggle = document.getElementById("toggle-password");
  var loginSubmit = document.getElementById("login-submit");
  var registerSubmit = document.getElementById("register-submit");
  var errorBox = document.getElementById("login-error");
  var statusBox = document.getElementById("login-status");
  var nextInput = document.getElementById("login-next");
  var resendButton = document.getElementById("resend-verification");
  var tabs = Array.prototype.slice.call(document.querySelectorAll("[data-auth-mode]"));

  if (!loginForm || !registerForm || !email || !password || !loginSubmit || !errorBox) return;

  var params = new URLSearchParams(window.location.search);
  var requestedNext = params.get("next") || "/";
  if (nextInput) nextInput.value = requestedNext;

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
    statusBox.hidden = true;
  }

  function clearError() {
    errorBox.textContent = "";
    errorBox.hidden = true;
  }

  function showStatus(message) {
    statusBox.textContent = message;
    statusBox.hidden = false;
    errorBox.hidden = true;
  }

  function revealResend() {
    if (resendButton) resendButton.hidden = false;
  }

  function setMode(mode) {
    var isRegister = mode === "register";
    loginForm.hidden = isRegister;
    registerForm.hidden = !isRegister;
    tabs.forEach(function (tab) {
      var active = tab.getAttribute("data-auth-mode") === mode;
      tab.classList.toggle("is-active", active);
      tab.setAttribute("aria-selected", String(active));
    });
    clearError();
    if (isRegister) {
      document.getElementById("register-name").focus();
    } else {
      email.focus();
    }
  }

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      setMode(tab.getAttribute("data-auth-mode"));
    });
  });

  if (params.get("mode") === "register") setMode("register");
  if (params.get("verified") === "1") showStatus("邮箱验证成功，请使用新账户登录。");
  if (params.get("verified") === "0") {
    showError("验证链接无效或已过期，请重新发送验证邮件。");
    revealResend();
  }
  if (params.get("error") === "rate") showError("登录尝试过于频繁，请稍后再试。");
  if (params.get("error") === "service") showError("登录服务暂时不可用，请稍后再试。");
  if (params.get("error") === "invalid") showError("邮箱或密码错误，请重试。");
  if (params.get("error") === "unverified") {
    showError("请先完成邮箱验证，再登录账户。");
    revealResend();
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

  [email, password].forEach(function (input) {
    input.addEventListener("input", clearError);
  });

  async function parsePayload(response) {
    try {
      return await response.json();
    } catch (_) {
      return null;
    }
  }

  function errorMessage(payload, fallback) {
    return (payload && payload.error && payload.error.message) || fallback;
  }

  if (resendButton) {
    resendButton.addEventListener("click", async function () {
      clearError();
      var value = email.value.trim();
      if (!value) {
        showError("请先填写邮箱。");
        email.focus();
        return;
      }
      resendButton.disabled = true;
      try {
        var response = await fetch("/api/auth/resend-verification", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Accept": "application/json", "Content-Type": "application/json" },
          body: JSON.stringify({ email: value }),
        });
        var payload = await parsePayload(response);
        if (response.ok && payload && payload.ok) {
          showStatus("如果该邮箱正在等待验证，新的验证邮件已经发送。");
        } else {
          showError(errorMessage(payload, "验证邮件发送失败，请稍后重试。"));
        }
      } catch (_) {
        showError("无法连接 StudyFlow 服务，请稍后重试。");
      } finally {
        resendButton.disabled = false;
      }
    });
  }

  loginForm.addEventListener("submit", async function (event) {
    if (!window.fetch) return;
    event.preventDefault();
    clearError();
    resendButton.hidden = true;
    var emailValue = email.value.trim();
    var passwordValue = password.value;
    if (!emailValue || !passwordValue) {
      showError("请输入邮箱和密码。");
      (emailValue ? password : email).focus();
      return;
    }
    loginSubmit.disabled = true;
    loginSubmit.textContent = "正在登录…";
    try {
      var response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailValue, password: passwordValue, next: requestedNext }),
      });
      var payload = await parsePayload(response);
      if (response.ok && payload && payload.ok) {
        var destination = payload.data && payload.data.redirect ? payload.data.redirect : requestedNext;
        if (typeof destination !== "string" || destination.charAt(0) !== "/" || destination.indexOf("//") === 0) {
          destination = "/";
        }
        window.location.assign(destination);
        return;
      }
      var code = payload && payload.error && payload.error.code;
      if (response.status === 429) {
        showError("登录尝试过于频繁，请稍后再试。");
      } else if (code === "EMAIL_NOT_VERIFIED") {
        showError("请先完成邮箱验证，再登录账户。");
        resendButton.hidden = false;
      } else if (response.status === 401) {
        showError("邮箱或密码错误，请重试。");
      } else {
        showError(errorMessage(payload, "登录失败，请稍后重试。"));
      }
    } catch (_) {
      showError("无法连接 StudyFlow 服务，请稍后重试。");
    } finally {
      loginSubmit.disabled = false;
      loginSubmit.textContent = "登录";
      password.focus();
      password.select();
    }
  });

  registerForm.addEventListener("submit", async function (event) {
    event.preventDefault();
    clearError();
    var name = document.getElementById("register-name").value.trim();
    var emailValue = document.getElementById("register-email").value.trim();
    var passwordValue = document.getElementById("register-password").value;
    var confirmValue = document.getElementById("register-confirm").value;
    if (!emailValue) {
      showError("请输入邮箱。");
      document.getElementById("register-email").focus();
      return;
    }
    if (passwordValue.length < 12) {
      showError("密码至少需要 12 个字符。");
      document.getElementById("register-password").focus();
      return;
    }
    if (passwordValue !== confirmValue) {
      showError("两次输入的密码不一致。");
      document.getElementById("register-confirm").focus();
      return;
    }
    registerSubmit.disabled = true;
    registerSubmit.textContent = "正在创建…";
    try {
      var response = await fetch("/api/auth/register", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ email: emailValue, password: passwordValue, display_name: name }),
      });
      var payload = await parsePayload(response);
      if (response.ok && payload && payload.ok) {
        email.value = emailValue;
        setMode("login");
        showStatus("账户已创建。请查收邮箱中的验证链接，完成验证后即可登录。");
        resendButton.hidden = false;
        password.focus();
      } else if (payload && payload.error && payload.error.code === "EMAIL_DELIVERY_FAILED") {
        email.value = emailValue;
        setMode("login");
        showError(errorMessage(payload, "账户已创建，但验证邮件发送失败，请重新发送。"));
        revealResend();
      } else {
        showError(errorMessage(payload, "注册失败，请稍后重试。"));
      }
    } catch (_) {
      showError("无法连接 StudyFlow 服务，请稍后重试。");
    } finally {
      registerSubmit.disabled = false;
      registerSubmit.textContent = "创建账户";
    }
  });
})();
