/** Reusable image drop zone with client-side preview and validation. */

import { icon, refreshIcons } from "./icons.js";
import { formatFileSize } from "../ui.js";
import { toastError } from "./toast.js";

const ACCEPTED = ["image/jpeg", "image/png", "image/webp"];
const MAX_BYTES = 8 * 1024 * 1024;

export function createImageUploader({
  label = "上传图片",
  hint = "支持 JPG / PNG / WebP，最大 8 MB",
  onChange = () => {},
  compact = false,
} = {}) {
  const root = document.createElement("div");
  root.className = `image-uploader ${compact ? "image-uploader-compact" : ""}`;
  root.innerHTML = `
    <input type="file" accept="image/jpeg,image/png,image/webp" hidden aria-label="${label}">
    <div class="upload-dropzone" role="button" tabindex="0" aria-label="${label}">
      <div class="upload-empty">
        <span class="upload-icon">${icon("image-plus")}</span>
        <strong>${label}</strong>
        <span>${hint}</span>
        <span class="upload-link">点击选择或拖拽图片到这里</span>
      </div>
      <div class="upload-preview" hidden>
        <img alt="已选择的图片预览">
        <div class="upload-preview-meta">
          <span class="upload-filename"></span>
          <span class="upload-filesize"></span>
        </div>
        <button type="button" class="btn btn-secondary btn-sm upload-remove">${icon("rotate-ccw")}<span>重新选择</span></button>
      </div>
    </div>
    <p class="field-hint upload-error" role="alert" hidden></p>
  `;
  const input = root.querySelector("input[type=file]");
  const dropzone = root.querySelector(".upload-dropzone");
  const empty = root.querySelector(".upload-empty");
  const preview = root.querySelector(".upload-preview");
  const image = root.querySelector("img");
  const filename = root.querySelector(".upload-filename");
  const filesize = root.querySelector(".upload-filesize");
  const errorEl = root.querySelector(".upload-error");
  let selected = null;
  let objectUrl = null;

  function showError(message) {
    errorEl.textContent = message;
    errorEl.hidden = !message;
  }

  function clear() {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    selected = null;
    input.value = "";
    image.removeAttribute("src");
    preview.hidden = true;
    empty.hidden = false;
    showError("");
    onChange(null);
  }

  function choose(file) {
    if (!file) return;
    if (!ACCEPTED.includes(file.type)) {
      toastError(new Error("仅支持 JPG、PNG、WebP 图片"));
      return;
    }
    if (file.size > MAX_BYTES) {
      toastError(new Error("图片超过 8 MB，请压缩后重试"));
      return;
    }
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    selected = file;
    objectUrl = URL.createObjectURL(file);
    image.src = objectUrl;
    filename.textContent = file.name;
    filesize.textContent = formatFileSize(file.size);
    preview.hidden = false;
    empty.hidden = true;
    showError("");
    onChange(file);
    refreshIcons(root);
  }

  input.addEventListener("change", () => choose(input.files && input.files[0]));
  dropzone.addEventListener("click", (event) => {
    if (event.target.closest(".upload-remove")) return;
    if (event.target.closest("button") && !event.target.closest(".upload-remove")) return;
    input.click();
  });
  dropzone.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      input.click();
    }
  });
  root.querySelector(".upload-remove").addEventListener("click", (event) => {
    event.stopPropagation();
    input.click();
  });
  ["dragenter", "dragover"].forEach((type) => {
    dropzone.addEventListener(type, (event) => {
      event.preventDefault();
      dropzone.classList.add("is-dragover");
    });
  });
  ["dragleave", "drop"].forEach((type) => {
    dropzone.addEventListener(type, (event) => {
      event.preventDefault();
      dropzone.classList.remove("is-dragover");
    });
  });
  dropzone.addEventListener("drop", (event) => {
    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    choose(file);
  });

  refreshIcons(root);
  return {
    el: root,
    getFile: () => selected,
    clear,
    reset: clear,
  };
}
