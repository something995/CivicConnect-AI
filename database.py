"""SQLite database for storing and tracking civic complaints."""

import sqlite3
import uuid
import logging
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent / "complaints.db"


def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _hash_password(password: str) -> str:
    """Simple SHA-256 hash for passwords (sufficient for demo/academic project)."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    """Create the complaints and admin_users tables if they don't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id              TEXT PRIMARY KEY,
            created_at      TEXT NOT NULL,
            city            TEXT NOT NULL,
            area            TEXT NOT NULL,
            complaint_text  TEXT NOT NULL,
            issue_type      TEXT NOT NULL,
            display_label   TEXT NOT NULL,
            severity        TEXT NOT NULL DEFAULT 'medium',
            severity_score  INTEGER NOT NULL DEFAULT 50,
            status          TEXT NOT NULL DEFAULT 'submitted',
            image_url       TEXT,
            image_label     TEXT,
            image_confidence REAL,
            authority_dept  TEXT,
            authority_phone TEXT,
            authority_email TEXT,
            emailed         INTEGER NOT NULL DEFAULT 0,
            forwarded_at    TEXT,
            escalation_due  TEXT,
            response_notes  TEXT,
            resolved_at     TEXT,
            community_verified INTEGER NOT NULL DEFAULT 0,
            assigned_to     TEXT,
            assigned_at     TEXT,
            gps_lat         REAL,
            gps_lng         REAL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id          TEXT PRIMARY KEY,
            username    TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            full_name   TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'field_worker',
            zone        TEXT,
            created_at  TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS field_inspections (
            id              TEXT PRIMARY KEY,
            created_at      TEXT NOT NULL,
            inspector_id    TEXT NOT NULL,
            inspector_name  TEXT NOT NULL,
            latitude        REAL,
            longitude       REAL,
            address         TEXT,
            notes           TEXT,
            image_url       TEXT,
            issue_type      TEXT NOT NULL DEFAULT 'others',
            display_label   TEXT NOT NULL DEFAULT 'Other',
            severity        TEXT NOT NULL DEFAULT 'medium',
            severity_score  INTEGER NOT NULL DEFAULT 50,
            image_label     TEXT,
            image_confidence REAL,
            status          TEXT NOT NULL DEFAULT 'identified',
            resolved_at     TEXT,
            FOREIGN KEY (inspector_id) REFERENCES admin_users(id)
        )
    """)

    conn.commit()

    # Add columns if missing (for existing databases)
    for col, coltype in [
        ("forwarded_at", "TEXT"),
        ("escalation_due", "TEXT"),
        ("response_notes", "TEXT"),
        ("resolved_at", "TEXT"),
        ("community_verified", "INTEGER DEFAULT 0"),
        ("assigned_to", "TEXT"),
        ("assigned_at", "TEXT"),
        ("gps_lat", "REAL"),
        ("gps_lng", "REAL"),
    ]:
        try:
            conn = get_connection()
            conn.execute(f"ALTER TABLE complaints ADD COLUMN {col} {coltype}")
            conn.commit()
            conn.close()
        except Exception:
            pass  # Column already exists

    # Seed default admin accounts if none exist
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) as c FROM admin_users").fetchone()["c"]
    if count == 0:
        now = datetime.now().isoformat()
        default_admins = [
            ("ADM-001", "supervisor", _hash_password("admin123"),
             "GHMC Supervisor", "supervisor", None, now),
            ("ADM-002", "worker_khairatabad", _hash_password("field123"),
             "Field Worker — Khairatabad", "field_worker", "Khairatabad", now),
            ("ADM-003", "worker_kukatpally", _hash_password("field123"),
             "Field Worker — Kukatpally", "field_worker", "Kukatpally", now),
            ("ADM-004", "worker_charminar", _hash_password("field123"),
             "Field Worker — Charminar", "field_worker", "Charminar", now),
            ("ADM-005", "worker_secunderabad", _hash_password("field123"),
             "Field Worker — Secunderabad", "field_worker", "Secunderabad", now),
        ]
        conn.executemany(
            "INSERT OR IGNORE INTO admin_users VALUES (?, ?, ?, ?, ?, ?, ?)",
            default_admins
        )
        conn.commit()
        logger.info("🔐 Seeded %d default admin accounts", len(default_admins))

    conn.close()
    logger.info("✅ Database initialised at %s", DB_PATH)


# ── Admin Auth ──────────────────────────────────────────────────────

def authenticate_admin(username: str, password: str) -> dict | None:
    """Verify admin credentials. Returns user dict or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM admin_users WHERE username = ? AND password = ?",
        (username, _hash_password(password))
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_admin_user(user_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM admin_users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_workers() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM admin_users WHERE role = 'field_worker' ORDER BY zone"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Complaint Assignment ────────────────────────────────────────────

def assign_complaint(complaint_id: str, worker_id: str):
    """Assign a complaint to a field worker."""
    conn = get_connection()
    conn.execute(
        """UPDATE complaints SET assigned_to = ?, assigned_at = ?, status = 'in_progress'
           WHERE id = ?""",
        (worker_id, datetime.now().isoformat(), complaint_id)
    )
    conn.commit()
    conn.close()


def get_complaints_by_zone(zone: str) -> list:
    """Get all complaints in a specific zone (for field workers)."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM complaints WHERE area IN (
            SELECT DISTINCT area FROM complaints
        ) ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
            END,
            created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_complaints_for_worker(worker_id: str) -> list:
    """Get complaints assigned to a specific worker."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM complaints WHERE assigned_to = ? ORDER BY created_at DESC",
        (worker_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_admin_stats() -> dict:
    """Get admin-level statistics for the command center."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) as c FROM complaints").fetchone()["c"]
    pending = conn.execute(
        "SELECT COUNT(*) as c FROM complaints WHERE status IN ('submitted', 'forwarded')"
    ).fetchone()["c"]
    in_progress = conn.execute(
        "SELECT COUNT(*) as c FROM complaints WHERE status = 'in_progress'"
    ).fetchone()["c"]
    resolved = conn.execute(
        "SELECT COUNT(*) as c FROM complaints WHERE status = 'resolved'"
    ).fetchone()["c"]
    overdue = conn.execute(
        "SELECT COUNT(*) as c FROM complaints WHERE status = 'forwarded' AND escalation_due < ?",
        (datetime.now().isoformat(),)
    ).fetchone()["c"]

    by_severity = conn.execute("""
        SELECT severity, COUNT(*) as count FROM complaints GROUP BY severity
    """).fetchall()

    by_zone_area = conn.execute("""
        SELECT area, COUNT(*) as count, severity,
               AVG(severity_score) as avg_score
        FROM complaints GROUP BY area ORDER BY count DESC LIMIT 20
    """).fetchall()

    by_type = conn.execute("""
        SELECT issue_type, COUNT(*) as count FROM complaints
        GROUP BY issue_type ORDER BY count DESC
    """).fetchall()

    recent = conn.execute("""
        SELECT * FROM complaints ORDER BY created_at DESC LIMIT 50
    """).fetchall()

    workers = conn.execute("SELECT * FROM admin_users WHERE role = 'field_worker'").fetchall()

    conn.close()
    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "overdue": overdue,
        "by_severity": [dict(r) for r in by_severity],
        "by_zone_area": [dict(r) for r in by_zone_area],
        "by_type": [dict(r) for r in by_type],
        "recent": [dict(r) for r in recent],
        "workers": [dict(r) for r in workers],
    }


def generate_complaint_id() -> str:
    """
    Generate an official-looking complaint ID like HYD-VIGIL-1029.
    Uses sequential numbering to look like a professional monitoring platform.
    """
    conn = get_connection()
    # Get current max numeric suffix
    row = conn.execute("""
        SELECT id FROM complaints
        WHERE id LIKE 'HYD-VIGIL-%'
        ORDER BY CAST(SUBSTR(id, 11) AS INTEGER) DESC
        LIMIT 1
    """).fetchone()
    conn.close()

    if row:
        try:
            last_num = int(row["id"].split("-")[-1])
        except (ValueError, IndexError):
            last_num = 1000
    else:
        last_num = 1000  # Start from 1001

    return f"HYD-VIGIL-{last_num + 1}"


def save_complaint(data: dict) -> str:
    """Insert a new complaint and return the complaint ID."""
    complaint_id = generate_complaint_id()
    conn = get_connection()
    conn.execute("""
        INSERT INTO complaints (
            id, created_at, city, area, complaint_text, issue_type,
            display_label, severity, severity_score, status,
            image_url, image_label, image_confidence,
            authority_dept, authority_phone, authority_email,
            gps_lat, gps_lng
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        complaint_id,
        datetime.now().isoformat(),
        data.get("city", ""),
        data.get("area", ""),
        data.get("complaint_text", ""),
        data.get("issue_type", "others"),
        data.get("display_label", "Other"),
        data.get("severity", "medium"),
        data.get("severity_score", 50),
        "submitted",
        data.get("image_url"),
        data.get("image_label"),
        data.get("image_confidence"),
        data.get("authority_dept"),
        data.get("authority_phone"),
        data.get("authority_email"),
        data.get("gps_lat"),
        data.get("gps_lng"),
    ))
    conn.commit()
    conn.close()
    logger.info("💾 Complaint saved: %s", complaint_id)
    return complaint_id


def get_complaint(complaint_id: str):
    """Retrieve a single complaint by ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM complaints WHERE id = ?", (complaint_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_status(complaint_id: str, status: str, notes: str = None):
    """Update complaint status. If resolving, record timestamp."""
    conn = get_connection()
    if status == "resolved":
        conn.execute(
            "UPDATE complaints SET status = ?, response_notes = ?, resolved_at = ? WHERE id = ?",
            (status, notes, datetime.now().isoformat(), complaint_id)
        )
    else:
        conn.execute(
            "UPDATE complaints SET status = ?, response_notes = ? WHERE id = ?",
            (status, notes, complaint_id)
        )
    conn.commit()
    conn.close()


def mark_forwarded(complaint_id: str):
    """Mark complaint as forwarded. Sets 48-hour escalation timer."""
    now = datetime.now()
    escalation = now + timedelta(hours=48)
    conn = get_connection()
    conn.execute(
        """UPDATE complaints
           SET emailed = 1, status = 'forwarded',
               forwarded_at = ?, escalation_due = ?
           WHERE id = ?""",
        (now.isoformat(), escalation.isoformat(), complaint_id)
    )
    conn.commit()
    conn.close()


def mark_emailed(complaint_id: str):
    """Alias for backward compatibility."""
    mark_forwarded(complaint_id)


def community_verify(complaint_id: str):
    """Increment community verification count."""
    conn = get_connection()
    conn.execute(
        "UPDATE complaints SET community_verified = community_verified + 1 WHERE id = ?",
        (complaint_id,)
    )
    conn.commit()
    conn.close()


def get_escalation_status(complaint: dict) -> dict:
    """
    Calculate escalation status for a complaint.
    Returns: {"is_overdue": bool, "hours_remaining": float, "hours_elapsed": float, "label": str}
    """
    if complaint.get("status") == "resolved":
        return {"is_overdue": False, "hours_remaining": 0, "hours_elapsed": 0, "label": "Resolved"}

    if not complaint.get("escalation_due"):
        if not complaint.get("forwarded_at"):
            return {"is_overdue": False, "hours_remaining": 0, "hours_elapsed": 0, "label": "Not Yet Forwarded"}
        # No escalation set — treat forwarded_at + 48h as deadline
        forwarded = datetime.fromisoformat(complaint["forwarded_at"])
        deadline = forwarded + timedelta(hours=48)
    else:
        deadline = datetime.fromisoformat(complaint["escalation_due"])
        forwarded = datetime.fromisoformat(complaint.get("forwarded_at", complaint["created_at"]))

    now = datetime.now()
    hours_elapsed = (now - forwarded).total_seconds() / 3600
    hours_remaining = (deadline - now).total_seconds() / 3600
    is_overdue = hours_remaining <= 0

    if is_overdue:
        label = f"⚠️ OVERDUE by {abs(hours_remaining):.0f}h — Follow up now!"
    elif hours_remaining <= 12:
        label = f"⏰ {hours_remaining:.0f}h remaining — Escalation soon"
    else:
        label = f"🕐 {hours_remaining:.0f}h remaining"

    return {
        "is_overdue": is_overdue,
        "hours_remaining": hours_remaining,
        "hours_elapsed": hours_elapsed,
        "label": label,
    }


def get_recent_complaints(limit: int = 50):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM complaints ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stats():
    """Return aggregate statistics for the dashboard."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) as c FROM complaints").fetchone()["c"]

    by_type = conn.execute("""
        SELECT issue_type, COUNT(*) as count
        FROM complaints GROUP BY issue_type ORDER BY count DESC
    """).fetchall()

    by_area = conn.execute("""
        SELECT area, COUNT(*) as count
        FROM complaints GROUP BY area ORDER BY count DESC LIMIT 15
    """).fetchall()

    by_severity = conn.execute("""
        SELECT severity, COUNT(*) as count
        FROM complaints GROUP BY severity
    """).fetchall()

    by_status = conn.execute("""
        SELECT status, COUNT(*) as count
        FROM complaints GROUP BY status
    """).fetchall()

    by_date = conn.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM complaints GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 30
    """).fetchall()

    conn.close()

    return {
        "total": total,
        "by_type": [dict(r) for r in by_type],
        "by_area": [dict(r) for r in by_area],
        "by_severity": [dict(r) for r in by_severity],
        "by_status": [dict(r) for r in by_status],
        "by_date": [dict(r) for r in by_date],
    }


# ── Field Inspections ──────────────────────────────────────────────

def generate_inspection_id() -> str:
    """Generate an ID like FLD-INS-0001."""
    conn = get_connection()
    row = conn.execute("""
        SELECT id FROM field_inspections
        WHERE id LIKE 'FLD-INS-%'
        ORDER BY CAST(SUBSTR(id, 9) AS INTEGER) DESC
        LIMIT 1
    """).fetchone()
    conn.close()

    if row:
        try:
            last_num = int(row["id"].split("-")[-1])
        except (ValueError, IndexError):
            last_num = 0
    else:
        last_num = 0

    return f"FLD-INS-{last_num + 1:04d}"


def save_field_inspection(data: dict) -> str:
    """Save a field inspection record and return the inspection ID."""
    inspection_id = generate_inspection_id()
    conn = get_connection()
    conn.execute("""
        INSERT INTO field_inspections (
            id, created_at, inspector_id, inspector_name,
            latitude, longitude, address, notes,
            image_url, issue_type, display_label,
            severity, severity_score,
            image_label, image_confidence, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        inspection_id,
        datetime.now().isoformat(),
        data.get("inspector_id", ""),
        data.get("inspector_name", ""),
        data.get("latitude"),
        data.get("longitude"),
        data.get("address", ""),
        data.get("notes", ""),
        data.get("image_url"),
        data.get("issue_type", "others"),
        data.get("display_label", "Other"),
        data.get("severity", "medium"),
        data.get("severity_score", 50),
        data.get("image_label"),
        data.get("image_confidence"),
        "identified",
    ))
    conn.commit()
    conn.close()
    logger.info("🔍 Field inspection saved: %s", inspection_id)
    return inspection_id


