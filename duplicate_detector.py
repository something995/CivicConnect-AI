"""
Duplicate Complaint Detection Module

Uses three signals to detect similar complaints:
  1. Text similarity   — cosine similarity on word vectors
  2. Location matching  — city + area string matching
  3. Image similarity   — Perceptual Hashing (pHash)

pHash stays consistent even if photos are slightly blurry, cropped,
or taken at a different angle. This lets us detect when two citizens
photograph the same pothole from different positions.

If duplicates are found, the new complaint can be attached to an
existing "community ticket" instead of creating a standalone entry.
"""

import sqlite3
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter
import math

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent / "complaints.db"

# ── Thresholds ─────────────────────────────────────────────────────
TEXT_SIMILARITY_THRESHOLD = 0.35
IMAGE_HASH_THRESHOLD = 12          # Hamming distance; <=12 = visually similar
TIME_WINDOW_DAYS = 30


# ── pHash support ──────────────────────────────────────────────────
try:
    import imagehash
    from PIL import Image
    PHASH_AVAILABLE = True
    logger.info("✅ imagehash available — image duplicate detection enabled")
except ImportError:
    PHASH_AVAILABLE = False
    logger.warning("⚠️  imagehash not installed — image duplicate detection disabled")


def compute_phash(image_path: str) -> str:
    """
    Compute a perceptual hash for an image file.
    Returns a hex string (e.g. "a4e0f83c18281808") or None.
    
    Unlike a standard file hash (MD5/SHA), pHash stays the same
    even if the photo is slightly blurry, resized, or taken at a
    slightly different angle.
    """
    if not PHASH_AVAILABLE:
        return None
    try:
        img = Image.open(image_path)
        h = imagehash.phash(img, hash_size=16)
        return str(h)
    except Exception as exc:
        logger.warning("pHash computation failed: %s", exc)
        return None


def _hamming_distance(hash_a: str, hash_b: str) -> int:
    """Compute Hamming distance between two hex hash strings."""
    if not hash_a or not hash_b or len(hash_a) != len(hash_b):
        return 999  # incomparable
    try:
        int_a = int(hash_a, 16)
        int_b = int(hash_b, 16)
        return bin(int_a ^ int_b).count('1')
    except ValueError:
        return 999


# ── Database helpers ───────────────────────────────────────────────

def _get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_phash_column():
    """Add the image_phash column if it doesn't exist."""
    conn = _get_connection()
    try:
        conn.execute("ALTER TABLE complaints ADD COLUMN image_phash TEXT")
        conn.commit()
        logger.info("Added image_phash column to complaints table")
    except sqlite3.OperationalError:
        pass  # column already exists
    conn.close()


# Run once at import time
_ensure_phash_column()


def save_phash(complaint_id: str, phash_value: str):
    """Store the pHash alongside a complaint."""
    if not phash_value:
        return
    conn = _get_connection()
    conn.execute("UPDATE complaints SET image_phash = ? WHERE id = ?",
                 (phash_value, complaint_id))
    conn.commit()
    conn.close()


# ── Text similarity ───────────────────────────────────────────────

def _cosine_similarity(text_a: str, text_b: str) -> float:
    """
    Simple word-overlap cosine similarity with TF weighting.
    No external ML dependencies needed.
    """
    words_a = Counter(text_a.lower().split())
    words_b = Counter(text_b.lower().split())

    common = set(words_a.keys()) & set(words_b.keys())
    if not common:
        return 0.0

    # Remove stop words from similarity calculation
    STOP = {"the", "a", "an", "is", "in", "on", "at", "of", "to", "and",
            "it", "for", "has", "have", "been", "was", "are", "this", "that",
            "my", "i", "we", "our", "there", "near", "from", "with"}
    common -= STOP

    if not common:
        return 0.0

    dot = sum(words_a[w] * words_b[w] for w in common)
    mag_a = math.sqrt(sum(v ** 2 for k, v in words_a.items() if k not in STOP))
    mag_b = math.sqrt(sum(v ** 2 for k, v in words_b.items() if k not in STOP))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)


# ── Location similarity ───────────────────────────────────────────

