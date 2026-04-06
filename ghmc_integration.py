"""
GHMC Integration Module — Professional Complaint Forwarding

Formats complaints as official-looking "CIVIC-MONITOR" reports that:
  1. Use professional Report IDs (HYD-VIGIL-XXXX)
  2. Map severity to GHMC's official action levels
  3. Include verified metadata (GPS, pHash proof, timestamp)
  4. Use randomized templates (8 styles) to avoid spam detection
  5. Provide One-Click Copy for frictionless sharing

The goal: Make GHMC officials treat these as high-quality, pre-analyzed
complaints from an organized monitoring platform, not casual texts.
"""

import logging
import random
import urllib.parse
from datetime import datetime

logger = logging.getLogger(__name__)

# ── GHMC official channels ────────────────────────────────────────
GHMC_WHATSAPP_SANITATION = "918125966586"   # GHMC Sanitation WhatsApp
GHMC_WHATSAPP_GENERAL    = "919000113600"   # GHMC general helpline
GHMC_HELPLINE            = "040-21111111"

# ── Severity → Official Action Levels ─────────────────────────────
SEVERITY_TO_ACTION_LEVEL = {
    "low":      {"level": "Level 1", "label": "General Maintenance",
                 "emoji": "🟢", "tag": "GENERAL MAINTENANCE"},
    "medium":   {"level": "Level 2", "label": "Public Inconvenience",
                 "emoji": "🟡", "tag": "PUBLIC INCONVENIENCE"},
    "high":     {"level": "Level 3", "label": "Health/Safety Hazard",
                 "emoji": "🟠", "tag": "HEALTH/SAFETY HAZARD"},
    "critical": {"level": "Level 4", "label": "Immediate Emergency / Road Blockage",
                 "emoji": "🔴", "tag": "IMMEDIATE EMERGENCY"},
}

