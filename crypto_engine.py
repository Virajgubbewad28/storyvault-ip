"""
StoryVault IP — Cryptographic Fingerprinting, Image Telemetry & Dynamic QR Engine
"""
import base64
import hashlib
import io
import qrcode
from PIL import Image


def compute_sha256(file_bytes: bytes) -> str:
    """Return the 64-character hexadecimal SHA-256 digest of raw image bytes."""
    sha256_hash = hashlib.sha256()
    sha256_hash.update(file_bytes)
    return sha256_hash.hexdigest()


def format_file_size(num_bytes: int) -> str:
    """Format byte size into human-readable KB or MB."""
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.2f} MB"
    return f"{num_bytes / 1024:.1f} KB"


def generate_qr_base64(target_url: str) -> str:
    """Generate a unique, high-contrast Base64 PNG QR code encoding target_url."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(target_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


def extract_image_telemetry(file_bytes: bytes, filename: str) -> dict:
    """Compute SHA-256 hash and extract resolution, format, and color profile."""
    digest = compute_sha256(file_bytes)
    size_str = format_file_size(len(file_bytes))

    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            width, height = img.size
            dimensions = f"{width} × {height} px"
            img_format = img.format or filename.split(".")[-1].upper()
            color_profile = "sRGB" if img.mode in ("RGB", "RGBA", "P") else img.mode
    except Exception:
        dimensions = "Unknown"
        img_format = filename.split(".")[-1].upper() if "." in filename else "IMAGE"
        color_profile = "sRGB"

    return {
        "sha256_hash": digest,
        "file_size": size_str,
        "dimensions": dimensions,
        "format": img_format,
        "color_profile": color_profile,
    }