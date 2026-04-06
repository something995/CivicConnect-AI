from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, session
import pandas as pd
import joblib
from pathlib import Path
import os
import argparse
import logging
import urllib.parse

from database import (init_db, save_complaint, get_complaint,
                      get_recent_complaints, get_stats, mark_emailed,
                      update_status, community_verify, get_escalation_status,
                      authenticate_admin, get_admin_user, get_admin_stats,
                      assign_complaint, get_complaints_for_worker,
                      get_all_workers,
                      save_field_inspection, get_field_inspections,
                      get_field_inspection_stats, update_inspection_status)
from severity import compute_severity
from duplicate_detector import find_duplicates, get_duplicate_count, compute_phash, save_phash
from ghmc_integration import get_ghmc_forwarding_options

# ---------------------------------------------------------------------------
# App & config
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "civic-connect-dev-key")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODELS_DIR = BASE_DIR / "models"
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(message)s")
logger = logging.getLogger(__name__)

# Initialise database
init_db()

# ---------------------------------------------------------------------------
# Load datasets
# ---------------------------------------------------------------------------
try:
    authority_df = pd.read_csv(DATA_DIR / "authority_mapping.csv")
    logger.info("✅ authority_mapping.csv loaded  (%d rows)", len(authority_df))
except FileNotFoundError:
    authority_df = pd.DataFrame()
    logger.warning("⚠️  authority_mapping.csv not found")

try:
    solutions_df = pd.read_csv(DATA_DIR / "solution_knowledge_base.csv")
    logger.info("✅ solution_knowledge_base.csv loaded  (%d rows)", len(solutions_df))
except FileNotFoundError:
    solutions_df = pd.DataFrame()
    logger.warning("⚠️  solution_knowledge_base.csv not found")

# ---------------------------------------------------------------------------
# Load text model
# ---------------------------------------------------------------------------
text_model_path = MODELS_DIR / "text_model.joblib"
if text_model_path.exists():
    text_model = joblib.load(text_model_path)
    logger.info("✅ Text model loaded")
else:
    text_model = None
    logger.warning("⚠️  text_model.joblib not found")

# ---------------------------------------------------------------------------
# Load image model (optional)
# ---------------------------------------------------------------------------
image_model = None
try:
    from ultralytics import YOLO
    finetuned = BASE_DIR / "runs" / "classify" / "train" / "weights" / "best.pt"
    base_wt = MODELS_DIR / "yolov8n-cls.pt"
    if finetuned.exists():
        image_model = YOLO(str(finetuned))
        logger.info("✅ Image model loaded (fine-tuned)")
    elif base_wt.exists():
        image_model = YOLO(str(base_wt))
        logger.info("✅ Image model loaded (base)")
except ImportError:
    logger.warning("⚠️  ultralytics not installed")
except Exception as exc:
    logger.warning("⚠️  Image model error: %s", exc)

# ---------------------------------------------------------------------------
# Label maps
# ---------------------------------------------------------------------------
IMAGE_LABEL_MAP = {
    "pothole":             "pothole_road_damage",
    "garbage_dump":        "garbage",
    "streetlight_failure": "streetlight_or_electricity",
    "waterlogging":        "waterlogging",
    "Unlabeled":           "others",
}

DISPLAY_LABELS = {
    "pothole_road_damage":        "🕳️ Pothole / Road Damage",
    "garbage":                    "🗑️ Garbage / Solid Waste",
    "sewage_overflow":            "🚰 Sewage Overflow",
    "streetlight_or_electricity": "💡 Streetlight / Electricity",
    "waterlogging":               "🌊 Waterlogging / Flooding",
    "others":                     "📋 Other Civic Issue",
}

SEVERITY_COLORS = {
    "critical": "#ef4444",
    "high":     "#f59e0b",
    "medium":   "#3b82f6",
    "low":      "#10b981",
}

# If image model confidence is below this, prefer text classification
LOW_CONFIDENCE_THRESHOLD = 55.0

