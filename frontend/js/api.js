/**
 * Centralised REST client.
 * All pages use this module so headers, error shapes, uploads and timeouts are
 * handled in exactly one place.
 */

const API_BASE = (window.__STUDYFLOW_API_BASE__ || "/api").replace(/\/$/, "");
const DEFAULT_TIMEOUT_MS = 90000;

export class ApiError extends Error {
  constructor(message, { code = "UNKNOWN_ERROR", status = 0, details = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function buildUrl(path, query) {
  const url = path.startsWith("http")
    ? path
    : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  if (!query) return url;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  });
  const suffix = params.toString();
  return suffix ? `${url}${url.includes("?") ? "&" : "?"}${suffix}` : url;
}

/**
 * @param {string} path
 * @param {object} options
 * @returns {Promise<object>} the whole response envelope ({ok,data,ai?,message?})
 */
export async function request(
  path,
  {
    method = "GET",
    body = undefined,
    query = undefined,
    signal = undefined,
    timeout = DEFAULT_TIMEOUT_MS,
    formData = false,
  } = {}
) {
  const url = buildUrl(path, query);
  const controller = new AbortController();
  let timedOut = false;
  const timer = timeout
    ? window.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeout)
    : null;

  const onExternalAbort = () => controller.abort();
  if (signal) {
    if (signal.aborted) controller.abort();
    else signal.addEventListener("abort", onExternalAbort, { once: true });
  }

  const headers = { Accept: "application/json" };
  let payload = body;
  if (body !== undefined && !formData) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  try {
    const response = await fetch(url, {
      method,
      headers,
      body: payload,
      signal: controller.signal,
      credentials: "same-origin",
    });
    const text = await response.text();
    let parsed = null;
    if (text) {
      try {
        parsed = JSON.parse(text);
      } catch {
        if (!response.ok) {
          throw new ApiError(`服务器返回了非 JSON 响应（HTTP ${response.status}）`, {
            code: "INVALID_RESPONSE",
            status: response.status,
          });
        }
      }
    }
    if (!response.ok || (parsed && parsed.ok === false)) {
      const upstream = parsed && parsed.error ? parsed.error : {};
      throw new ApiError(
        upstream.message || `请求失败（HTTP ${response.status}）`,
        {
          code: upstream.code || "HTTP_ERROR",
          status: response.status,
          details: upstream.details || null,
        }
      );
    }
    if (!parsed) {
      throw new ApiError("服务器返回了空响应", { code: "EMPTY_RESPONSE", status: response.status });
    }
    return parsed;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error && error.name === "AbortError") {
      if (timedOut) {
        throw new ApiError("请求超时，请检查网络或稍后重试", {
          code: "TIMEOUT",
          status: 0,
        });
      }
      throw error;
    }
    throw new ApiError("无法连接到 StudyFlow 服务，请确认 Flask 后端正在运行", {
      code: "NETWORK_ERROR",
      status: 0,
    });
  } finally {
    if (timer) window.clearTimeout(timer);
    if (signal) signal.removeEventListener("abort", onExternalAbort);
  }
}

export const api = {
  get(path, query, options = {}) {
    return request(path, { ...options, method: "GET", query });
  },
  post(path, body = {}, options = {}) {
    return request(path, { ...options, method: "POST", body });
  },
  put(path, body = {}, options = {}) {
    return request(path, { ...options, method: "PUT", body });
  },
  patch(path, body = {}, options = {}) {
    return request(path, { ...options, method: "PATCH", body });
  },
  delete(path, options = {}) {
    return request(path, { ...options, method: "DELETE" });
  },
  async upload(file, { field = "image", signal } = {}) {
    const form = new FormData();
    form.append(field, file);
    return request("/uploads", {
      method: "POST",
      body: form,
      formData: true,
      signal,
      timeout: 45000,
    });
  },
};

export function isAbortError(error) {
  return Boolean(error && error.name === "AbortError");
}
