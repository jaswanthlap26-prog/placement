import sqlite3
import os
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "tracker.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

# -----------------------------------------------------------------------------
# REST API ENDPOINTS
# -----------------------------------------------------------------------------

@app.route("/api/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Overall placement statistics
    cursor.execute("""
    SELECT 
        COUNT(DISTINCT s.student_id) AS total_students,
        COUNT(DISTINCT CASE WHEN s.placement_status IN ('Placed', 'Dream_Placed') THEN s.student_id END) AS total_placed,
        COUNT(DISTINCT CASE WHEN s.placement_status = 'Internship_Only' THEN s.student_id END) AS total_interns,
        COUNT(DISTINCT CASE WHEN s.placement_status = 'Unplaced' THEN s.student_id END) AS total_unplaced,
        ROUND((COUNT(DISTINCT CASE WHEN s.placement_status IN ('Placed', 'Dream_Placed') THEN s.student_id END) * 100.0) / 
              NULLIF(COUNT(DISTINCT s.student_id), 0), 1) AS placement_rate,
        ROUND(AVG(o.offered_ctc), 2) AS avg_ctc,
        MAX(o.offered_ctc) AS max_ctc
    FROM students s
    LEFT JOIN offers o ON s.student_id = o.student_id AND o.acceptance_status = 'Accepted';
    """)
    stats = dict(cursor.fetchone() or {})

    # Active drives count
    cursor.execute("SELECT COUNT(*) AS active_drives FROM drives WHERE status IN ('Registration_Open', 'Ongoing');")
    stats["active_drives"] = cursor.fetchone()["active_drives"]

    # Department breakdown
    cursor.execute("""
    SELECT 
        d.dept_code,
        d.dept_name,
        COUNT(s.student_id) AS total_students,
        COUNT(CASE WHEN s.placement_status IN ('Placed', 'Dream_Placed') THEN 1 END) AS placed,
        COUNT(CASE WHEN s.placement_status = 'Internship_Only' THEN 1 END) AS intern_only,
        ROUND(AVG(CASE WHEN o.acceptance_status = 'Accepted' THEN o.offered_ctc END), 2) AS avg_ctc
    FROM departments d
    LEFT JOIN students s ON d.dept_id = s.dept_id
    LEFT JOIN offers o ON s.student_id = o.student_id AND o.acceptance_status = 'Accepted'
    GROUP BY d.dept_id, d.dept_code, d.dept_name;
    """)
    stats["departments"] = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(stats)


@app.route("/api/students", methods=["GET"])
def get_students():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT s.*, d.dept_code, d.dept_name 
    FROM students s
    JOIN departments d ON s.dept_id = d.dept_id
    ORDER BY s.roll_no ASC;
    """)
    students = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(students)


@app.route("/api/drives", methods=["GET"])
def get_drives():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT dr.*, c.name AS company_name, c.company_tier, c.industry,
           GROUP_CONCAT(dept.dept_code, ', ') AS eligible_dept_codes,
           (SELECT COUNT(*) FROM registrations r WHERE r.drive_id = dr.drive_id) AS total_applicants
    FROM drives dr
    JOIN companies c ON dr.company_id = c.company_id
    LEFT JOIN drive_eligible_departments ded ON dr.drive_id = ded.drive_id
    LEFT JOIN departments dept ON ded.dept_id = dept.dept_id
    GROUP BY dr.drive_id
    ORDER BY dr.drive_id DESC;
    """)
    drives = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(drives)


@app.route("/api/drives/<int:drive_id>", methods=["GET"])
def get_drive_details(drive_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Drive info
    cursor.execute("""
    SELECT dr.*, c.name AS company_name, c.company_tier, c.industry, c.hr_name, c.hr_email
    FROM drives dr
    JOIN companies c ON dr.company_id = c.company_id
    WHERE dr.drive_id = ?;
    """, (drive_id,))
    drive = cursor.fetchone()
    if not drive:
        conn.close()
        return jsonify({"error": "Drive not found"}), 404
    drive_dict = dict(drive)

    # Rounds
    cursor.execute("""
    SELECT * FROM drive_rounds WHERE drive_id = ? ORDER BY round_number ASC;
    """, (drive_id,))
    drive_dict["rounds"] = [dict(r) for r in cursor.fetchall()]

    # Eligible depts
    cursor.execute("""
    SELECT d.dept_id, d.dept_code, d.dept_name 
    FROM drive_eligible_departments ded
    JOIN departments d ON ded.dept_id = d.dept_id
    WHERE ded.drive_id = ?;
    """, (drive_id,))
    drive_dict["departments"] = [dict(d) for d in cursor.fetchall()]

    conn.close()
    return jsonify(drive_dict)


@app.route("/api/student/<int:student_id>/eligibility", methods=["GET"])
def check_student_drives(student_id):
    """Returns all drives with real-time eligibility evaluation for a specific student."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM students WHERE student_id = ?;", (student_id,))
    student = cursor.fetchone()
    if not student:
        conn.close()
        return jsonify({"error": "Student not found"}), 404

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    SELECT dr.*, c.name AS company_name, c.company_tier,
           GROUP_CONCAT(dept.dept_code, ', ') AS eligible_dept_codes,
           (SELECT status FROM registrations r WHERE r.student_id = ? AND r.drive_id = dr.drive_id) AS registration_status,
           (SELECT registration_id FROM registrations r WHERE r.student_id = ? AND r.drive_id = dr.drive_id) AS registration_id
    FROM drives dr
    JOIN companies c ON dr.company_id = c.company_id
    LEFT JOIN drive_eligible_departments ded ON dr.drive_id = ded.drive_id
    LEFT JOIN departments dept ON ded.dept_id = dept.dept_id
    GROUP BY dr.drive_id
    ORDER BY dr.drive_id DESC;
    """, (student_id, student_id))
    
    rows = cursor.fetchall()
    drives_with_eligibility = []

    for r in rows:
        d = dict(r)
        reasons = []

        # Check deadline
        if d["reg_deadline"] < now_str:
            reasons.append("Registration deadline has passed")

        # Check CGPA
        if student["cgpa"] < d["min_cgpa"]:
            reasons.append(f"CGPA {student['cgpa']} is below requirement of {d['min_cgpa']}")

        # Check Backlogs
        if student["active_backlogs"] > d["max_backlogs"]:
            reasons.append(f"Student has {student['active_backlogs']} backlog(s); maximum allowed is {d['max_backlogs']}")

        # Check Batch
        if student["batch_year"] != d["eligible_batch_year"]:
            reasons.append(f"Batch {student['batch_year']} is not eligible (Required: {d['eligible_batch_year']})")

        # Check Department
        cursor.execute("SELECT 1 FROM drive_eligible_departments WHERE drive_id = ? AND dept_id = ?;", 
                       (d["drive_id"], student["dept_id"]))
        if not cursor.fetchone():
            reasons.append("Your department is not eligible for this drive")

        d["is_eligible"] = len(reasons) == 0
        d["eligibility_reasons"] = reasons
        drives_with_eligibility.append(d)

    conn.close()
    return jsonify(drives_with_eligibility)


