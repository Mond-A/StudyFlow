"""Local image upload endpoint. Images are validated with Pillow."""

from __future__ import annotations

from flask import Blueprint, request

from ..db import get_current_user_id
from ..utils.responses import success
from ..utils.uploads import save_image_upload

bp = Blueprint("uploads", __name__)


@bp.post("/uploads")
def upload_image():
    file_storage = request.files.get("image") or request.files.get("file")
    result = save_image_upload(file_storage, get_current_user_id())
    return success(result, status=201, message="图片上传成功")