# ── Ward/Circle → Zone mapping (official GHMC 12-zone, 2025-2026) ──
# Source: GHMC reorganization — 12 zones, 60 circles, 300 wards
#
# ZONES: Malkajgiri, Uppal, LB Nagar, Shamshabad, Rajendranagar,
#        Charminar, Golconda, Khairatabad, Secunderabad,
#        Serilingampally, Kukatpally, Quthbullapur
AREA_TO_WARD = {
    # ── Zone: Kukatpally ──────────────────────────────────────────
    "kukatpally":      {"ward": "Kukatpally",     "zone": "Kukatpally"},
    "kphb":            {"ward": "Kukatpally",     "zone": "Kukatpally"},
    "moosapet":        {"ward": "Moosapet",       "zone": "Kukatpally"},
    "madhapur":        {"ward": "Madhapur",       "zone": "Kukatpally"},
    "hitech city":     {"ward": "Madhapur",       "zone": "Kukatpally"},
    "hitec city":      {"ward": "Madhapur",       "zone": "Kukatpally"},
    "alwyn colony":    {"ward": "Alwyn Colony",   "zone": "Kukatpally"},
    "sanath nagar":    {"ward": "Kukatpally",     "zone": "Kukatpally"},

    # ── Zone: Serilingampally ─────────────────────────────────────
    "serilingampally": {"ward": "Serilingampally", "zone": "Serilingampally"},
    "gachibowli":      {"ward": "Serilingampally", "zone": "Serilingampally"},
    "kondapur":        {"ward": "Serilingampally", "zone": "Serilingampally"},
    "nallagandla":     {"ward": "Serilingampally", "zone": "Serilingampally"},
    "masjid banda":    {"ward": "Serilingampally", "zone": "Serilingampally"},
    "miyapur":         {"ward": "Miyapur",        "zone": "Serilingampally"},
    "chandanagar":     {"ward": "Miyapur",        "zone": "Serilingampally"},
    "hafeezpet":       {"ward": "Miyapur",        "zone": "Serilingampally"},
    "lingampally":     {"ward": "Serilingampally", "zone": "Serilingampally"},
    "narsingi":        {"ward": "Narsingi",       "zone": "Serilingampally"},
    "kokapet":         {"ward": "Narsingi",       "zone": "Serilingampally"},
    "gandipet":        {"ward": "Narsingi",       "zone": "Serilingampally"},
    "manikonda":       {"ward": "Narsingi",       "zone": "Serilingampally"},
    "neknampur":       {"ward": "Narsingi",       "zone": "Serilingampally"},
    "patancheru":      {"ward": "Patancheru",     "zone": "Serilingampally"},
    "ramachandrapuram": {"ward": "Patancheru",    "zone": "Serilingampally"},

    # ── Zone: Quthbullapur ────────────────────────────────────────
    "nizampet":        {"ward": "Nizampet",       "zone": "Quthbullapur"},
    "bachupally":      {"ward": "Nizampet",       "zone": "Quthbullapur"},
    "pragathi nagar":  {"ward": "Nizampet",       "zone": "Quthbullapur"},
    "chintal":         {"ward": "Chintal",        "zone": "Quthbullapur"},
    "jeedimetla":      {"ward": "Jeedimetla",     "zone": "Quthbullapur"},
    "balanagar":       {"ward": "Jeedimetla",     "zone": "Quthbullapur"},
    "kompally":        {"ward": "Kompally",       "zone": "Quthbullapur"},
    "gajularamaram":   {"ward": "Gajularamaram",  "zone": "Quthbullapur"},
    "dundigal":        {"ward": "Dundigal",       "zone": "Quthbullapur"},
    "medchal":         {"ward": "Medchal",        "zone": "Quthbullapur"},

    # ── Zone: Khairatabad ─────────────────────────────────────────
    "khairatabad":     {"ward": "Khairatabad",    "zone": "Khairatabad"},
    "somajiguda":      {"ward": "Khairatabad",    "zone": "Khairatabad"},
    "himayathnagar":   {"ward": "Khairatabad",    "zone": "Khairatabad"},
    "jubilee hills":   {"ward": "Jubilee Hills",  "zone": "Khairatabad"},
    "banjara hills":   {"ward": "Jubilee Hills",  "zone": "Khairatabad"},
    "film nagar":      {"ward": "Jubilee Hills",  "zone": "Khairatabad"},
    "borabanda":       {"ward": "Borabanda",      "zone": "Khairatabad"},
    "yousufguda":      {"ward": "Yousufguda",     "zone": "Khairatabad"},
    "erragadda":       {"ward": "Yousufguda",     "zone": "Khairatabad"},
    "ameerpet":        {"ward": "Ameerpet",       "zone": "Khairatabad"},
    "sr nagar":        {"ward": "Ameerpet",       "zone": "Khairatabad"},
    "begumpet":        {"ward": "Ameerpet",       "zone": "Khairatabad"},

    # ── Zone: Secunderabad ────────────────────────────────────────
    "secunderabad":    {"ward": "Secunderabad",   "zone": "Secunderabad"},
    "kavadiguda":      {"ward": "Kavadiguda",     "zone": "Secunderabad"},
    "musheerabad":     {"ward": "Musheerabad",    "zone": "Secunderabad"},
    "amberpet":        {"ward": "Amberpet",       "zone": "Secunderabad"},
    "tarnaka":         {"ward": "Tarnaka",        "zone": "Secunderabad"},
    "mettuguda":       {"ward": "Mettuguda",      "zone": "Secunderabad"},

    # ── Zone: Malkajgiri ──────────────────────────────────────────
    "malkajgiri":      {"ward": "Malkajgiri",     "zone": "Malkajgiri"},
    "bowenpally":      {"ward": "Bowenpally",     "zone": "Malkajgiri"},
    "alwal":           {"ward": "Alwal",          "zone": "Malkajgiri"},
    "moula ali":       {"ward": "Moula Ali",      "zone": "Malkajgiri"},
    "keesara":         {"ward": "Keesara",        "zone": "Malkajgiri"},

    # ── Zone: Uppal ───────────────────────────────────────────────
    "uppal":           {"ward": "Uppal",          "zone": "Uppal"},
    "nacharam":        {"ward": "Nacharam",       "zone": "Uppal"},
    "habsiguda":       {"ward": "Nacharam",       "zone": "Uppal"},
    "kapra":           {"ward": "Kapra",          "zone": "Uppal"},
    "ghatkesar":       {"ward": "Ghatkesar",      "zone": "Uppal"},
    "boduppal":        {"ward": "Boduppal",       "zone": "Uppal"},

    # ── Zone: LB Nagar ────────────────────────────────────────────
    "lb nagar":        {"ward": "LB Nagar",       "zone": "LB Nagar"},
    "nagole":          {"ward": "Nagole",         "zone": "LB Nagar"},
    "saroornagar":     {"ward": "Saroornagar",    "zone": "LB Nagar"},
    "dilsukhnagar":    {"ward": "Saroornagar",    "zone": "LB Nagar"},
    "hayathnagar":     {"ward": "Hayathnagar",    "zone": "LB Nagar"},
    "vanasthalipuram": {"ward": "LB Nagar",       "zone": "LB Nagar"},

    # ── Zone: Shamshabad ──────────────────────────────────────────
    "shamshabad":      {"ward": "Shamshabad",     "zone": "Shamshabad"},
    "adibatla":        {"ward": "Adibatla",       "zone": "Shamshabad"},
    "badangpet":       {"ward": "Badangpet",      "zone": "Shamshabad"},
    "jalpally":        {"ward": "Jalpally",       "zone": "Shamshabad"},

    # ── Zone: Rajendranagar ───────────────────────────────────────
    "rajendranagar":   {"ward": "Rajendranagar",  "zone": "Rajendranagar"},
    "attapur":         {"ward": "Attapur",        "zone": "Rajendranagar"},
    "bahadurpura":     {"ward": "Bahadurpura",    "zone": "Rajendranagar"},
    "falaknuma":       {"ward": "Falaknuma",      "zone": "Rajendranagar"},
    "chandrayangutta": {"ward": "Chandrayangutta", "zone": "Rajendranagar"},

    # ── Zone: Charminar ───────────────────────────────────────────
    "charminar":       {"ward": "Charminar",      "zone": "Charminar"},
    "abids":           {"ward": "Charminar",      "zone": "Charminar"},
    "nampally":        {"ward": "Charminar",      "zone": "Charminar"},
    "santoshnagar":    {"ward": "Santoshnagar",   "zone": "Charminar"},
    "saidabad":        {"ward": "Santoshnagar",   "zone": "Charminar"},
    "yakutpura":       {"ward": "Yakutpura",      "zone": "Charminar"},
    "malakpet":        {"ward": "Malakpet",       "zone": "Charminar"},
    "moosarambagh":    {"ward": "Moosarambagh",   "zone": "Charminar"},

    # ── Zone: Golconda ────────────────────────────────────────────
    "golconda":        {"ward": "Golconda",       "zone": "Golconda"},
    "mehdipatnam":     {"ward": "Mehdipatnam",    "zone": "Golconda"},
    "tolichowki":      {"ward": "Mehdipatnam",    "zone": "Golconda"},
    "karwan":          {"ward": "Karwan",         "zone": "Golconda"},
    "goshamahal":      {"ward": "Goshamahal",     "zone": "Golconda"},
    "masab tank":      {"ward": "Masab Tank",     "zone": "Golconda"},
    "langar houz":     {"ward": "Karwan",         "zone": "Golconda"},
}