def get_field_inspection(inspection_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM field_inspections WHERE id = ?", (inspection_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_field_inspections(inspector_id: str = None, status: str = None, limit: int = 200) -> list:
    """Get field inspections with optional filters."""
    conn = get_connection()
    query = "SELECT * FROM field_inspections WHERE 1=1"
    params = []
    if inspector_id:
        query += " AND inspector_id = ?"
        params.append(inspector_id)
    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END, created_at DESC"
    query += " LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_field_inspection_stats() -> dict:
    """Get aggregate stats for field inspections."""
    conn = get_connection()

    total = conn.execute("SELECT COUNT(*) as c FROM field_inspections").fetchone()["c"]
    identified = conn.execute(
        "SELECT COUNT(*) as c FROM field_inspections WHERE status = 'identified'"
    ).fetchone()["c"]
    in_progress = conn.execute(
        "SELECT COUNT(*) as c FROM field_inspections WHERE status = 'in_progress'"
    ).fetchone()["c"]
    resolved = conn.execute(
        "SELECT COUNT(*) as c FROM field_inspections WHERE status = 'resolved'"
    ).fetchone()["c"]

    by_severity = conn.execute("""
        SELECT severity, COUNT(*) as count FROM field_inspections GROUP BY severity
    """).fetchall()

    by_type = conn.execute("""
        SELECT issue_type, COUNT(*) as count FROM field_inspections
        GROUP BY issue_type ORDER BY count DESC
    """).fetchall()

    # Group by approximate area (rounded lat/lng)
    by_area = conn.execute("""
        SELECT address, COUNT(*) as count, AVG(severity_score) as avg_score
        FROM field_inspections
        WHERE address IS NOT NULL AND address != ''
        GROUP BY address ORDER BY avg_score DESC LIMIT 20
    """).fetchall()

    recent = conn.execute("""
        SELECT * FROM field_inspections
        ORDER BY CASE severity
            WHEN 'critical' THEN 1 WHEN 'high' THEN 2
            WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END,
        created_at DESC LIMIT 100
    """).fetchall()

    conn.close()
    return {
        "total": total,
        "identified": identified,
        "in_progress": in_progress,
        "resolved": resolved,
        "by_severity": [dict(r) for r in by_severity],
        "by_type": [dict(r) for r in by_type],
        "by_area": [dict(r) for r in by_area],
        "recent": [dict(r) for r in recent],
    }


def update_inspection_status(inspection_id: str, status: str, notes: str = None):
    """Update a field inspection status."""
    conn = get_connection()
    if status == "resolved":
        conn.execute(
            "UPDATE field_inspections SET status = ?, resolved_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(), inspection_id)
        )
    else:
        conn.execute(
            "UPDATE field_inspections SET status = ? WHERE id = ?",
            (status, inspection_id)
        )
    conn.commit()
    conn.close()

