"""Local image upload endpoint. Images are validated with Pillow."""

from __future__ import annotations

from flask import Blueprint, request

from ..utils.responses import success
from ..utils.uploads import save_image_upload

bp = Blueprint("uploads", __name__)


@bp.post("/uploads")
def upload_image():
    file_storage = request.files.get("image") or request.files.get("file")
    result = save_image_upload(file_storage)
    return success(result, status=201, message="图片上传成功")