def _location_match_score(city_a: str, area_a: str,
                          city_b: str, area_b: str) -> float:
    """Return a location similarity score (0.0 to 1.0)."""
    city_a = (city_a or "").strip().lower()
    city_b = (city_b or "").strip().lower()
    area_a = (area_a or "").strip().lower()
    area_b = (area_b or "").strip().lower()

    if city_a == city_b and area_a == area_b:
        return 1.0
    elif city_a == city_b and (area_a in area_b or area_b in area_a):
        return 0.7
    elif city_a == city_b:
        return 0.3
    return 0.0


# ── Main duplicate finder ─────────────────────────────────────────

def find_duplicates(complaint_text: str, issue_type: str,
                    city: str, area: str,
                    image_label: str = None,
                    image_phash: str = None,
                    max_results: int = 5) -> list:
    """
    Search existing complaints for potential duplicates.

    Uses three signals weighted together:
      - Text similarity   (45%)
      - Location match    (25%)
      - Issue type match  (20%)
      - Image pHash match (10% bonus)

    Returns a list of match dictionaries sorted by overall score.
    """
    conn = _get_connection()

    cutoff = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).isoformat()

    rows = conn.execute("""
        SELECT id, complaint_text, issue_type, city, area,
               severity, status, created_at, image_label, image_phash
        FROM complaints
        WHERE created_at >= ?
        ORDER BY created_at DESC
        LIMIT 200
    """, (cutoff,)).fetchall()
    conn.close()

    if not rows:
        return []

    matches = []

    for row in rows:
        row = dict(row)

        # 1. Text similarity
        text_sim = _cosine_similarity(complaint_text, row["complaint_text"])

        # 2. Location match
        loc_score = _location_match_score(city, area, row["city"], row["area"])

        # 3. Issue type match
        issue_match = (issue_type == row["issue_type"])

        # 4. Image pHash similarity (the key innovation)
        image_sim_bonus = 0.0
        image_match_reason = None

        if image_phash and row.get("image_phash"):
            hamming = _hamming_distance(image_phash, row["image_phash"])
            if hamming <= IMAGE_HASH_THRESHOLD:
                # Very similar images — likely the same physical issue
                image_sim_bonus = 1.0 - (hamming / IMAGE_HASH_THRESHOLD)
                image_match_reason = f"Image match (pHash distance: {hamming})"
        elif image_label and row.get("image_label") and image_label == row["image_label"]:
            # Fallback: same classification label
            image_sim_bonus = 0.5
            image_match_reason = "Same issue type detected in image"

        # Weighted overall score
        overall = (
            text_sim * 0.40 +
            loc_score * 0.25 +
            (0.20 if issue_match else 0.0) +
            image_sim_bonus * 0.15
        )

        # Only include meaningful matches
        if overall >= 0.28 and (text_sim >= TEXT_SIMILARITY_THRESHOLD or
                                 (issue_match and loc_score >= 0.7) or
                                 image_sim_bonus >= 0.5):
            match_entry = {
                "id": row["id"],
                "complaint_text": (row["complaint_text"][:150] +
                                   ("..." if len(row["complaint_text"]) > 150 else "")),
                "similarity_score": round(overall * 100, 1),
                "text_similarity": round(text_sim * 100, 1),
                "location_match": round(loc_score * 100, 1),
                "issue_match": issue_match,
                "image_match": image_match_reason,
                "created_at": row["created_at"][:10],
                "severity": row["severity"],
                "status": row["status"],
                "area": row["area"],
                "issue_type": row["issue_type"],
            }
            matches.append(match_entry)

    matches.sort(key=lambda x: x["similarity_score"], reverse=True)

    logger.info("🔍 Duplicate check: %d matches (top: %.1f%%) [pHash=%s]",
                len(matches),
                matches[0]["similarity_score"] if matches else 0,
                "yes" if image_phash else "no")

    return matches[:max_results]


def get_duplicate_count(issue_type: str, city: str, area: str) -> int:
    """Count how many complaints exist for the same issue+location recently."""
    conn = _get_connection()
    cutoff = (datetime.now() - timedelta(days=TIME_WINDOW_DAYS)).isoformat()

    count = conn.execute("""
        SELECT COUNT(*) as c FROM complaints
        WHERE issue_type = ?
        AND LOWER(city) = ?
        AND LOWER(area) = ?
        AND created_at >= ?
    """, (issue_type,
          (city or "").strip().lower(),
          (area or "").strip().lower(),
          cutoff)).fetchone()["c"]

    conn.close()
    return count