@app.route("/api/register", methods=["POST"])
def register_student():
    data = request.json or {}
    student_id = data.get("student_id")
    drive_id = data.get("drive_id")

    if not student_id or not drive_id:
        return jsonify({"success": False, "message": "student_id and drive_id are required."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check student & drive
    cursor.execute("SELECT * FROM students WHERE student_id = ?;", (student_id,))
    student = cursor.fetchone()
    cursor.execute("SELECT * FROM drives WHERE drive_id = ?;", (drive_id,))
    drive = cursor.fetchone()

    if not student or not drive:
        conn.close()
        return jsonify({"success": False, "message": "Student or drive not found."}), 404

    # Check existing registration
    cursor.execute("SELECT * FROM registrations WHERE student_id = ? AND drive_id = ?;", (student_id, drive_id))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Already registered for this drive."}), 409

    # Validate rules
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if drive["reg_deadline"] < now_str:
        conn.close()
        return jsonify({"success": False, "message": "Registration deadline has expired."}), 400

    if student["cgpa"] < drive["min_cgpa"]:
        conn.close()
        return jsonify({"success": False, "message": f"CGPA {student['cgpa']} < Required {drive['min_cgpa']}"}), 400

    if student["active_backlogs"] > drive["max_backlogs"]:
        conn.close()
        return jsonify({"success": False, "message": f"Backlogs exceed limit ({drive['max_backlogs']} max allowed)."}), 400

    cursor.execute("SELECT 1 FROM drive_eligible_departments WHERE drive_id = ? AND dept_id = ?;", (drive_id, student["dept_id"]))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Student department is not eligible for this drive."}), 400

    # Insert registration
    cursor.execute("INSERT INTO registrations (student_id, drive_id, status) VALUES (?, ?, 'Applied');", (student_id, drive_id))
    reg_id = cursor.lastrowid

    # Automatically initialize round 1 progress record if round 1 exists
    cursor.execute("SELECT round_id FROM drive_rounds WHERE drive_id = ? AND round_number = 1;", (drive_id,))
    round1 = cursor.fetchone()
    if round1:
        cursor.execute("INSERT INTO round_progress (registration_id, round_id, attendance, status) VALUES (?, ?, 'Pending', 'Pending');",
                       (reg_id, round1["round_id"]))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Registered successfully!", "registration_id": reg_id})


@app.route("/api/student/<int:student_id>/progress", methods=["GET"])
def get_student_progress(student_id):
    """Fetches all drive applications and stage-by-stage progression for a student."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT r.registration_id, r.status AS overall_status, r.registered_at,
           dr.drive_id, dr.title AS drive_title, dr.drive_type, dr.stipend_monthly, dr.ctc_annual,
           c.name AS company_name, c.company_tier
    FROM registrations r
    JOIN drives dr ON r.drive_id = dr.drive_id
    JOIN companies c ON dr.company_id = c.company_id
    WHERE r.student_id = ?
    ORDER BY r.registered_at DESC;
    """, (student_id,))
    applications = [dict(row) for row in cursor.fetchall()]

    for app_item in applications:
        # Fetch all rounds defined for this drive
        cursor.execute("""
        SELECT dr_r.round_id, dr_r.round_number, dr_r.round_name, dr_r.round_mode, dr_r.round_date, dr_r.cutoff_score,
               rp.attendance, rp.score, rp.status AS round_status, rp.feedback, rp.evaluated_at
        FROM drive_rounds dr_r
        LEFT JOIN round_progress rp ON dr_r.round_id = rp.round_id AND rp.registration_id = ?
        WHERE dr_r.drive_id = ?
        ORDER BY dr_r.round_number ASC;
        """, (app_item["registration_id"], app_item["drive_id"]))
        app_item["rounds"] = [dict(r) for r in cursor.fetchall()]

        # Check offer
        cursor.execute("SELECT * FROM offers WHERE student_id = ? AND drive_id = ?;", (student_id, app_item["drive_id"]))
        offer = cursor.fetchone()
        app_item["offer"] = dict(offer) if offer else None

    conn.close()
    return jsonify(applications)


@app.route("/api/drives/<int:drive_id>/rounds/<int:round_id>/candidates", methods=["GET"])
def get_round_candidates(drive_id, round_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        r.registration_id,
        r.status AS application_status,
        s.student_id,
        s.roll_no,
        s.first_name || ' ' || s.last_name AS full_name,
        d.dept_code,
        s.cgpa,
        s.active_backlogs,
        s.email,
        s.phone,
        rp.progress_id,
        COALESCE(rp.attendance, 'Pending') AS attendance,
        rp.score,
        COALESCE(rp.status, 'Pending') AS round_status,
        rp.feedback
    FROM registrations r
    JOIN students s ON r.student_id = s.student_id
    JOIN departments d ON s.dept_id = d.dept_id
    LEFT JOIN round_progress rp ON r.registration_id = rp.registration_id AND rp.round_id = ?
    WHERE r.drive_id = ?
    ORDER BY s.roll_no ASC;
    """, (round_id, drive_id))
    candidates = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(candidates)


@app.route("/api/round-progress/update", methods=["POST"])
def update_round_progress():
    data = request.json or {}
    registration_id = data.get("registration_id")
    round_id = data.get("round_id")
    attendance = data.get("attendance", "Present")
    score = data.get("score")
    status = data.get("status", "Pending")
    feedback = data.get("feedback", "")

    if not registration_id or not round_id:
        return jsonify({"success": False, "message": "registration_id and round_id are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO round_progress (registration_id, round_id, attendance, score, status, feedback, evaluated_at)
    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(registration_id, round_id) DO UPDATE SET
        attendance = excluded.attendance,
        score = excluded.score,
        status = excluded.status,
        feedback = excluded.feedback,
        evaluated_at = CURRENT_TIMESTAMP;
    """, (registration_id, round_id, attendance, score, status, feedback))

    # Update overall registration status if rejected
    if status == "Rejected":
        cursor.execute("UPDATE registrations SET status = 'Rejected' WHERE registration_id = ?;", (registration_id,))
    elif status == "Cleared":
        cursor.execute("UPDATE registrations SET status = 'In_Process' WHERE registration_id = ? AND status != 'Selected';", (registration_id,))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Round evaluation saved."})


@app.route("/api/drives/<int:drive_id>/promote-round", methods=["POST"])
def promote_candidates_to_next_round(drive_id):
    data = request.json or {}
    from_round_number = data.get("from_round_number")

    if from_round_number is None:
        return jsonify({"success": False, "message": "from_round_number is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Find next round
    cursor.execute("SELECT round_id, round_name FROM drive_rounds WHERE drive_id = ? AND round_number = ?;", (drive_id, from_round_number))
    current_round = cursor.fetchone()
    cursor.execute("SELECT round_id, round_name FROM drive_rounds WHERE drive_id = ? AND round_number = ?;", (drive_id, from_round_number + 1))
    next_round = cursor.fetchone()

    if not current_round or not next_round:
        conn.close()
        return jsonify({"success": False, "message": "No subsequent round found to promote candidates to."}), 404

    # Find candidates who cleared current_round but aren't in next_round yet
    cursor.execute("""
    SELECT r.registration_id
    FROM registrations r
    JOIN round_progress rp ON r.registration_id = rp.registration_id
    WHERE r.drive_id = ?
      AND rp.round_id = ?
      AND rp.status = 'Cleared'
      AND r.registration_id NOT IN (
          SELECT registration_id FROM round_progress WHERE round_id = ?
      );
    """, (drive_id, current_round["round_id"], next_round["round_id"]))
    cleared_regs = cursor.fetchall()

    promoted_count = 0
    for reg in cleared_regs:
        cursor.execute("""
        INSERT INTO round_progress (registration_id, round_id, attendance, status)
        VALUES (?, ?, 'Pending', 'Pending');
        """, (reg["registration_id"], next_round["round_id"]))
        promoted_count += 1

    conn.commit()
    conn.close()
    return jsonify({
        "success": True, 
        "message": f"Successfully promoted {promoted_count} candidates to {next_round['round_name']}!",
        "promoted_count": promoted_count
    })


@app.route("/api/offers", methods=["POST"])
def issue_offer():
    data = request.json or {}
    student_id = data.get("student_id")
    drive_id = data.get("drive_id")
    offer_type = data.get("offer_type", "Placement")
    offered_stipend = data.get("offered_stipend", 0.0)
    offered_ctc = data.get("offered_ctc", 0.0)
    offer_letter_url = data.get("offer_letter_url", "")
    acceptance_status = data.get("acceptance_status", "Pending")

    if not student_id or not drive_id:
        return jsonify({"success": False, "message": "student_id and drive_id required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO offers (student_id, drive_id, offer_type, offered_stipend, offered_ctc, offer_letter_url, acceptance_status, response_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(student_id, drive_id) DO UPDATE SET
        offer_type = excluded.offer_type,
        offered_stipend = excluded.offered_stipend,
        offered_ctc = excluded.offered_ctc,
        offer_letter_url = excluded.offer_letter_url,
        acceptance_status = excluded.acceptance_status,
        response_date = CURRENT_TIMESTAMP;
    """, (student_id, drive_id, offer_type, offered_stipend, offered_ctc, offer_letter_url, acceptance_status))

    # Trigger logic: If accepted, update student placement status and registration status
    if acceptance_status == "Accepted":
        cursor.execute("UPDATE registrations SET status = 'Selected' WHERE student_id = ? AND drive_id = ?;", (student_id, drive_id))
        
        new_status = 'Placed'
        if offer_type == 'Internship':
            cursor.execute("SELECT placement_status FROM students WHERE student_id = ?;", (student_id,))
            current_st = cursor.fetchone()["placement_status"]
            new_status = current_st if current_st in ('Placed', 'Dream_Placed') else 'Internship_Only'
        else:
            new_status = 'Dream_Placed' if float(offered_ctc or 0) >= 15.0 else 'Placed'

        cursor.execute("UPDATE students SET placement_status = ? WHERE student_id = ?;", (new_status, student_id))

    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": "Offer saved successfully."})


# -----------------------------------------------------------------------------
# MAIN WEB UI (SPA INTERFACE)
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Placement & Internship TrackHub</title>
    <!-- Tailwind CSS CDN -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .timeline-line {
            position: absolute;
            left: 1.25rem;
            top: 2rem;
            bottom: 0;
            width: 2px;
            background-color: #e5e7eb;
        }
    </style>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col font-sans">

    <!-- Top Navigation Bar -->
    <header class="bg-indigo-900 text-white shadow-md sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex justify-between items-center h-16">
            <div class="flex items-center space-x-3">
                <div class="p-2 bg-indigo-700 rounded-lg shadow-inner">
                    <i class="fa-solid fa-graduation-cap text-xl text-amber-300"></i>
                </div>
                <div>
                    <h1 class="text-xl font-bold tracking-tight">TrackHub</h1>
                    <p class="text-xs text-indigo-200">Internship & Placement Operations System</p>
                </div>
            </div>

            <!-- Role Selector & Tabs -->
            <div class="flex items-center space-x-4">
                <nav class="flex space-x-1 bg-indigo-950/60 p-1 rounded-xl">
                    <button onclick="switchTab('analytics')" id="nav-analytics" class="px-3.5 py-1.5 rounded-lg text-sm font-medium transition duration-150 bg-indigo-600 text-white">
                        <i class="fa-solid fa-chart-pie mr-1.5"></i> Dashboard
                    </button>
                    <button onclick="switchTab('drives')" id="nav-drives" class="px-3.5 py-1.5 rounded-lg text-sm font-medium transition duration-150 text-indigo-200 hover:text-white">
                        <i class="fa-solid fa-building-columns mr-1.5"></i> Drives
                    </button>
                    <button onclick="switchTab('evaluator')" id="nav-evaluator" class="px-3.5 py-1.5 rounded-lg text-sm font-medium transition duration-150 text-indigo-200 hover:text-white">
                        <i class="fa-solid fa-tasks mr-1.5"></i> Round Evaluator
                    </button>
                    <button onclick="switchTab('student_portal')" id="nav-student_portal" class="px-3.5 py-1.5 rounded-lg text-sm font-medium transition duration-150 text-indigo-200 hover:text-white">
                        <i class="fa-solid fa-user-graduate mr-1.5"></i> Student Portal
                    </button>
                </nav>

                <!-- Student Persona Picker (Simulates Login) -->
                <div class="flex items-center space-x-2 pl-2 border-l border-indigo-700/60">
                    <span class="text-xs text-indigo-300 hidden md:inline">Logged As:</span>
                    <select id="activeStudentSelect" onchange="onStudentChange()" class="bg-indigo-800 text-white text-xs rounded-lg px-2.5 py-1.5 border border-indigo-600 focus:outline-none focus:ring-2 focus:ring-amber-400">
                        <!-- Populated by JS -->
                    </select>
                </div>
            </div>
        </div>
    </header>

    <!-- Main Container -->
    <main class="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">

        <!-- Notification Banner -->
        <div id="toastNotification" class="hidden mb-6 p-4 rounded-xl shadow-lg border text-sm font-medium transition duration-300 flex items-center justify-between">
            <span id="toastMessage"></span>
            <button onclick="hideToast()" class="text-slate-500 hover:text-slate-800">&times;</button>
        </div>

        <!-- ================================================================= -->
        <!-- TAB 1: ANALYTICS & TPO DASHBOARD -->
        <!-- ================================================================= -->
        <section id="tab-analytics" class="space-y-6">
            <!-- Metric Cards -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                <div class="bg-white p-5 rounded-2xl shadow-sm border border-slate-200/80 hover:shadow-md transition">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Placement Rate</p>
                            <h3 id="stat-rate" class="text-2xl font-black text-slate-800 mt-1">--%</h3>
                        </div>
                        <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center text-emerald-600">
                            <i class="fa-solid fa-award text-xl"></i>
                        </div>
                    </div>
                    <p class="text-xs text-slate-500 mt-3"><span id="stat-placed" class="font-bold text-emerald-600">0</span> of <span id="stat-total" class="font-semibold">0</span> candidates placed</p>
                </div>

                <div class="bg-white p-5 rounded-2xl shadow-sm border border-slate-200/80 hover:shadow-md transition">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Average Package</p>
                            <h3 id="stat-avg-ctc" class="text-2xl font-black text-slate-800 mt-1">₹-- LPA</h3>
                        </div>
                        <div class="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center text-indigo-600">
                            <i class="fa-solid fa-money-bill-trend-up text-xl"></i>
                        </div>
                    </div>
                    <p class="text-xs text-slate-500 mt-3">Highest CTC: <span id="stat-max-ctc" class="font-bold text-indigo-600">₹-- LPA</span></p>
                </div>

                <div class="bg-white p-5 rounded-2xl shadow-sm border border-slate-200/80 hover:shadow-md transition">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Internships Secured</p>
                            <h3 id="stat-interns" class="text-2xl font-black text-slate-800 mt-1">--</h3>
                        </div>
                        <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center text-amber-600">
                            <i class="fa-solid fa-briefcase text-xl"></i>
                        </div>
                    </div>
                    <p class="text-xs text-slate-500 mt-3">Summer & Pre-Placement Offers</p>
                </div>

                <div class="bg-white p-5 rounded-2xl shadow-sm border border-slate-200/80 hover:shadow-md transition">
                    <div class="flex items-center justify-between">
                        <div>
                            <p class="text-xs font-semibold text-slate-500 uppercase tracking-wider">Active Drives</p>
                            <h3 id="stat-active-drives" class="text-2xl font-black text-slate-800 mt-1">--</h3>
                        </div>
                        <div class="w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center text-sky-600">
                            <i class="fa-solid fa-building text-xl"></i>
                        </div>
                    </div>
                    <p class="text-xs text-slate-500 mt-3">Currently open for registration</p>
                </div>
            </div>

            <!-- Charts & Department Breakdown -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Dept Table -->
                <div class="lg:col-span-2 bg-white rounded-2xl shadow-sm border border-slate-200/80 p-5">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-base font-bold text-slate-800">Department Placement Performance</h3>
                        <span class="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full font-medium">Batch 2025</span>
                    </div>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left text-sm text-slate-600">
                            <thead class="bg-slate-50 text-xs font-semibold uppercase text-slate-500 border-b">
                                <tr>
                                    <th class="py-3 px-4">Department</th>
                                    <th class="py-3 px-4 text-center">Total</th>
                                    <th class="py-3 px-4 text-center">Placed</th>
                                    <th class="py-3 px-4 text-center">Intern Only</th>
                                    <th class="py-3 px-4 text-center">Avg CTC</th>
                                </tr>
                            </thead>
                            <tbody id="deptStatsBody" class="divide-y divide-slate-100">
                                <!-- Populated dynamically -->
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Doughnut Chart -->
                <div class="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-5 flex flex-col justify-between">
                    <h3 class="text-base font-bold text-slate-800 mb-2">Student Status Ratio</h3>
                    <div class="relative flex-1 flex items-center justify-center" style="max-height: 240px;">
                        <canvas id="placementRatioChart"></canvas>
                    </div>
                    <div class="mt-4 pt-3 border-t border-slate-100 flex justify-around text-xs text-slate-500">
                        <div class="flex items-center"><span class="w-2.5 h-2.5 rounded-full bg-emerald-500 mr-1.5"></span> Placed</div>
                        <div class="flex items-center"><span class="w-2.5 h-2.5 rounded-full bg-amber-500 mr-1.5"></span> Intern Only</div>
                        <div class="flex items-center"><span class="w-2.5 h-2.5 rounded-full bg-slate-300 mr-1.5"></span> Unplaced</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 2: DRIVES DIRECTORY & MANAGEMENT -->
        <!-- ================================================================= -->
        <section id="tab-drives" class="hidden space-y-6">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h2 class="text-xl font-bold text-slate-900">Campus Drives & Openings</h2>
                    <p class="text-sm text-slate-500">View hiring campaigns, recruitment deadlines, and eligibility criteria</p>
                </div>
            </div>

            <!-- Drives Cards Grid -->
            <div id="drivesGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <!-- Populated dynamically -->
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 3: ROUND PROGRESS & EVALUATOR (TPO / INTERVIEWER) -->
        <!-- ================================================================= -->
        <section id="tab-evaluator" class="hidden space-y-6">
            <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200/80">
                <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
                    <div>
                        <h2 class="text-xl font-bold text-slate-900">Multi-Round Candidate Evaluator</h2>
                        <p class="text-sm text-slate-500">Review candidate performance, grade rounds, and promote to subsequent stages</p>
                    </div>
                    <div class="flex flex-wrap items-center gap-3">
                        <button onclick="promoteCurrentRoundCandidates()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold shadow-sm transition flex items-center">
                            <i class="fa-solid fa-angles-right mr-1.5"></i> Promote Cleared to Next Round
                        </button>
                    </div>
                </div>

                <!-- Drive and Round Selectors -->
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200 mb-6">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Select Drive</label>
                        <select id="evaluatorDriveSelect" onchange="onEvaluatorDriveChange()" class="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                            <!-- Populated dynamically -->
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Select Stage / Round</label>
                        <select id="evaluatorRoundSelect" onchange="loadRoundCandidates()" class="w-full bg-white border border-slate-300 rounded-lg px-3 py-2 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                            <!-- Populated dynamically -->
                        </select>
                    </div>
                </div>

                <!-- Candidates Table -->
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm text-slate-700">
                        <thead class="bg-slate-100 text-xs font-semibold uppercase text-slate-600 border-b">
                            <tr>
                                <th class="py-3 px-4">Student</th>
                                <th class="py-3 px-4">Academic Specs</th>
                                <th class="py-3 px-4">Attendance</th>
                                <th class="py-3 px-4">Score</th>
                                <th class="py-3 px-4">Round Outcome</th>
                                <th class="py-3 px-4">Feedback</th>
                                <th class="py-3 px-4 text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody id="evaluatorTableBody" class="divide-y divide-slate-100">
                            <!-- Populated dynamically -->
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- ================================================================= -->
        <!-- TAB 4: STUDENT PORTAL (REGISTRATION & LIVE TRACKER) -->
        <!-- ================================================================= -->
        <section id="tab-student_portal" class="hidden space-y-6">
            <!-- Student Header Profile Banner -->
            <div id="studentProfileBanner" class="bg-gradient-to-r from-indigo-700 to-indigo-900 text-white rounded-2xl p-6 shadow-md flex flex-col md:flex-row md:items-center justify-between gap-4">
                <!-- Dynamically populated -->
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Left 2 Cols: My Active Applications & Multi-Round Journey -->
                <div class="lg:col-span-2 space-y-6">
                    <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200/80">
                        <h3 class="text-lg font-bold text-slate-900 mb-1 flex items-center">
                            <i class="fa-solid fa-route text-indigo-600 mr-2"></i> My Application Progress Timeline
                        </h3>
                        <p class="text-xs text-slate-500 mb-6">Real-time status tracking across every stage of your selection process</p>

                        <div id="studentProgressList" class="space-y-6">
                            <!-- Populated dynamically -->
                        </div>
                    </div>
                </div>

                <!-- Right Col: Available Drives with Instant Eligibility Check -->
                <div class="space-y-6">
                    <div class="bg-white p-6 rounded-2xl shadow-sm border border-slate-200/80">
                        <h3 class="text-lg font-bold text-slate-900 mb-1 flex items-center">
                            <i class="fa-solid fa-file-signature text-amber-500 mr-2"></i> Open Drives & Eligibility
                        </h3>
                        <p class="text-xs text-slate-500 mb-4">Live verification against CGPA, backlogs, department, and deadlines</p>

                        <div id="studentEligibleDrivesList" class="space-y-4">
                            <!-- Populated dynamically -->
                        </div>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <!-- Offer Modal -->
    <div id="offerModal" class="hidden fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div class="bg-white w-full max-w-md rounded-2xl p-6 shadow-2xl space-y-4">
            <h3 class="text-lg font-bold text-slate-900">Generate Selection Offer</h3>
            <div class="space-y-3 text-sm">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Student</label>
                    <input type="text" id="modalStudentName" readonly class="w-full bg-slate-100 border border-slate-200 rounded-lg px-3 py-2 text-slate-700 font-medium">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Offer Type</label>
                    <select id="modalOfferType" class="w-full border border-slate-300 rounded-lg px-3 py-2">
                        <option value="Placement">Full-Time Placement</option>
                        <option value="Internship">Internship</option>
                    </select>
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Annual CTC (in LPA)</label>
                    <input type="number" step="0.1" id="modalOfferCTC" class="w-full border border-slate-300 rounded-lg px-3 py-2" placeholder="e.g. 18.5">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Monthly Stipend (if Internship)</label>
                    <input type="number" step="1000" id="modalOfferStipend" class="w-full border border-slate-300 rounded-lg px-3 py-2" placeholder="e.g. 50000">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Offer Letter Link</label>
                    <input type="text" id="modalOfferUrl" class="w-full border border-slate-300 rounded-lg px-3 py-2" placeholder="https://cdn.college.edu/offers/...">
                </div>
            </div>
            <div class="flex justify-end space-x-2 pt-2 border-t">
                <button onclick="closeOfferModal()" class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl">Cancel</button>
                <button onclick="submitOffer()" class="px-4 py-2 text-sm bg-emerald-600 hover:bg-emerald-700 text-white font-medium rounded-xl">Confirm & Issue Offer</button>
            </div>
        </div>
    </div>

    <!-- Scripting / Logic -->
    <script>
        let currentStudents = [];
        let currentDrives = [];
        let selectedStudentId = 1;
        let placementChart = null;
        let pendingOfferData = null;

        // Initialize App
        document.addEventListener('DOMContentLoaded', async () => {
            await loadStudents();
            await loadDashboardStats();
            await loadDrives();
            await loadEvaluatorDriveList();
        });

        // Tab Navigation
        function switchTab(tabId) {
            ['analytics', 'drives', 'evaluator', 'student_portal'].forEach(t => {
                document.getElementById(`tab-${t}`).classList.add('hidden');
                document.getElementById(`nav-${t}`).classList.remove('bg-indigo-600', 'text-white');
                document.getElementById(`nav-${t}`).classList.add('text-indigo-200');
            });
            document.getElementById(`tab-${tabId}`).classList.remove('hidden');
            document.getElementById(`nav-${tabId}`).classList.add('bg-indigo-600', 'text-white');
            document.getElementById(`nav-${tabId}`).classList.remove('text-indigo-200');

            if (tabId === 'student_portal') {
                renderStudentPortal();
            } else if (tabId === 'analytics') {
                loadDashboardStats();
            } else if (tabId === 'evaluator') {
                loadEvaluatorDriveList();
            }
        }

        // Notification Helper
        function showToast(message, isError = false) {
            const toast = document.getElementById('toastNotification');
            const msg = document.getElementById('toastMessage');
            toast.className = `mb-6 p-4 rounded-xl shadow-lg border text-sm font-medium transition duration-300 flex items-center justify-between ${
                isError ? 'bg-rose-50 border-rose-200 text-rose-800' : 'bg-emerald-50 border-emerald-200 text-emerald-800'
            }`;
            msg.innerHTML = `${isError ? '<i class="fa-solid fa-circle-exclamation mr-2"></i>' : '<i class="fa-solid fa-circle-check mr-2"></i>'} ${message}`;
            toast.classList.remove('hidden');
            setTimeout(() => { toast.classList.add('hidden'); }, 5000);
        }

        function hideToast() {
            document.getElementById('toastNotification').classList.add('hidden');
        }

        // Load Students for personas
        async function loadStudents() {
            try {
                const res = await fetch('/api/students');
                currentStudents = await res.json();
                const select = document.getElementById('activeStudentSelect');
                select.innerHTML = '';
                currentStudents.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.student_id;
                    opt.text = `${s.roll_no} - ${s.first_name} (${s.dept_code})`;
                    select.appendChild(opt);
                });
                selectedStudentId = currentStudents[0]?.student_id || 1;
            } catch (err) {
                console.error("Error loading students:", err);
            }
        }

        function onStudentChange() {
            selectedStudentId = parseInt(document.getElementById('activeStudentSelect').value);
            renderStudentPortal();
        }

        // Load Dashboard Statistics
        async function loadDashboardStats() {
            try {
                const res = await fetch('/api/dashboard/stats');
                const data = await res.json();

                document.getElementById('stat-rate').innerText = `${data.placement_rate || 0}%`;
                document.getElementById('stat-placed').innerText = data.total_placed || 0;
                document.getElementById('stat-total').innerText = data.total_students || 0;
                document.getElementById('stat-avg-ctc').innerText = `₹${data.avg_ctc || 0} LPA`;
                document.getElementById('stat-max-ctc').innerText = `₹${data.max_ctc || 0} LPA`;
                document.getElementById('stat-interns').innerText = data.total_interns || 0;
                document.getElementById('stat-active-drives').innerText = data.active_drives || 0;

                // Dept stats
                const tbody = document.getElementById('deptStatsBody');
                tbody.innerHTML = '';
                (data.departments || []).forEach(d => {
                    tbody.innerHTML += `
                        <tr class="hover:bg-slate-50/80">
                            <td class="py-3.5 px-4 font-semibold text-slate-800">${d.dept_code} <span class="text-xs text-slate-400 font-normal">(${d.dept_name})</span></td>
                            <td class="py-3.5 px-4 text-center">${d.total_students}</td>
                            <td class="py-3.5 px-4 text-center font-bold text-emerald-600">${d.placed}</td>
                            <td class="py-3.5 px-4 text-center text-amber-600 font-medium">${d.intern_only}</td>
                            <td class="py-3.5 px-4 text-center font-medium">${d.avg_ctc ? `₹${d.avg_ctc} LPA` : '-'}</td>
                        </tr>
                    `;
                });

                // Chart
                const placed = data.total_placed || 0;
                const intern = data.total_interns || 0;
                const unplaced = data.total_unplaced || 0;

                if (placementChart) placementChart.destroy();
                const ctx = document.getElementById('placementRatioChart').getContext('2d');
                placementChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Placed', 'Intern Only', 'Unplaced'],
                        datasets: [{
                            data: [placed, intern, unplaced],
                            backgroundColor: ['#10b981', '#f59e0b', '#cbd5e1'],
                            borderWidth: 0
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        cutout: '70%'
                    }
                });

            } catch (err) {
                console.error("Error loading dashboard stats:", err);
            }
        }

        // Load Drives
        async function loadDrives() {
            try {
                const res = await fetch('/api/drives');
                currentDrives = await res.json();
                const grid = document.getElementById('drivesGrid');
                grid.innerHTML = '';

                currentDrives.forEach(dr => {
                    const badgeColor = dr.status === 'Ongoing' ? 'bg-emerald-100 text-emerald-700' : 
                                      (dr.status === 'Registration_Open' ? 'bg-sky-100 text-sky-700' : 'bg-slate-100 text-slate-700');
                    grid.innerHTML += `
                        <div class="bg-white rounded-2xl shadow-sm border border-slate-200/80 p-5 flex flex-col justify-between hover:shadow-md transition">
                            <div>
                                <div class="flex items-center justify-between mb-3">
                                    <span class="text-xs font-bold px-2.5 py-1 rounded-full ${badgeColor}">
                                        ${dr.status.replace('_', ' ')}
                                    </span>
                                    <span class="text-xs text-slate-400 font-medium">${dr.company_tier}</span>
                                </div>
                                <h3 class="text-base font-bold text-slate-900">${dr.title}</h3>
                                <p class="text-xs font-semibold text-indigo-600 mb-2">${dr.company_name} • ${dr.industry || 'Tech'}</p>
                                <p class="text-xs text-slate-500 line-clamp-2 mb-4">${dr.job_description || ''}</p>

                                <div class="space-y-1.5 text-xs text-slate-600 bg-slate-50 p-3 rounded-xl mb-4">
                                    <div class="flex justify-between">
                                        <span class="text-slate-400">Compensation:</span>
                                        <span class="font-bold text-slate-800">${dr.ctc_annual > 0 ? `₹${dr.ctc_annual} LPA` : `₹${dr.stipend_monthly}/mo`}</span>
                                    </div>
                                    <div class="flex justify-between">
                                        <span class="text-slate-400">Min CGPA:</span>
                                        <span class="font-medium">${dr.min_cgpa} (Max Backlogs: ${dr.max_backlogs})</span>
                                    </div>
                                    <div class="flex justify-between">
                                        <span class="text-slate-400">Eligible Depts:</span>
                                        <span class="font-medium">${dr.eligible_dept_codes || 'All'}</span>
                                    </div>
                                </div>
                            </div>

                            <div class="pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
                                <span><i class="fa-solid fa-users mr-1"></i> ${dr.total_applicants} Applicants</span>
                                <span>Deadline: ${new Date(dr.reg_deadline).toLocaleDateString()}</span>
                            </div>
                        </div>
                    `;
                });
            } catch (err) {
                console.error("Error loading drives:", err);
            }
        }

        // Student Portal Rendering
        async function renderStudentPortal() {
            const student = currentStudents.find(s => s.student_id === selectedStudentId);
            if (!student) return;

            // Header Banner
            const banner = document.getElementById('studentProfileBanner');
            const statusBadge = student.placement_status === 'Placed' || student.placement_status === 'Dream_Placed'
                ? 'bg-emerald-500 text-white' : (student.placement_status === 'Internship_Only' ? 'bg-amber-400 text-slate-900' : 'bg-indigo-600 text-white');

            banner.innerHTML = `
                <div>
                    <div class="flex items-center space-x-3 mb-1">
                        <h2 class="text-2xl font-black">${student.first_name} ${student.last_name}</h2>
                        <span class="text-xs font-bold px-2.5 py-0.5 rounded-full ${statusBadge}">${student.placement_status.replace('_', ' ')}</span>
                    </div>
                    <p class="text-xs text-indigo-200">Roll No: ${student.roll_no} • ${student.dept_name} (${student.dept_code}) • Batch ${student.batch_year}</p>
                </div>
                <div class="flex items-center space-x-6 text-sm bg-indigo-800/60 px-5 py-3 rounded-xl border border-indigo-600/40">
                    <div>
                        <p class="text-xs text-indigo-300">CGPA</p>
                        <p class="text-xl font-black text-amber-300">${student.cgpa}</p>
                    </div>
                    <div class="border-l border-indigo-600/40 pl-4">
                        <p class="text-xs text-indigo-300">Active Backlogs</p>
                        <p class="text-xl font-black ${student.active_backlogs > 0 ? 'text-rose-400' : 'text-emerald-300'}">${student.active_backlogs}</p>
                    </div>
                </div>
            `;

            // Load Eligible Drives & Applied Drives
            loadStudentEligibility(student.student_id);
            loadStudentProgress(student.student_id);
        }

        async function loadStudentEligibility(studentId) {
            try {
                const res = await fetch(`/api/student/${studentId}/eligibility`);
                const drives = await res.json();
                const container = document.getElementById('studentEligibleDrivesList');
                container.innerHTML = '';

                drives.forEach(d => {
                    const isRegistered = !!d.registration_status;
                    container.innerHTML += `
                        <div class="p-4 rounded-xl border ${d.is_eligible ? 'border-slate-200 bg-slate-50/50' : 'border-rose-100 bg-rose-50/20'} text-xs">
                            <div class="flex justify-between items-start mb-1">
                                <h4 class="font-bold text-slate-800 text-sm">${d.title}</h4>
                                <span class="font-semibold text-indigo-600">${d.company_name}</span>
                            </div>
                            <p class="text-slate-500 mb-2">Compensation: <span class="font-semibold text-slate-700">${d.ctc_annual > 0 ? `₹${d.ctc_annual} LPA` : `₹${d.stipend_monthly}/mo`}</span></p>
                            
                            ${!d.is_eligible ? `
                                <div class="text-rose-600 bg-rose-50 p-2 rounded-lg mb-2">
                                    <i class="fa-solid fa-triangle-exclamation mr-1"></i> Ineligible: ${d.eligibility_reasons.join(', ')}
                                </div>
                            ` : ''}

                            <div class="flex items-center justify-between pt-2 border-t border-slate-200/60 mt-2">
                                <span class="text-slate-400">Deadline: ${new Date(d.reg_deadline).toLocaleDateString()}</span>
                                ${isRegistered ? `
                                    <span class="px-3 py-1 bg-emerald-100 text-emerald-800 font-bold rounded-lg"><i class="fa-solid fa-check mr-1"></i> Applied</span>
                                ` : (d.is_eligible ? `
                                    <button onclick="registerForDrive(${studentId}, ${d.drive_id})" class="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-sm transition">
                                        Apply Now
                                    </button>
                                ` : `
                                    <span class="text-slate-400 font-medium italic">Not Eligible</span>
                                `)}
                            </div>
                        </div>
                    `;
                });
            } catch (err) {
                console.error("Error loading eligibility:", err);
            }
        }

        async function registerForDrive(studentId, driveId) {
            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ student_id: studentId, drive_id: driveId })
                });
                const result = await res.json();
                if (result.success) {
                    showToast(result.message);
                    renderStudentPortal();
                } else {
                    showToast(result.message, true);
                }
            } catch (err) {
                showToast("Failed to register. Please try again.", true);
            }
        }

        async function loadStudentProgress(studentId) {
            try {
                const res = await fetch(`/api/student/${studentId}/progress`);
                const applications = await res.json();
                const container = document.getElementById('studentProgressList');
                container.innerHTML = '';

                if (applications.length === 0) {
                    container.innerHTML = `<p class="text-sm text-slate-400 italic">No applications submitted yet. Browse open drives to apply.</p>`;
                    return;
                }

                applications.forEach(app => {
                    let roundsHtml = '';
                    app.rounds.forEach((rd, idx) => {
                        let roundBadge = 'bg-slate-100 text-slate-500 border-slate-200';
                        let icon = '<i class="fa-solid fa-hourglass-start"></i>';
                        if (rd.round_status === 'Cleared') {
                            roundBadge = 'bg-emerald-50 text-emerald-700 border-emerald-300';
                            icon = '<i class="fa-solid fa-circle-check text-emerald-600"></i>';
                        } else if (rd.round_status === 'Rejected') {
                            roundBadge = 'bg-rose-50 text-rose-700 border-rose-300';
                            icon = '<i class="fa-solid fa-circle-xmark text-rose-600"></i>';
                        } else if (rd.attendance === 'Present') {
                            roundBadge = 'bg-sky-50 text-sky-700 border-sky-300';
                            icon = '<i class="fa-solid fa-spinner fa-spin text-sky-600"></i>';
                        }

                        roundsHtml += `
                            <div class="relative pl-8 pb-4">
                                ${idx < app.rounds.length - 1 ? '<div class="timeline-line"></div>' : ''}
                                <div class="absolute left-2.5 -translate-x-1/2 top-0.5 bg-white p-0.5 rounded-full z-10">
                                    ${icon}
                                </div>
                                <div class="p-3 rounded-xl border ${roundBadge}">
                                    <div class="flex justify-between items-center text-xs">
                                        <span class="font-bold">Stage ${rd.round_number}: ${rd.round_name}</span>
                                        <span class="font-semibold uppercase tracking-wider">${rd.round_status || 'Pending Evaluation'}</span>
                                    </div>
                                    ${rd.score !== null ? `<p class="text-xs mt-1">Score: <strong class="font-bold">${rd.score}/100</strong></p>` : ''}
                                    ${rd.feedback ? `<p class="text-xs text-slate-500 mt-1 italic">"${rd.feedback}"</p>` : ''}
                                </div>
                            </div>
                        `;
                    });

                    // Offer card
                    let offerHtml = '';
                    if (app.offer) {
                        offerHtml = `
                            <div class="mt-4 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs">
                                <div class="flex justify-between items-center mb-1">
                                    <span class="font-black text-emerald-800 text-sm"><i class="fa-solid fa-trophy mr-1 text-amber-500"></i> Offer Received!</span>
                                    <span class="px-2 py-0.5 rounded-full font-bold bg-emerald-200 text-emerald-900">${app.offer.acceptance_status}</span>
                                </div>
                                <p class="text-slate-600">Role: <strong>${app.offer.offer_type}</strong> • Compensation: <strong>₹${app.offer.offered_ctc || 0} LPA</strong></p>
                                ${app.offer.acceptance_status === 'Pending' ? `
                                    <div class="mt-3 flex space-x-2">
                                        <button onclick="respondToOffer(${app.offer.student_id}, ${app.offer.drive_id}, 'Accepted')" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-lg shadow-sm">Accept Offer</button>
                                        <button onclick="respondToOffer(${app.offer.student_id}, ${app.offer.drive_id}, 'Declined')" class="px-3 py-1.5 bg-slate-200 hover:bg-slate-300 text-slate-700 font-semibold rounded-lg">Decline</button>
                                    </div>
                                ` : ''}
                            </div>
                        `;
                    }

                    container.innerHTML += `
                        <div class="p-5 rounded-2xl border border-slate-200 bg-white shadow-sm mb-4">
                            <div class="flex justify-between items-center mb-4 pb-3 border-b border-slate-100">
                                <div>
                                    <h4 class="text-base font-bold text-slate-800">${app.drive_title}</h4>
                                    <p class="text-xs text-slate-500">${app.company_name} • Applied on ${new Date(app.registered_at).toLocaleDateString()}</p>
                                </div>
                                <span class="px-3 py-1 rounded-full text-xs font-bold ${
                                    app.overall_status === 'Selected' ? 'bg-emerald-100 text-emerald-800' :
                                    (app.overall_status === 'Rejected' ? 'bg-rose-100 text-rose-800' : 'bg-indigo-100 text-indigo-800')
                                }">
                                    ${app.overall_status.replace('_', ' ')}
                                </span>
                            </div>
                            <div class="space-y-1">
                                ${roundsHtml}
                            </div>
                            ${offerHtml}
                        </div>
                    `;
                });
            } catch (err) {
                console.error("Error loading student progress:", err);
            }
        }

        async function respondToOffer(studentId, driveId, status) {
            try {
                const res = await fetch('/api/offers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ student_id: studentId, drive_id: driveId, acceptance_status: status })
                });
                const result = await res.json();
                if (result.success) {
                    showToast(`Offer ${status}!`);
                    await loadStudents();
                    renderStudentPortal();
                }
            } catch (err) {
                showToast("Failed to update offer status.", true);
            }
        }

        // Evaluator Tab Logic
        async function loadEvaluatorDriveList() {
            try {
                const res = await fetch('/api/drives');
                const drives = await res.json();
                const select = document.getElementById('evaluatorDriveSelect');
                select.innerHTML = '';
                drives.forEach(d => {
                    const opt = document.createElement('option');
                    opt.value = d.drive_id;
                    opt.text = `${d.company_name} - ${d.title}`;
                    select.appendChild(opt);
                });
                if (drives.length > 0) {
                    onEvaluatorDriveChange();
                }
            } catch (err) {
                console.error(err);
            }
        }

        async function onEvaluatorDriveChange() {
            const driveId = document.getElementById('evaluatorDriveSelect').value;
            try {
                const res = await fetch(`/api/drives/${driveId}`);
                const drive = await res.json();
                const roundSelect = document.getElementById('evaluatorRoundSelect');
                roundSelect.innerHTML = '';
                (drive.rounds || []).forEach(r => {
                    const opt = document.createElement('option');
                    opt.value = r.round_id;
                    opt.dataset.roundNumber = r.round_number;
                    opt.text = `Stage ${r.round_number}: ${r.round_name}`;
                    roundSelect.appendChild(opt);
                });
                loadRoundCandidates();
            } catch (err) {
                console.error(err);
            }
        }

        async function loadRoundCandidates() {
            const driveId = document.getElementById('evaluatorDriveSelect').value;
            const roundId = document.getElementById('evaluatorRoundSelect').value;
            if (!driveId || !roundId) return;

            try {
                const res = await fetch(`/api/drives/${driveId}/rounds/${roundId}/candidates`);
                const candidates = await res.json();
                const tbody = document.getElementById('evaluatorTableBody');
                tbody.innerHTML = '';

                if (candidates.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="7" class="py-6 text-center text-slate-400 italic">No candidates registered or promoted to this round yet.</td></tr>`;
                    return;
                }

                candidates.forEach(c => {
                    tbody.innerHTML += `
                        <tr class="hover:bg-slate-50/80">
                            <td class="py-3 px-4">
                                <p class="font-bold text-slate-800">${c.full_name}</p>
                                <p class="text-xs text-slate-400">${c.roll_no} • ${c.dept_code}</p>
                            </td>
                            <td class="py-3 px-4 text-xs">
                                <p>CGPA: <strong>${c.cgpa}</strong></p>
                                <p class="text-slate-400">Backlogs: ${c.active_backlogs}</p>
                            </td>
                            <td class="py-3 px-4">
                                <select id="att_${c.registration_id}" class="text-xs border rounded-lg px-2 py-1 bg-white">
                                    <option value="Pending" ${c.attendance === 'Pending' ? 'selected' : ''}>Pending</option>
                                    <option value="Present" ${c.attendance === 'Present' ? 'selected' : ''}>Present</option>
                                    <option value="Absent" ${c.attendance === 'Absent' ? 'selected' : ''}>Absent</option>
                                </select>
                            </td>
                            <td class="py-3 px-4">
                                <input type="number" id="score_${c.registration_id}" value="${c.score !== null ? c.score : ''}" placeholder="0-100" class="w-16 text-xs border rounded-lg px-2 py-1">
                            </td>
                            <td class="py-3 px-4">
                                <select id="status_${c.registration_id}" class="text-xs border rounded-lg px-2 py-1 font-semibold ${
                                    c.round_status === 'Cleared' ? 'text-emerald-700 bg-emerald-50' : (c.round_status === 'Rejected' ? 'text-rose-700 bg-rose-50' : '')
                                }">
                                    <option value="Pending" ${c.round_status === 'Pending' ? 'selected' : ''}>Pending</option>
                                    <option value="Cleared" ${c.round_status === 'Cleared' ? 'selected' : ''}>Cleared</option>
                                    <option value="Rejected" ${c.round_status === 'Rejected' ? 'selected' : ''}>Rejected</option>
                                    <option value="Waitlisted" ${c.round_status === 'Waitlisted' ? 'selected' : ''}>Waitlisted</option>
                                </select>
                            </td>
                            <td class="py-3 px-4">
                                <input type="text" id="feedback_${c.registration_id}" value="${c.feedback || ''}" placeholder="Interviewer remarks" class="text-xs border rounded-lg px-2 py-1 w-full max-w-xs">
                            </td>
                            <td class="py-3 px-4 text-center space-x-1">
                                <button onclick="saveRoundEvaluation(${c.registration_id}, ${roundId})" class="px-2.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-sm">
                                    Save
                                </button>
                                <button onclick="openOfferModal(${c.student_id}, '${c.full_name}', ${driveId})" title="Issue Final Offer" class="px-2 py-1.5 bg-emerald-100 hover:bg-emerald-200 text-emerald-800 rounded-lg text-xs font-semibold">
                                    <i class="fa-solid fa-certificate"></i>
                                </button>
                            </td>
                        </tr>
                    `;
                });
            } catch (err) {
                console.error(err);
            }
        }

        async function saveRoundEvaluation(registrationId, roundId) {
            const attendance = document.getElementById(`att_${registrationId}`).value;
            const scoreVal = document.getElementById(`score_${registrationId}`).value;
            const status = document.getElementById(`status_${registrationId}`).value;
            const feedback = document.getElementById(`feedback_${registrationId}`).value;

            try {
                const res = await fetch('/api/round-progress/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        registration_id: registrationId,
                        round_id: roundId,
                        attendance: attendance,
                        score: scoreVal ? parseFloat(scoreVal) : null,
                        status: status,
                        feedback: feedback
                    })
                });
                const result = await res.json();
                if (result.success) {
                    showToast("Candidate evaluation updated successfully!");
                    loadRoundCandidates();
                }
            } catch (err) {
                showToast("Failed to save evaluation.", true);
            }
        }

        async function promoteCurrentRoundCandidates() {
            const driveId = document.getElementById('evaluatorDriveSelect').value;
            const roundSelect = document.getElementById('evaluatorRoundSelect');
            const roundNum = parseInt(roundSelect.options[roundSelect.selectedIndex]?.dataset.roundNumber);

            if (!roundNum) return;

            try {
                const res = await fetch(`/api/drives/${driveId}/promote-round`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ from_round_number: roundNum })
                });
                const result = await res.json();
                if (result.success) {
                    showToast(result.message);
                    onEvaluatorDriveChange();
                } else {
                    showToast(result.message, true);
                }
            } catch (err) {
                showToast("Promotion error.", true);
            }
        }

        // Offer Modal Handlers
        function openOfferModal(studentId, studentName, driveId) {
            pendingOfferData = { student_id: studentId, drive_id: driveId };
            document.getElementById('modalStudentName').value = studentName;
            document.getElementById('offerModal').classList.remove('hidden');
        }

        function closeOfferModal() {
            document.getElementById('offerModal').classList.add('hidden');
            pendingOfferData = null;
        }

        async function submitOffer() {
            if (!pendingOfferData) return;
            const offerType = document.getElementById('modalOfferType').value;
            const ctc = document.getElementById('modalOfferCTC').value;
            const stipend = document.getElementById('modalOfferStipend').value;
            const url = document.getElementById('modalOfferUrl').value;

            try {
                const res = await fetch('/api/offers', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        student_id: pendingOfferData.student_id,
                        drive_id: pendingOfferData.drive_id,
                        offer_type: offerType,
                        offered_ctc: ctc ? parseFloat(ctc) : 0,
                        offered_stipend: stipend ? parseFloat(stipend) : 0,
                        offer_letter_url: url,
                        acceptance_status: 'Accepted'
                    })
                });
                const result = await res.json();
                if (result.success) {
                    showToast("Selection offer recorded and accepted!");
                    closeOfferModal();
                    loadRoundCandidates();
                    await loadStudents();
                }
            } catch (err) {
                showToast("Failed to issue offer.", true);
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print("Starting Placement & Internship TrackHub Server on port 5000...")
    app.run(host="127.0.0.1", port=5000, debug=True)
