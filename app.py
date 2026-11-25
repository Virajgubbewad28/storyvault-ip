"""
StoryVault IP — Digital Story Image Source Register
Main Flask Web Application, Dynamic QR Generator & Provenance Verification API
"""
import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from database import (
    init_db,
    get_db_connection,
    generate_next_reg_id,
    current_ist_timestamp,
)
from crypto_engine import (
    extract_image_telemetry,
    compute_sha256,
    generate_qr_base64,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

app = Flask(__name__)
# Ensures _external=True generates https:// URLs accurately behind cloud reverse proxies
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config["UPLOAD_FOLDER"] = os.path.join(BASE_DIR, "static", "uploads")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload cap
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

init_db()


def is_allowed_image(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def build_certificate_links(reg_id: str) -> tuple[str, str]:
    """Return (direct_pdf_print_url, qr_base64_data_uri) unique to reg_id."""
    pdf_print_url = url_for("certificate", reg_id=reg_id, autoprint=1, _external=True)
    qr_data_uri = generate_qr_base64(pdf_print_url)
    return pdf_print_url, qr_data_uri


@app.errorhandler(413)
def file_too_large(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "File exceeds the 50 MB upload limit."}), 413
    return redirect(url_for("register", error="Uploaded file exceeds the 50 MB limit."))


@app.route("/")
def index():
    conn = get_db_connection()
    try:
        total_count = conn.execute("SELECT COUNT(*) FROM registry_assets").fetchone()[0]
        latest_asset = conn.execute(
            "SELECT * FROM registry_assets ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return render_template("index.html", total_count=total_count, latest_asset=latest_asset)


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        story_title = request.form.get("story_title", "").strip() or "Untitled Digital Story"
        episode_no = request.form.get("episode_no", "").strip() or "Episode 01"
        frame_id = request.form.get("frame_id", "").strip() or "Frame 01"
        primary_creator = request.form.get("primary_creator", "").strip() or "Viraj S."
        co_author = request.form.get("co_author", "").strip() or "Sole Authorship"
        if co_author.lower().startswith("none"):
            co_author = "Sole Authorship"
        source_type = request.form.get("source_classification", "Original Artwork")
        usage_license = request.form.get(
            "usage_license", "All Rights Reserved — Author Copyright"
        )

        uploaded_file = request.files.get("story_image")
        if not uploaded_file or not uploaded_file.filename:
            return redirect(
                url_for("register", error="Please select a story image file before committing.")
            )

        if not is_allowed_image(uploaded_file.filename):
            return redirect(
                url_for("register", error="Only PNG, JPG, JPEG, and WEBP image files are allowed.")
            )

        file_bytes = uploaded_file.read()
        if not file_bytes:
            return redirect(
                url_for("register", error="Uploaded file is empty. Please choose a valid image.")
            )

        telemetry = extract_image_telemetry(file_bytes, uploaded_file.filename)

        conn = get_db_connection()
        try:
            existing = conn.execute(
                "SELECT reg_id FROM registry_assets WHERE sha256_hash = ?",
                (telemetry["sha256_hash"],),
            ).fetchone()
            if existing:
                return redirect(url_for("verify", reg_id=existing["reg_id"], duplicate="1"))

            safe_name = secure_filename(uploaded_file.filename) or "story_frame.png"
            stored_filename = f"{uuid.uuid4().hex[:8]}_{safe_name}"
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)
            with open(save_path, "wb") as f:
                f.write(file_bytes)

            reg_id = generate_next_reg_id(conn)
            timestamp = current_ist_timestamp()

            conn.execute(
                """
                INSERT INTO registry_assets (
                    reg_id, story_title, episode_no, frame_id, primary_creator,
                    co_author, source_type, usage_license, sha256_hash, file_name,
                    file_path, file_size, dimensions, color_profile, registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reg_id,
                    story_title,
                    episode_no,
                    frame_id,
                    primary_creator,
                    co_author,
                    source_type,
                    usage_license,
                    telemetry["sha256_hash"],
                    safe_name,
                    f"uploads/{stored_filename}",
                    telemetry["file_size"],
                    telemetry["dimensions"],
                    telemetry["color_profile"],
                    timestamp,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return redirect(url_for("verify", reg_id=reg_id, created="1"))

    error_msg = request.args.get("error")
    return render_template("register.html", error_msg=error_msg)


@app.route("/api/inspect", methods=["POST"])
def api_inspect():
    """Real-time SHA-256 & image metadata inspection endpoint for the Registration Studio."""
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "No file provided"}), 400

    if not is_allowed_image(uploaded_file.filename):
        return jsonify({"error": "Unsupported format. Use PNG, JPG, or WEBP."}), 400

    file_bytes = uploaded_file.read()
    if not file_bytes:
        return jsonify({"error": "Empty file provided"}), 400

    telemetry = extract_image_telemetry(file_bytes, uploaded_file.filename)

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT reg_id, story_title, primary_creator FROM registry_assets WHERE sha256_hash = ?",
            (telemetry["sha256_hash"],),
        ).fetchone()
    finally:
        conn.close()

    telemetry["filename"] = uploaded_file.filename
    telemetry["collision"] = dict(existing) if existing else None
    return jsonify(telemetry)


@app.route("/ledger")
def ledger():
    conn = get_db_connection()
    try:
        assets = conn.execute("SELECT * FROM registry_assets ORDER BY id DESC").fetchall()
    finally:
        conn.close()

    total_count = len(assets)
    original_count = sum(1 for a in assets if a["source_type"] == "Original Artwork")
    licensed_cc0_count = sum(
        1 for a in assets if a["source_type"] in ("Licensed Stock", "Public Domain / CC0")
    )
    original_pct = round((original_count / total_count) * 100, 1) if total_count else 0.0
    licensed_pct = round((licensed_cc0_count / total_count) * 100, 1) if total_count else 0.0

    return render_template(
        "ledger.html",
        assets=assets,
        total_count=total_count,
        original_count=original_count,
        original_pct=original_pct,
        licensed_cc0_count=licensed_cc0_count,
        licensed_pct=licensed_pct,
    )


@app.route("/verify")
def verify():
    reg_id = request.args.get("reg_id", "").strip()
    asset = None
    pdf_print_url = ""
    qr_data_uri = ""

    if reg_id:
        conn = get_db_connection()
        try:
            asset = conn.execute(
                "SELECT * FROM registry_assets WHERE reg_id = ?", (reg_id,)
            ).fetchone()
        finally:
            conn.close()

    if asset:
        pdf_print_url, qr_data_uri = build_certificate_links(asset["reg_id"])

    created = request.args.get("created") == "1"
    duplicate = request.args.get("duplicate") == "1"

    return render_template(
        "verify.html",
        asset=asset,
        pdf_print_url=pdf_print_url,
        qr_data_uri=qr_data_uri,
        created=created,
        duplicate=duplicate,
    )


@app.route("/certificate/<reg_id>")
def certificate(reg_id):
    conn = get_db_connection()
    try:
        asset = conn.execute(
            "SELECT * FROM registry_assets WHERE reg_id = ?", (reg_id.strip(),)
        ).fetchone()
    finally:
        conn.close()

    if not asset:
        return redirect(url_for("verify"))

    pdf_print_url, qr_data_uri = build_certificate_links(asset["reg_id"])
    return render_template(
        "certificate.html",
        asset=asset,
        pdf_print_url=pdf_print_url,
        qr_data_uri=qr_data_uri,
    )


@app.route("/api/verify", methods=["POST"])
def api_verify():
    """Cryptographic tamper-detection endpoint: returns matching record + unique QR code."""
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "No file uploaded"}), 400

    file_bytes = uploaded_file.read()
    if not file_bytes:
        return jsonify({"error": "Empty file uploaded"}), 400

    digest = compute_sha256(file_bytes)

    conn = get_db_connection()
    try:
        match = conn.execute(
            "SELECT * FROM registry_assets WHERE sha256_hash = ?", (digest,)
        ).fetchone()
    finally:
        conn.close()

    if match:
        record_dict = dict(match)
        pdf_print_url, qr_data_uri = build_certificate_links(record_dict["reg_id"])
        return jsonify(
            {
                "verified": True,
                "sha256_hash": digest,
                "record": record_dict,
                "pdf_print_url": pdf_print_url,
                "qr_data_uri": qr_data_uri,
            }
        )
    return jsonify(
        {
            "verified": False,
            "sha256_hash": digest,
            "filename": uploaded_file.filename,
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)