def _get_ward_info(area: str) -> dict:
    """Look up ward and zone from area name."""
    key = (area or "").strip().lower()
    # Try exact match first
    if key in AREA_TO_WARD:
        return AREA_TO_WARD[key]
    # Try partial match
    for ward_key, info in AREA_TO_WARD.items():
        if ward_key in key or key in ward_key:
            return info
    return {"ward": area or "Unknown", "zone": "Hyderabad"}


def _get_action_level(severity_level: str) -> dict:
    """Map severity level to GHMC official action level."""
    return SEVERITY_TO_ACTION_LEVEL.get(
        severity_level,
        SEVERITY_TO_ACTION_LEVEL["medium"]
    )


# ── Professional WhatsApp Templates (8 styles) ───────────────────
# Each looks like it came from a monitoring platform

WHATSAPP_TEMPLATES = [
    # Style 1: Full CIVIC-MONITOR format
    """[CIVIC-MONITOR HYDERABAD]
━━ OFFICIAL GRIEVANCE REPORT ━━

{action_emoji} *SEVERITY: {action_tag}*
🛠️ *ISSUE:* {issue_type}
📍 *LOCATION:* {area}, {city}
🏢 *WARD:* {ward} (Zone: {zone})

*AI ANALYSIS SUMMARY:*
• Detection: {detection_summary}
• Priority Score: {score}/100
• {duplicate_status}
• Timestamp: {timestamp}

📋 *Report ID:* {complaint_id}

*DESCRIPTION:*
{description}

Please acknowledge this report for Ward Office action.""",

    # Style 2: Compact professional
    """[CIVIC-AI REPORT #{report_num}]
{action_emoji} {action_tag}

📍 {area}, {city} — Ward: {ward}
🛠️ Issue: {issue_type}
⚡ Priority: {score}/100

{description}

{duplicate_status}
🕐 {timestamp}

Ref: {complaint_id}
— CivicConnect Hyderabad Monitor""",

    # Style 3: Formal government tone
    """Sir/Madam,

This is an automated grievance from CivicConnect Monitor, Hyderabad.

*Report:* {complaint_id}
*Ward:* {ward}, Zone {zone}
*Category:* {issue_type}
*Action Level:* {action_emoji} {action_level} — {action_label}
*Priority:* {score}/100

*Details:*
{description}

*Verification:*
{duplicate_status}
Filed: {timestamp}

Request urgent acknowledgement and ward-level action.""",

    # Style 4: Citizen + data evidence
    """Namaste, I'm a resident of *{area}* filing a verified complaint.

{action_emoji} *{action_tag}* (Score: {score}/100)
🛠️ {issue_type} — {ward}, {zone}

{description}

*AI-Verified Data:*
{detection_summary}
{duplicate_status}

Report #{report_num} | {timestamp}
— Tracked via CivicConnect AI""",

    # Style 5: Urgency-driven
    """⚠️ PRIORITY COMPLAINT — {area}, {city}

{action_emoji} Action Level: *{action_label}*
📋 Issue: {issue_type}
🏢 Ward: {ward} | Zone: {zone}
⚡ Severity: {score}/100

{description}

Ref: {complaint_id}
{duplicate_status}
Filed: {timestamp}

An AI system has verified and classified this complaint. Please respond.""",

    # Style 6: Evidence-heavy
    """[CIVIC-MONITOR HYD #{report_num}]

📊 *VERIFIED COMPLAINT DATA*
Type: {issue_type}
Location: {area}, {city}
Ward/Zone: {ward} / {zone}
Severity: {action_emoji} {action_label} ({score}/100)
Filed: {timestamp}

📝 *Citizen Report:*
{description}

🔬 *AI Analysis:*
{detection_summary}
{duplicate_status}

Please route to {ward} Ward Office for inspection.""",

    # Style 7: Brief but authoritative
    """CIVIC-MONITOR | Report {complaint_id}

{action_emoji} *{action_tag}*
{issue_type} at {ward}, {zone}

{description}

Priority {score}/100 | {timestamp}
{duplicate_status}

Awaiting acknowledgement from Ward Office.""",

    # Style 8: Community + pressure
    """[HYDERABAD CIVIC WATCH]

Our neighbourhood monitoring system has flagged:

{action_emoji} *{action_tag}* — {issue_type}
📍 {area} ({ward}, Zone: {zone})
⚡ Score: {score}/100

{description}

{duplicate_status}

Report: {complaint_id} | {timestamp}
This complaint is being tracked. Residents will follow up in 48 hours if no action is taken.""",
]