# Text keywords that override image classification when confidence is low
TEXT_OVERRIDE_KEYWORDS = {
    "sewage_overflow": [
        "sewage", "manhole", "drain", "sewer", "overflow", "gutter",
        "nala", "naala", "drainage", "septic", "waste water", "wastewater",
        "open drain", "clogged drain", "manhol", "sewage water",
        "dirty water flowing", "foul smell", "stinking water",
    ],
    "waterlogging": [
        "waterlogging", "water logging", "flooded", "flooding", "submerged",
        "water stagnant", "stagnant water", "water accumulated", "knee deep",
        "ankle deep", "rain water", "rainwater",
    ],
    "garbage": [
        "garbage", "trash", "rubbish", "waste dump", "littering",
        "solid waste", "pile of waste", "dumping", "debris",
    ],
    "streetlight_or_electricity": [
        "streetlight", "street light", "pole", "electric", "wire",
        "transformer", "no light", "dark road", "lamp post",
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def classify_text(text: str) -> str:
    if not text_model or not text or not text.strip():
        return "others"
    try:
        return text_model.predict([text])[0]
    except Exception:
        return "others"


def classify_image(image_path: str):
    if image_model is None:
        return None, None
    try:
        results = image_model(image_path)
        probs = results[0].probs
        raw = results[0].names[probs.top1]
        mapped = IMAGE_LABEL_MAP.get(raw, raw)
        conf = round(float(probs.top1conf) * 100, 1)
        return mapped, conf
    except Exception:
        return None, None


def fuse_classifications(text_label: str, image_label: str, image_confidence: float,
                         complaint_text: str) -> tuple:
    """
    Smart fusion of text + image classification.
    Returns (final_label, was_overridden: bool, override_reason: str)
    
    Rules:
    1. If image confidence >= threshold, trust image unless text strongly disagrees
    2. If image confidence < threshold, check text keywords for a better match
    3. If text keywords point to a specific issue the model can't detect (e.g. sewage),
       override the image classification
    """
    text_lower = (complaint_text or "").lower()
    override_reason = ""
    
    # If no image classification, just return text
    if not image_label:
        return text_label, False, ""
    
    # Check if text keywords strongly suggest a category different from image
    text_keyword_match = None
    match_count = 0
    for category, keywords in TEXT_OVERRIDE_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text_lower)
        if hits > match_count:
            match_count = hits
            text_keyword_match = category
    
    # Case 1: Image confidence is low — text keywords get priority
    if image_confidence is not None and image_confidence < LOW_CONFIDENCE_THRESHOLD:
        if text_keyword_match and text_keyword_match != image_label:
            override_reason = (f"Image prediction '{image_label}' had low confidence "
                             f"({image_confidence}%), text keywords suggest '{text_keyword_match}'")
            return text_keyword_match, True, override_reason
        # If text also uncertain, fall back to text model
        if text_label != "others" and text_label != image_label:
            override_reason = (f"Image had low confidence ({image_confidence}%), "
                             f"using text classification '{text_label}'")
            return text_label, True, override_reason
    
    # Case 2: Image says pothole/waterlogging but text strongly says sewage
    # (sewage_overflow is NOT in the image training set, so it can never be predicted)
    if text_keyword_match == "sewage_overflow" and match_count >= 2:
        if image_label in ("pothole_road_damage", "waterlogging", "others"):
            override_reason = (f"Text contains {match_count} sewage-related keywords, "
                             f"overriding image prediction '{image_label}'")
            return "sewage_overflow", True, override_reason
    
    # Case 3: High confidence image + matching or non-conflicting text → trust image
    return image_label, False, ""


def find_authority(city: str, area: str, issue_type: str):
    if authority_df.empty:
        return None
    df = authority_df.copy()
    df["city_lower"] = df["city"].str.lower()
    df["area_lower"] = df["area"].str.lower()
    cl = (city or "").strip().lower()
    al = (area or "").strip().lower()
    for mask in [
        (df["city_lower"] == cl) & (df["area_lower"] == al) & (df["issue_type"] == issue_type),
        (df["city_lower"] == cl) & (df["issue_type"] == issue_type),
        df["issue_type"] == issue_type,
    ]:
        result = df[mask]
        if not result.empty:
            return result.iloc[0].to_dict()
    return None


def get_solution(issue_type: str):
    if solutions_df.empty:
        return {"title": "General Advice",
                "citizen_steps": ["Contact your local municipality."],
                "authority_steps": ["Triage and route to correct department."]}
    row = solutions_df[solutions_df["issue_type"] == issue_type]
    if row.empty:
        row = solutions_df[solutions_df["issue_type"] == "others"]
    if row.empty:
        return {"title": "General Advice",
                "citizen_steps": ["Contact your local municipality."],
                "authority_steps": ["Triage and route to correct department."]}
    r = row.iloc[0]
    return {
        "title": r["title"],
        "citizen_steps": [s for s in str(r["citizen_steps"]).split("\n") if s.strip()],
        "authority_steps": [s for s in str(r["authority_steps"]).split("\n") if s.strip()],
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    complaint_text = request.form.get("complaint_text", "").strip()
    city = request.form.get("city", "").strip()
    area = request.form.get("area", "").strip()
    image = request.files.get("image")
    gps_lat = request.form.get("gps_lat", "").strip()
    gps_lng = request.form.get("gps_lng", "").strip()

    if not complaint_text and (not image or not image.filename):
        flash("Please enter a complaint or upload an image.", "error")
        return redirect(url_for("index"))

    # ── Text classification ────────────────────────────────────────
    raw_text_label = classify_text(complaint_text) if complaint_text else "others"

    # ── Image classification + pHash ─────────────────────────────
    image_label, image_confidence = None, None
    image_phash = None
    saved_image_url = None
    if image and image.filename:
        safe_name = image.filename.replace(" ", "_")
        image_path = str(UPLOAD_FOLDER / safe_name)
        image.save(image_path)
        saved_image_url = url_for("static", filename=f"uploads/{safe_name}")
        image_label, image_confidence = classify_image(image_path)
        image_phash = compute_phash(image_path)  # perceptual hash

    # ── Final label (smart fusion of text + image) ──────────────────
    final_label, was_overridden, override_reason = fuse_classifications(
        raw_text_label, image_label, image_confidence, complaint_text
    )
    if was_overridden:
        logger.info("🔄 Classification override: %s", override_reason)
    display_label = DISPLAY_LABELS.get(final_label, final_label.replace("_", " ").title())

    # ── Duplicate detection (text + location + pHash) ──────────────
    duplicates = find_duplicates(
        complaint_text, final_label, city, area,
        image_label=image_label,
        image_phash=image_phash
    )
    duplicate_count = get_duplicate_count(final_label, city, area)

    # ── Severity (now includes image + duplicate factors) ──────────
    severity = compute_severity(
        complaint_text, final_label,
        image_label=image_label,
        image_confidence=image_confidence,
        duplicate_count=duplicate_count
    )

    # ── Authority & solution ───────────────────────────────────────
    authority = find_authority(city, area, final_label)
    solution = get_solution(final_label)

    # ── Save to database ───────────────────────────────────────────
    complaint_id = save_complaint({
        "city": city,
        "area": area,
        "complaint_text": complaint_text,
        "issue_type": final_label,
        "display_label": display_label,
        "severity": severity["level"],
        "severity_score": severity["score"],
        "image_url": saved_image_url,
        "image_label": image_label,
        "image_confidence": image_confidence,
        "authority_dept": authority["department_name"] if authority else None,
        "authority_phone": authority["phone"] if authority else None,
        "authority_email": authority["email"] if authority else None,
        "gps_lat": float(gps_lat) if gps_lat else None,
        "gps_lng": float(gps_lng) if gps_lng else None,
    })

    # Save image pHash for future duplicate detection
    if image_phash:
        save_phash(complaint_id, image_phash)

    # ── GHMC forwarding options ────────────────────────────────────
    forwarding = get_ghmc_forwarding_options(
        complaint_id, complaint_text, final_label, display_label,
        city, area, severity, authority,
        duplicate_count=duplicate_count,
        image_verified=(image_phash is not None),
        image_label=image_label
    )

    logger.info(
        "Analyze  text=%s  img=%s  final=%s  severity=%s/%d  dups=%d  city=%s/%s  gps=%s,%s",
        raw_text_label, image_label, final_label,
        severity["level"], severity["score"], len(duplicates),
        city, area, gps_lat, gps_lng
    )

    return render_template(
        "result.html",
        complaint_id=complaint_id,
        complaint_text=complaint_text,
        issue_type=display_label,
        raw_issue_type=final_label,
        city=city,
        area=area,
        authority=authority,
        solution=solution,
        severity=severity,
        severity_color=SEVERITY_COLORS.get(severity["level"], "#3b82f6"),
        image_label=image_label,
        image_confidence=image_confidence,
        saved_image_url=saved_image_url,
        duplicates=duplicates,
        duplicate_count=duplicate_count,
        forwarding=forwarding,
    )


@app.route("/track", methods=["GET", "POST"])
def track():
    complaint = None
    search_id = ""
    escalation = None
    if request.method == "POST":
        search_id = request.form.get("complaint_id", "").strip()
        complaint = get_complaint(search_id)
        if complaint:
            escalation = get_escalation_status(complaint)
        else:
            flash(f"No complaint found with ID: {search_id}", "error")
    return render_template("tracker.html",
                           complaint=complaint,
                           search_id=search_id,
                           escalation=escalation,
                           severity_colors=SEVERITY_COLORS,
                           display_labels=DISPLAY_LABELS)


@app.route("/dashboard")
def dashboard():
    stats = get_stats()
    recent = get_recent_complaints(20)
    return render_template("dashboard.html",
                           stats=stats,
                           recent=recent,
                           severity_colors=SEVERITY_COLORS,
                           display_labels=DISPLAY_LABELS)


@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats())


@app.route("/api/complaint/<complaint_id>")
def api_complaint(complaint_id):
    """REST API endpoint for complaint data (future integration)."""
    c = get_complaint(complaint_id)
    if not c:
        return jsonify({"error": "not found"}), 404
    return jsonify(c)


@app.route("/email-sent/<complaint_id>")
def email_sent(complaint_id):
    mark_emailed(complaint_id)
    flash(f"Report {complaint_id} marked as forwarded. 48-hour escalation timer started.", "success")
    return redirect(url_for("track"))


@app.route("/update-status/<complaint_id>", methods=["POST"])
def update_complaint_status(complaint_id):
    """Let users update the status of their complaint."""
    new_status = request.form.get("status", "").strip()
    notes = request.form.get("notes", "").strip()
    valid_statuses = ["submitted", "forwarded", "acknowledged", "in_progress", "resolved", "no_response"]
    if new_status not in valid_statuses:
        flash("Invalid status.", "error")
        return redirect(url_for("track"))

    update_status(complaint_id, new_status, notes)
    status_labels = {
        "acknowledged": "🟢 GHMC has acknowledged your complaint!",
        "in_progress": "🟡 Work in progress — great news!",
        "resolved": "✅ Complaint resolved! Thank you for reporting.",
        "no_response": "🟠 Marked as no response. Consider escalating.",
    }
    msg = status_labels.get(new_status, f"Status updated to: {new_status}")
    flash(msg, "success")
    return redirect(url_for("track"))


@app.route("/community-verify/<complaint_id>", methods=["POST"])
def verify_complaint(complaint_id):
    """Let community members confirm an issue exists / is resolved."""
    community_verify(complaint_id)
    flash(f"👍 Thank you! Your verification for Report {complaint_id} has been recorded.", "success")
    return redirect(url_for("track"))


@app.route("/about")
def about():
    return render_template("about.html")


# ---------------------------------------------------------------------------
# Admin / GHMC Routes
# ---------------------------------------------------------------------------

def _require_admin():
    """Check if user is logged in as admin. Returns user dict or None."""
    user_id = session.get("admin_id")
    if not user_id:
        return None
    return get_admin_user(user_id)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate_admin(username, password)
        if user:
            session["admin_id"] = user["id"]
            session["admin_role"] = user["role"]
            session["admin_name"] = user["full_name"]
            session["admin_zone"] = user.get("zone")
            flash(f"Welcome, {user['full_name']}!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid credentials. Try again.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_role", None)
    session.pop("admin_name", None)
    session.pop("admin_zone", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("admin_login"))


@app.route("/admin")
@app.route("/admin/dashboard")
def admin_dashboard():
    user = _require_admin()
    if not user:
        flash("Please log in to access the GHMC Command Center.", "error")
        return redirect(url_for("admin_login"))

    stats = get_admin_stats()
    return render_template("admin_dashboard.html",
                           user=user,
                           stats=stats,
                           severity_colors=SEVERITY_COLORS,
                           display_labels=DISPLAY_LABELS)


@app.route("/admin/assign/<complaint_id>", methods=["POST"])
def admin_assign(complaint_id):
    user = _require_admin()
    if not user or user["role"] != "supervisor":
        flash("Only supervisors can assign complaints.", "error")
        return redirect(url_for("admin_dashboard"))

    worker_id = request.form.get("worker_id")
    if worker_id:
        assign_complaint(complaint_id, worker_id)
        flash(f"Complaint {complaint_id} assigned successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/update-status/<complaint_id>", methods=["POST"])
def admin_update_status(complaint_id):
    user = _require_admin()
    if not user:
        flash("Please log in.", "error")
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status", "").strip()
    notes = request.form.get("notes", "").strip()
    admin_note = f"[Updated by {user['full_name']}] {notes}"
    update_status(complaint_id, new_status, admin_note)
    flash(f"Report {complaint_id} → {new_status.replace('_', ' ').upper()}", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/api/admin/complaints")
def api_admin_complaints():
    """JSON API for heatmap and admin data."""
    user = _require_admin()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    complaints = get_recent_complaints(200)
    # Add coordinates for heatmap
    from ghmc_integration import _get_ward_info
    AREA_COORDS = {
        "kukatpally": [17.4849, 78.4138], "kphb": [17.4849, 78.4138],
        "miyapur": [17.4967, 78.3537], "gachibowli": [17.4401, 78.3489],
        "madhapur": [17.4484, 78.3908], "hitech city": [17.4486, 78.3736],
        "kondapur": [17.4576, 78.3563], "jubilee hills": [17.4325, 78.4070],
        "banjara hills": [17.4260, 78.4406], "ameerpet": [17.4375, 78.4483],
        "charminar": [17.3616, 78.4747], "abids": [17.3928, 78.4749],
        "secunderabad": [17.4399, 78.4983], "begumpet": [17.4439, 78.4665],
        "lb nagar": [17.3457, 78.5522], "dilsukhnagar": [17.3687, 78.5247],
        "uppal": [17.3961, 78.5597], "malkajgiri": [17.4527, 78.5273],
        "tarnaka": [17.4233, 78.5319], "habsiguda": [17.4127, 78.5289],
        "mehdipatnam": [17.3953, 78.4425], "tolichowki": [17.4014, 78.4166],
        "nampally": [17.3920, 78.4654], "somajiguda": [17.4280, 78.4560],
        "bowenpally": [17.4698, 78.4800], "alwal": [17.5056, 78.5186],
        "kompally": [17.5370, 78.4860], "nagole": [17.3696, 78.5580],
        "hayathnagar": [17.3318, 78.5818], "attapur": [17.3709, 78.4192],
        "shamshabad": [17.2456, 78.4258], "nizampet": [17.5148, 78.3867],
        "bachupally": [17.5240, 78.3716], "erragadda": [17.4520, 78.4315],
        "moosapet": [17.4690, 78.4261], "balanagar": [17.4802, 78.4419],
        "manikonda": [17.4038, 78.3812], "lingampally": [17.4862, 78.3194],
        "chandanagar": [17.4969, 78.3308], "falaknuma": [17.3405, 78.4644],
        "rajendranagar": [17.3176, 78.4127], "malakpet": [17.3750, 78.4971],
        "santoshnagar": [17.3637, 78.5072], "karwan": [17.3956, 78.4296],
        "golconda": [17.3833, 78.4011], "goshamahal": [17.3862, 78.4581],
    }

    result = []
    for c in complaints:
        area_key = (c.get("area") or "").strip().lower()
        coords = AREA_COORDS.get(area_key, [17.385, 78.4867])  # Default: Hyderabad center
        ward_info = _get_ward_info(c.get("area", ""))
        result.append({
            "id": c["id"],
            "area": c["area"],
            "city": c["city"],
            "issue_type": c["issue_type"],
            "display_label": c.get("display_label", c["issue_type"]),
            "severity": c["severity"],
            "severity_score": c["severity_score"],
            "status": c["status"],
            "created_at": c["created_at"],
            "lat": coords[0],
            "lng": coords[1],
            "ward": ward_info["ward"],
            "zone": ward_info["zone"],
        })
    return jsonify(result)


# ---------------------------------------------------------------------------
# Field Inspection Routes
# ---------------------------------------------------------------------------

@app.route("/admin/inspect", methods=["GET", "POST"])
def admin_inspect():
    """Field inspection: capture photo + GPS to log an issue."""
    user = _require_admin()
    if not user:
        flash("Please log in to access field inspection.", "error")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        image = request.files.get("image")
        latitude = request.form.get("latitude", "").strip()
        longitude = request.form.get("longitude", "").strip()
        address = request.form.get("address", "").strip()
        notes = request.form.get("notes", "").strip()

        if not image or not image.filename:
            flash("Please capture or upload a photo of the issue.", "error")
            return redirect(url_for("admin_inspect"))

        # Save image
        import time
        safe_name = f"inspect_{int(time.time())}_{image.filename.replace(' ', '_')}"
        image_path = str(UPLOAD_FOLDER / safe_name)
        image.save(image_path)
        saved_image_url = url_for("static", filename=f"uploads/{safe_name}")

        # Classify image + fuse with notes text
        image_label, image_confidence = classify_image(image_path)
        text_label = classify_text(notes) if notes else "others"
        final_label, was_overridden, override_reason = fuse_classifications(
            text_label, image_label, image_confidence, notes
        )
        if was_overridden:
            logger.info("🔄 Field inspection override: %s", override_reason)
        display_label = DISPLAY_LABELS.get(final_label, final_label.replace("_", " ").title())

        # Compute severity
        severity = compute_severity(
            notes, final_label,
            image_label=image_label,
            image_confidence=image_confidence,
            duplicate_count=0
        )

        # Save inspection
        inspection_id = save_field_inspection({
            "inspector_id": user["id"],
            "inspector_name": user["full_name"],
            "latitude": float(latitude) if latitude else None,
            "longitude": float(longitude) if longitude else None,
            "address": address,
            "notes": notes,
            "image_url": saved_image_url,
            "issue_type": final_label,
            "display_label": display_label,
            "severity": severity["level"],
            "severity_score": severity["score"],
            "image_label": image_label,
            "image_confidence": image_confidence,
        })

        logger.info(
            "Field inspection %s by %s at %s,%s — %s (%s)",
            inspection_id, user["full_name"], latitude, longitude,
            final_label, severity["level"]
        )
        flash(f"✅ Inspection {inspection_id} logged — {display_label} ({severity['level'].upper()})", "success")
        return redirect(url_for("admin_inspections"))

    return render_template("field_inspect.html", user=user)


@app.route("/admin/inspections")
def admin_inspections():
    """Dashboard showing all field inspections."""
    user = _require_admin()
    if not user:
        flash("Please log in.", "error")
        return redirect(url_for("admin_login"))

    stats = get_field_inspection_stats()
    return render_template("field_inspections_dashboard.html",
                           user=user,
                           stats=stats,
                           severity_colors=SEVERITY_COLORS,
                           display_labels=DISPLAY_LABELS)


@app.route("/admin/inspection-status/<inspection_id>", methods=["POST"])
def admin_inspection_update(inspection_id):
    user = _require_admin()
    if not user:
        flash("Please log in.", "error")
        return redirect(url_for("admin_login"))

    new_status = request.form.get("status", "").strip()
    update_inspection_status(inspection_id, new_status)
    flash(f"Inspection {inspection_id} → {new_status.replace('_', ' ').upper()}", "success")
    return redirect(url_for("admin_inspections"))


@app.route("/api/admin/inspections")
def api_admin_inspections():
    """JSON API for field inspection map data."""
    user = _require_admin()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    inspections = get_field_inspections()
    result = []
    for ins in inspections:
        result.append({
            "id": ins["id"],
            "latitude": ins.get("latitude"),
            "longitude": ins.get("longitude"),
            "address": ins.get("address", ""),
            "issue_type": ins["issue_type"],
            "display_label": ins.get("display_label", ins["issue_type"]),
            "severity": ins["severity"],
            "severity_score": ins["severity_score"],
            "status": ins["status"],
            "created_at": ins["created_at"],
            "inspector_name": ins.get("inspector_name", ""),
            "notes": ins.get("notes", ""),
            "image_url": ins.get("image_url", ""),
        })
    return jsonify(result)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("FLASK_RUN_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", os.environ.get("FLASK_RUN_PORT", 5000))))
    parser.add_argument("--debug", dest="debug", action="store_true")
    parser.add_argument("--no-debug", dest="debug", action="store_false")
    parser.set_defaults(debug=True)
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)
