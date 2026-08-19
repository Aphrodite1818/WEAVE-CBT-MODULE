from __future__ import annotations

import asyncio
import hashlib
import os
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.settings import settings


# ============================================================
# IMAGE NORMALIZATION POLICY
# ============================================================

CANVAS_WIDTH = 1200
CANVAS_HEIGHT = 900

# Do not enlarge a tiny image infinitely.
MAX_UPSCALE_FACTOR = 2.0

# Protect against absurdly large/decompression-bomb images.
MAX_SOURCE_PIXELS = 40_000_000

NORMALIZED_MIME_TYPE = "image/webp"
NORMALIZED_EXTENSION = ".webp"

ALLOWED_SOURCE_FORMATS = {
    "JPEG",
    "PNG",
    "WEBP",
}


@dataclass(frozen=True)
class StoredMedia:
    """
    Metadata describing the exact file written to local storage.

    sha256 and size_bytes describe the NORMALIZED stored file,
    not the raw uploaded file.
    """

    storage_key: str
    mime_type: str
    size_bytes: int
    sha256: str


class LocalMediaStorage:
    """
    Store immutable CBT media files on persistent local disk.

    This class knows nothing about PostgreSQL or MediaAsset rows.
    It is responsible only for:

    - validating image bytes;
    - normalizing images;
    - generating safe storage keys;
    - writing files;
    - reading files;
    - deleting files.
    """

    def __init__(
        self,
        root: Path | None = None,
    ) -> None:
        self.root = (root or settings.MEDIA_STORAGE_PATH).resolve()

    # ========================================================
    # PUBLIC API
    # ========================================================

    async def save_question_image(
        self,
        data: bytes,
    ) -> StoredMedia:
        """
        Validate, normalize and persist one question image.

        Files are always stored as immutable normalized WebP images.
        """

        if not data:
            raise ValueError("Uploaded image is empty")

        if len(data) > settings.MEDIA_MAX_IMAGE_SIZE_BYTES:
            raise ValueError("Uploaded image exceeds the maximum allowed size")

        return await asyncio.to_thread(
            self._save_question_image_sync,
            data,
        )

    async def read(
        self,
        storage_key: str,
    ) -> bytes:
        """
        Read a stored media file.
        """

        path = self._resolve_storage_key(storage_key)

        return await asyncio.to_thread(path.read_bytes)

    async def exists(
        self,
        storage_key: str,
    ) -> bool:
        path = self._resolve_storage_key(storage_key)

        return await asyncio.to_thread(path.is_file)

    async def delete(
        self,
        storage_key: str,
    ) -> None:
        """
        Delete the physical file.

        MediaService must first determine that the MediaAsset
        is no longer referenced by a Question or ExamQuestion.
        """

        path = self._resolve_storage_key(storage_key)

        await asyncio.to_thread(
            self._delete_sync,
            path,
        )

    # ========================================================
    # IMAGE PROCESSING
    # ========================================================

    def _save_question_image_sync(
        self,
        data: bytes,
    ) -> StoredMedia:

        normalized_bytes = self._normalize_image(data)

        sha256 = hashlib.sha256(normalized_bytes).hexdigest()

        storage_key = self._generate_question_storage_key()

        destination = self._resolve_storage_key(storage_key)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._atomic_write(
            destination,
            normalized_bytes,
        )

        return StoredMedia(
            storage_key=storage_key,
            mime_type=NORMALIZED_MIME_TYPE,
            size_bytes=len(normalized_bytes),
            sha256=sha256,
        )

    @staticmethod
    def _normalize_image(
        data: bytes,
    ) -> bytes:
        """
        Normalize an uploaded image into a 1200x900 WebP canvas.

        Rules:

        - JPEG, PNG and WebP only;
        - respect EXIF rotation;
        - preserve aspect ratio;
        - never crop;
        - never stretch;
        - downscale large images;
        - upscale small images by at most 2x;
        - center image on a white 1200x900 canvas.
        """

        try:
            with warnings.catch_warnings():
                warnings.simplefilter(
                    "error",
                    Image.DecompressionBombWarning,
                )

                with Image.open(BytesIO(data)) as source:
                    if source.format not in ALLOWED_SOURCE_FORMATS:
                        raise ValueError("Unsupported image format")

                    width, height = source.size

                    if width <= 0 or height <= 0:
                        raise ValueError("Image dimensions are invalid")

                    if width * height > MAX_SOURCE_PIXELS:
                        raise ValueError("Image dimensions are too large")

                    # Correct images taken on phones where the actual
                    # orientation is stored in EXIF metadata.
                    source = ImageOps.exif_transpose(source)

                    width, height = source.size

                    scale = min(
                        CANVAS_WIDTH / width,
                        CANVAS_HEIGHT / height,
                    )

                    # Large image:
                    #     scale will naturally be below 1.
                    #
                    # Tiny image:
                    #     do not enlarge by more than 2x.
                    scale = min(
                        scale,
                        MAX_UPSCALE_FACTOR,
                    )

                    target_width = max(
                        1,
                        round(width * scale),
                    )

                    target_height = max(
                        1,
                        round(height * scale),
                    )

                    resized = source.resize(
                        (
                            target_width,
                            target_height,
                        ),
                        Image.Resampling.LANCZOS,
                    )

                    # White canvas provides predictable rendering
                    # regardless of frontend theme.
                    canvas = Image.new(
                        "RGB",
                        (
                            CANVAS_WIDTH,
                            CANVAS_HEIGHT,
                        ),
                        "white",
                    )

                    # Support transparent PNG/WebP images by compositing
                    # their alpha channel onto the white canvas.
                    if resized.mode in {
                        "RGBA",
                        "LA",
                    }:
                        rgba = resized.convert("RGBA")

                        x = (CANVAS_WIDTH - target_width) // 2

                        y = (CANVAS_HEIGHT - target_height) // 2

                        canvas.paste(
                            rgba,
                            (x, y),
                            rgba,
                        )

                    else:
                        rgb = resized.convert("RGB")

                        x = (CANVAS_WIDTH - target_width) // 2

                        y = (CANVAS_HEIGHT - target_height) // 2

                        canvas.paste(
                            rgb,
                            (x, y),
                        )

                    output = BytesIO()

                    canvas.save(
                        output,
                        format="WEBP",
                        lossless=True,
                        method=6,
                    )

                    return output.getvalue()

        except (
            UnidentifiedImageError,
            Image.DecompressionBombError,
        ) as exc:
            raise ValueError("Uploaded file is not a valid supported image") from exc

        except OSError as exc:
            raise ValueError("Uploaded image could not be processed") from exc

    # ========================================================
    # STORAGE KEYS
    # ========================================================

    @staticmethod
    def _generate_question_storage_key() -> str:
        """
        Generate an opaque server-controlled relative path.

        Example:

        questions/7a/7a5f03e4....webp
        """

        file_id = uuid4().hex

        return f"questions/{file_id[:2]}/{file_id}{NORMALIZED_EXTENSION}"

    def _resolve_storage_key(
        self,
        storage_key: str,
    ) -> Path:
        """
        Convert a relative storage key into an absolute filesystem path
        while preventing path traversal.
        """

        if not storage_key:
            raise ValueError("Storage key is required")

        relative_path = Path(storage_key)

        if relative_path.is_absolute():
            raise ValueError("Storage key must be relative")

        resolved = (self.root / relative_path).resolve()

        if not resolved.is_relative_to(self.root):
            raise ValueError("Invalid storage key")

        return resolved

    # ========================================================
    # FILE OPERATIONS
    # ========================================================

    @staticmethod
    def _atomic_write(
        destination: Path,
        data: bytes,
    ) -> None:
        """
        Write to a temporary file first and atomically replace the
        destination.

        This prevents partially-written media files if the process
        crashes during the write.
        """

        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")

        try:
            temporary.write_bytes(data)

            os.replace(
                temporary,
                destination,
            )

        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _delete_sync(
        path: Path,
    ) -> None:
        path.unlink(missing_ok=True)


local_media_storage = LocalMediaStorage()