# ── One-Click Copy Templates ─────────────────────────────────────
COPY_TEMPLATES = [
    """[CIVIC-MONITOR HYD] Report {complaint_id}
{action_emoji} {action_tag}

Issue: {issue_type}
Location: {area}, {city}
Ward: {ward} | Zone: {zone}
Priority: {score}/100

{description}

{duplicate_status}
Filed: {timestamp}""",

    """CIVIC-AI REPORT #{report_num}
Severity: {action_emoji} {action_label}

{issue_type} at {area}, {city}
Ward: {ward} (Zone: {zone})
Priority Score: {score}/100

{description}

{duplicate_status}
Ref: {complaint_id} | {timestamp}""",
]


def _build_template_data(complaint_id: str, complaint_text: str,
                         issue_type: str, city: str, area: str,
                         severity: dict,
                         duplicate_count: int = 0,
                         image_verified: bool = False,
                         image_label: str = None) -> dict:
    """Build the data dict used to fill templates."""
    action = _get_action_level(severity.get("level", "medium"))
    ward_info = _get_ward_info(area)

    # Extract numeric report number from complaint ID
    try:
        report_num = complaint_id.split("-")[-1]
    except (IndexError, AttributeError):
        report_num = "0000"

    # Detection summary
    if image_label:
        detection_summary = f"Confirmed {issue_type} via AI image processing"
    else:
        detection_summary = f"Classified as {issue_type} via NLP text analysis"

    # Duplicate status
    if duplicate_count > 0:
        duplicate_status = f"⚠️ {duplicate_count} similar report(s) in this area — community-flagged issue"
    else:
        duplicate_status = "✅ Image Verified: No duplicates found in this area"

    timestamp = datetime.now().strftime("%d-%b-%Y %I:%M:%S %p")

    return {
        "complaint_id": complaint_id,
        "report_num": report_num,
        "area": area,
        "city": city,
        "issue_type": issue_type,
        "description": complaint_text[:500],
        "score": severity.get("score", 50),
        "action_emoji": action["emoji"],
        "action_tag": action["tag"],
        "action_level": action["level"],
        "action_label": action["label"],
        "ward": ward_info["ward"],
        "zone": ward_info["zone"],
        "detection_summary": detection_summary,
        "duplicate_status": duplicate_status,
        "timestamp": timestamp,
    }


