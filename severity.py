"""
AI-based severity scoring for civic complaints.

Combines:
  1. Text analysis  (keyword matching, duration detection)
  2. Image analysis  (confidence-weighted damage estimation from YOLO)
  3. Issue-type base score
  4. Contextual factors  (complaint length, time persistence)
"""

import re
import logging

logger = logging.getLogger(__name__)

# ── Keyword dictionaries ─────────────────────────────────────────────

CRITICAL_KEYWORDS = [
    "accident", "death", "electrocution", "fire", "collapse", "drowning",
    "life threatening", "life-threatening", "fatal", "emergency", "sparking",
    "high tension", "fallen wire", "electric shock", "child fell", "children at risk",
    "hospital", "ambulance", "someone got hurt", "snake", "submerged",
    "major accident", "road cave", "sinkhole", "building crack",
    "open manhole", "manhole cover missing", "fell into manhole",
    "manhole broken", "sewage on road", "manhole open",
]

HIGH_KEYWORDS = [
    "dangerous", "hazard", "risk", "unsafe", "slipping", "falling",
    "deep pothole", "huge crater", "open manhole", "broken pole",
    "dark at night", "no visibility", "flooding", "knee-deep", "ankle-deep",
    "foul smell", "health issue", "infection", "mosquito", "dengue",
    "vehicle damage", "tyre burst", "tire puncture", "can't walk",
    "cannot pass", "blocked", "entered homes", "sewage entering",
    "multiple complaints", "no response", "ignored", "many days",
    "over a month", "weeks", "spreading", "breeding",
    "overflowing badly", "unbearable", "severe", "heavily damaged",
    "manhole", "sewage overflow", "drain overflow", "gutter overflow",
    "sewage leaking", "sewage water", "manhole cover", "drainage block",
    "nala overflow", "sewer burst", "septic overflow",
]

MEDIUM_KEYWORDS = [
    "pothole", "garbage", "sewage", "drain", "waterlogging", "stagnant",
    "not working", "broken", "damaged", "overflowing", "leaking",
    "not functioning", "piling up", "accumulating", "smell", "dirty",
    "dark", "flickering", "clogged", "waste", "sewer", "gutter",
    "drainage", "manhole", "nala",
]

LOW_KEYWORDS = [
    "minor", "small", "slightly", "sometimes", "occasional",
    "not urgent", "just noticed", "cosmetic", "paint", "faded",
]

# ── Issue-type base severity ─────────────────────────────────────────

ISSUE_BASE_SCORE = {
    "pothole_road_damage":        55,
    "sewage_overflow":            65,
    "waterlogging":               55,
    "streetlight_or_electricity": 50,
    "garbage":                    45,
    "others":                     40,
}

# ── Image-based severity factors ─────────────────────────────────────
# When the image model detects an issue with high confidence, it adds
# to the severity. Higher confidence = the issue is clearer/worse.

IMAGE_SEVERITY_BOOST = {
    "pothole_road_damage":        {"base": 10, "high_conf": 18},
    "garbage":                    {"base":  8, "high_conf": 14},
    "sewage_overflow":            {"base": 12, "high_conf": 20},
    "streetlight_or_electricity": {"base": 10, "high_conf": 16},
    "waterlogging":               {"base": 12, "high_conf": 20},
    "others":                     {"base":  5, "high_conf": 10},
}


def compute_severity(complaint_text: str, issue_type: str,
                     image_label: str = None,
                     image_confidence: float = None,
                     duplicate_count: int = 0) -> dict:
    """
    Return a severity assessment:
        {
            "level":  "low" | "medium" | "high" | "critical",
            "score":  0-100,
            "reasons": [str, ...]
        }
    """
    text = (complaint_text or "").lower()
    reasons = []

    # ── 1. Base score from issue type ──────────────────────────────
    score = ISSUE_BASE_SCORE.get(issue_type, 40)

    # ── 2. Text keyword analysis ───────────────────────────────────
    # Critical keywords
    for kw in CRITICAL_KEYWORDS:
        if kw in text:
            score += 25
            reasons.append(f"⚠️ Critical safety concern: '{kw}'")
            break

    # High keywords
    high_hits = 0
    for kw in HIGH_KEYWORDS:
        if kw in text:
            high_hits += 1
            if high_hits <= 3:
                reasons.append(f"🔴 High concern: '{kw}'")
    score += min(high_hits * 6, 30)

    # Medium keywords
    med_hits = sum(1 for kw in MEDIUM_KEYWORDS if kw in text)
    score += min(med_hits * 3, 15)

    # Low keywords (reduce)
    low_hits = sum(1 for kw in LOW_KEYWORDS if kw in text)
    score -= min(low_hits * 8, 20)

    # ── 3. Image-based severity boost ──────────────────────────────
    if image_label and image_confidence is not None:
        img_type = image_label
        boost_config = IMAGE_SEVERITY_BOOST.get(img_type, IMAGE_SEVERITY_BOOST["others"])

        if image_confidence >= 85:
            boost = boost_config["high_conf"]
            reasons.append(f"📷 Image confirms severe {img_type.replace('_', ' ')} (conf: {image_confidence}%)")
        elif image_confidence >= 60:
            boost = boost_config["base"]
            reasons.append(f"📷 Image detected {img_type.replace('_', ' ')} (conf: {image_confidence}%)")
        else:
            boost = boost_config["base"] // 2
            reasons.append(f"📷 Image suggests {img_type.replace('_', ' ')} (low conf: {image_confidence}%)")

        score += boost

    # ── 4. Contextual factors ──────────────────────────────────────
    # Complaint length (detailed = more urgent)
    word_count = len(text.split())
    if word_count > 40:
        score += 5
        reasons.append("📝 Detailed description provided")
    elif word_count < 8:
        score -= 5

    # Duration persistence
    duration_match = re.search(r'(\d+)\s*(day|week|month)', text)
    if duration_match:
        num = int(duration_match.group(1))
        unit = duration_match.group(2)
        if unit == "month" or (unit == "week" and num >= 2) or (unit == "day" and num >= 7):
            score += 10
            reasons.append(f"⏳ Issue persisting for {num} {unit}(s)")

    # ── 5. Duplicate/community impact boost ────────────────────────
    if duplicate_count > 0:
        dup_boost = min(duplicate_count * 5, 20)
        score += dup_boost
        reasons.append(f"👥 {duplicate_count} similar complaint(s) in this area")

    # ── Clamp & level ──────────────────────────────────────────────
    score = max(5, min(100, score))

    if score >= 80:
        level = "critical"
    elif score >= 60:
        level = "high"
    elif score >= 40:
        level = "medium"
    else:
        level = "low"

    if not reasons:
        reasons.append("Standard civic complaint")

    logger.info("Severity: score=%d  level=%s  img=%s/%s  dups=%d",
                score, level, image_label, image_confidence, duplicate_count)

    return {
        "level": level,
        "score": score,
        "reasons": reasons[:6],
    }
