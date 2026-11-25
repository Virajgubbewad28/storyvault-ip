"""
StoryVault IP — Immutable SQLite Provenance Ledger
Stores digital story image records, authorship metadata, and SHA-256 digests.
"""
import os
import sqlite3
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "storyvault.db")
IST = timezone(timedelta(hours=5, minutes=30))


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registry_assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reg_id TEXT UNIQUE NOT NULL,
                story_title TEXT NOT NULL,
                episode_no TEXT NOT NULL,
                frame_id TEXT NOT NULL,
                primary_creator TEXT NOT NULL,
                co_author TEXT NOT NULL,
                source_type TEXT NOT NULL,
                usage_license TEXT NOT NULL,
                sha256_hash TEXT UNIQUE NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT,
                file_size TEXT NOT NULL,
                dimensions TEXT NOT NULL,
                color_profile TEXT NOT NULL,
                registered_at TEXT NOT NULL
            )
            """
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM registry_assets").fetchone()[0]
        if count == 0:
            seed_records = [
                (
                    "REG-2026-085",
                    "Kaveri Glassworks",
                    "Ep. 05",
                    "Frame 03",
                    "Ananya Rao",
                    "Joint Authorship",
                    "AI-Assisted Work",
                    "Creative Commons Attribution 4.0 (CC BY 4.0)",
                    "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
                    "Kaveri_Ep05_Frame03.png",
                    "",
                    "1.85 MB",
                    "1920 × 1080 px",
                    "sRGB",
                    "24 Nov 2026, 11:50 IST",
                ),
                (
                    "REG-2026-086",
                    "Starlight Archive",
                    "Ch. 02",
                    "Plate 09",
                    "Rohan Kulkarni",
                    "Sole Authorship",
                    "Public Domain / CC0",
                    "CC0 1.0 Universal — Public Domain Dedication",
                    "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                    "Starlight_Ch02_Plate09.png",
                    "",
                    "3.10 MB",
                    "2560 × 1440 px",
                    "sRGB",
                    "24 Nov 2026, 21:05 IST",
                ),
                (
                    "REG-2026-087",
                    "Monsoon Courier",
                    "Ep. 07",
                    "Backdrop 02",
                    "Meera Nair",
                    "Joint Authorship",
                    "Licensed Stock",
                    "Commercial Publishing License — Webtoon Exclusive",
                    "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
                    "Monsoon_Ep07_Backdrop02.jpg",
                    "",
                    "2.12 MB",
                    "1920 × 1080 px",
                    "sRGB",
                    "25 Nov 2026, 14:22 IST",
                ),
                (
                    "REG-2026-088",
                    "Chronicles of Hampi",
                    "Ch. 01",
                    "Panel 04",
                    "Aarav Sharma",
                    "Sole Authorship",
                    "Original Artwork",
                    "All Rights Reserved — Author Copyright",
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "Hampi_Ch01_Panel04.png",
                    "",
                    "2.75 MB",
                    "2048 × 1152 px",
                    "sRGB",
                    "25 Nov 2026, 16:40 IST",
                ),
                (
                    "REG-2026-089",
                    "Neon Bengaluru 2099",
                    "Episode 03",
                    "Frame 12",
                    "Viraj S.",
                    "Sole Authorship",
                    "Original Artwork",
                    "All Rights Reserved — Author Copyright",
                    "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
                    "Cyber-Bengaluru_Ep03_Frame12.png",
                    "",
                    "2.40 MB",
                    "1920 × 1080 px",
                    "sRGB",
                    "25 Nov 2026, 17:15 IST",
                ),
            ]
            conn.executemany(
                """
                INSERT INTO registry_assets (
                    reg_id, story_title, episode_no, frame_id, primary_creator,
                    co_author, source_type, usage_license, sha256_hash, file_name,
                    file_path, file_size, dimensions, color_profile, registered_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                seed_records,
            )
            conn.commit()
    finally:
        conn.close()


def generate_next_reg_id(conn) -> str:
    row = conn.execute("SELECT id FROM registry_assets ORDER BY id DESC LIMIT 1").fetchone()
    next_seq = 85 + (row["id"] if row else 0)
    return f"REG-2026-{next_seq:03d}"


def current_ist_timestamp() -> str:
    return datetime.now(IST).strftime("%d %b %Y, %H:%M:%S IST")