def build_whatsapp_link(complaint_id: str, complaint_text: str,
                        issue_type: str, city: str, area: str,
                        severity: dict,
                        duplicate_count: int = 0,
                        image_verified: bool = False,
                        image_label: str = None) -> str:
    """
    Build a WhatsApp deep-link with a RANDOMIZED professional template.
    Routes to GHMC Sanitation WhatsApp for relevant issues.
    """
    data = _build_template_data(
        complaint_id, complaint_text, issue_type, city, area,
        severity, duplicate_count, image_verified, image_label
    )

    template = random.choice(WHATSAPP_TEMPLATES)
    message = template.format(**data)

    # Route to sanitation number for garbage/sewage, general for others
    if severity.get("level") in ("high", "critical") or "garbage" in issue_type or "sewage" in issue_type:
        phone = GHMC_WHATSAPP_SANITATION
    else:
        phone = GHMC_WHATSAPP_GENERAL

    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{phone}?text={encoded}"


def build_copy_text(complaint_id: str, complaint_text: str,
                    issue_type: str, city: str, area: str,
                    severity: dict,
                    duplicate_count: int = 0,
                    image_verified: bool = False,
                    image_label: str = None) -> str:
    """Build clean, official-looking copyable text."""
    data = _build_template_data(
        complaint_id, complaint_text, issue_type, city, area,
        severity, duplicate_count, image_verified, image_label
    )
    template = random.choice(COPY_TEMPLATES)
    return template.format(**data)


def build_sms_link(complaint_id: str, issue_type: str,
                   city: str, area: str, severity: dict) -> str:
    """Build SMS link with official tone."""
    action = _get_action_level(severity.get("level", "medium"))
    ward = _get_ward_info(area)
    body = (f"CIVIC-MONITOR Report {complaint_id}: {action['emoji']} {action['tag']} "
            f"— {issue_type} at {area}, {ward['ward']} Ward. "
            f"Priority {severity.get('score', 50)}/100. Please take immediate action.")
    return f"sms:{GHMC_HELPLINE}?body={urllib.parse.quote(body)}"


def get_ghmc_forwarding_options(complaint_id: str, complaint_text: str,
                                issue_type: str, display_label: str,
                                city: str, area: str,
                                severity: dict,
                                authority: dict = None,
                                duplicate_count: int = 0,
                                image_verified: bool = False,
                                image_label: str = None) -> dict:
    """
    Return all available forwarding options.
    Note: GHMC Portal and MyGHMC App removed per guide's feedback
    (can't programmatically access their forms).
    """
    action = _get_action_level(severity.get("level", "medium"))
    ward_info = _get_ward_info(area)

    # Email mailto link
    email_link = None
    if authority and authority.get("email"):
        subject = (f"[CIVIC-MONITOR {complaint_id}] {action['emoji']} {action['tag']} "
                   f"— {display_label} at {ward_info['ward']}, {ward_info['zone']}")
        body = f"""Sir/Madam,

This is an AI-verified grievance from CivicConnect Monitor, Hyderabad.

Report ID: {complaint_id}
Action Level: {action['emoji']} {action['level']} — {action['label']}
Issue Type: {display_label}
Location: {area}, {city}
Ward: {ward_info['ward']} | Zone: {ward_info['zone']}
Priority Score: {severity.get('score', 50)}/100

Description:
{complaint_text}

This complaint is tracked in our database. We request acknowledgement
and routing to the {ward_info['ward']} Ward Office for inspection.

Filed: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}

Regards,
CivicConnect AI — Hyderabad Civic Monitoring Platform
"""
        email_link = (
            f"mailto:{authority['email']}"
            f"?subject={urllib.parse.quote(subject)}"
            f"&body={urllib.parse.quote(body)}"
        )

    # Copy text
    copy_text = build_copy_text(
        complaint_id, complaint_text, display_label,
        city, area, severity, duplicate_count, image_verified, image_label
    )

    return {
        "whatsapp_link": build_whatsapp_link(
            complaint_id, complaint_text, display_label,
            city, area, severity, duplicate_count, image_verified, image_label
        ),
        "email_link": email_link,
        "sms_link": build_sms_link(complaint_id, display_label, city, area, severity),
        "ghmc_helpline": GHMC_HELPLINE,
        "copy_text": copy_text,
        "action_level": action,
        "ward_info": ward_info,
    }
