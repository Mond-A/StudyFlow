"""Image upload validation and local image loading for multimodal AI calls."""

from __future__ import annotations

import base64
import io
import os
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

from .exceptions import APIError

ALLOWED_FORMATS = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}
MAX_IMAGE_PIXELS = 25_000_000
MAX_EDGE = 2400


def save_image_upload(file_storage) -> dict:
    """Validate a real image with Pillow, strip metadata and store it safely."""
    if file_storage is None or not getattr(file_storage, "filename", ""):
        raise APIError("请选择要上传的图片", code="VALIDATION_ERROR", status_code=400)

    original_name = file_storage.filename
    ext = Path(original_name).suffix.lower().lstrip(".")
    allowed_ext = current_app.config["ALLOWED_IMAGE_EXTENSIONS"]
    if ext not in allowed_ext:
        raise APIError(
            "仅支持 JPG、PNG、WebP 图片",
            code="UNSUPPORTED_FILE_TYPE",
            status_code=415,
        )

    raw = file_storage.read()
    if not raw:
        raise APIError("上传的图片为空", code="VALIDATION_ERROR", status_code=400)
    max_bytes = current_app.config["MAX_IMAGE_BYTES"]
    if len(raw) > max_bytes:
        raise APIError(
            f"图片不能超过 {max_bytes // (1024 * 1024)} MB",
            code="FILE_TOO_LARGE",
            status_code=413,
        )

    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            image_format = (probe.format or "").upper()
            if image_format not in ALLOWED_FORMATS:
                raise APIError(
                    "文件内容不是受支持的图片格式",
                    code="UNSUPPORTED_FILE_TYPE",
                    status_code=415,
                )
            probe.verify()

        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            if max(image.size) > MAX_EDGE:
                image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
            width, height = image.size
            if image_format == "JPEG" and image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            if image_format == "PNG" and image.mode not in ("RGB", "RGBA", "L", "LA"):
                image = image.convert("RGBA")

            suffix, mime = ALLOWED_FORMATS[image_format]
            filename = f"{uuid.uuid4().hex}{suffix}"
            upload_dir = Path(current_app.config["UPLOAD_DIR"])
            upload_dir.mkdir(parents=True, exist_ok=True)
            target = upload_dir / filename
            temp = upload_dir / f".{filename}.part"
            save_kwargs = {}
            if image_format == "JPEG":
                save_kwargs = {"quality": 90, "optimize": True}
            elif image_format == "WEBP":
                save_kwargs = {"quality": 90, "method": 4}
            elif image_format == "PNG":
                save_kwargs = {"optimize": True}

            image.save(temp, format=image_format, **save_kwargs)
            os.replace(temp, target)
    except APIError:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise APIError(
            "图片无法读取或已损坏，请更换文件后重试",
            code="INVALID_IMAGE",
            status_code=415,
        ) from exc
    except Image.DecompressionBombError as exc:
        raise APIError(
            "图片像素尺寸过大",
            code="INVALID_IMAGE",
            status_code=413,
        ) from exc

    size_bytes = target.stat().st_size
    return {
        "filename": filename,
        "url": f"/uploads/{filename}",
        "mime_type": mime,
        "size_bytes": size_bytes,
        "width": width,
        "height": height,
        "original_name": original_name,
    }


def resolve_uploaded_image(url_or_filename: str) -> Path:
    """Only resolve files inside the configured upload directory (no SSRF)."""
    if not isinstance(url_or_filename, str) or not url_or_filename.strip():
        raise APIError("请先上传图片", code="IMAGE_REQUIRED", status_code=400)
    value = url_or_filename.strip()
    if value.startswith("http://") or value.startswith("https://"):
        raise APIError(
            "为安全起见，仅支持使用本地上传接口返回的图片地址",
            code="INVALID_IMAGE_URL",
            status_code=400,
        )
    if value.startswith("/uploads/"):
        value = value[len("/uploads/") :]
    value = Path(value).name
    if not value or Path(value).suffix.lower().lstrip(".") not in {
        "jpg",
        "jpeg",
        "png",
        "webp",
    }:
        raise APIError("图片地址无效", code="INVALID_IMAGE_URL", status_code=400)
    upload_dir = Path(current_app.config["UPLOAD_DIR"]).resolve()
    path = (upload_dir / value).resolve()
    if upload_dir not in path.parents or not path.is_file():
        raise APIError(
            "图片不存在，请重新上传", code="IMAGE_NOT_FOUND", status_code=404
        )
    if path.stat().st_size > current_app.config["MAX_IMAGE_BYTES"]:
        raise APIError("图片文件过大", code="FILE_TOO_LARGE", status_code=413)
    return path


def load_upload_data_url(url_or_filename: str) -> str:
    path = resolve_uploaded_image(url_or_filename)
    extension = path.suffix.lower().lstrip(".")
    mime = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }[extension]
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"
