# Internship & Placement TrackHub (Web Application & Database)

A full-stack web application and relational database management system for colleges and universities to manage campus recruitment drives, student registrations, multi-stage round evaluations, progress tracking, and job offers.

---

## 1. Features

### 📊 TPO & Placement Operations Dashboard
* Real-time metrics: Institutional Placement %, Average CTC, Highest CTC, Total Internships, and Active Drives.
* Department-level breakdown (CSE, IT, ECE, MECH) with dynamic Donut chart ratios.

### 🏢 Drive & Hiring Campaign Management
* View all company recruitment drives (Google, Microsoft, Qualcomm, TCS, etc.).
* Displays CTC / Stipend packages, required CGPA, allowed backlogs, eligible departments, and registration deadlines.

### 🎓 Student Portal & Dynamic Eligibility Engine
* Persona-based view to simulate logged-in students.
* **Instant Eligibility Checker**: Real-time evaluation against multiple criteria (CGPA cutoff, active backlogs, batch year, eligible department, and active deadline). If ineligible, clear contextual reasons are shown.
* **1-Click Registration**: Students can apply with automated validation.
* **Live Progress Timeline**: Visual vertical timeline showing current stage, score, interviewer remarks, and clearance status (`Cleared`, `Rejected`, `Waitlisted`, `Pending`).
* **Offer Acceptance**: Review received offers, salary packages, and accept/decline in 1-click.

### 🎯 Multi-Round Evaluator & Batch Promotion
* Choose any company drive and interview round (e.g., *Round 1: Online Assessment*, *Round 2: Technical Interview*, *Round 3: Bar Raiser*).
* Mark attendance (`Present` / `Absent`), input test/interview scores, update clearance outcomes, and write feedback.
* **Batch Promotion**: Promote all candidates who cleared Round $N$ directly into Round $N+1$ with a single click.
* **Offer Generation**: Issue Full-Time or Internship offers with automated student placement status upgrades.

---

## 2. Project Directory Structure

```
placement-tracker-db/
├── app.py              # Flask Web Application (REST API + Interactive UI)
├── init_db.py          # Database setup and seed migration script
├── tracker.db          # SQLite Database instance with relational schema
├── schema.sql          # PostgreSQL/Standard SQL DDL & Triggers
├── seed_data.sql       # Sample seed data for PostgreSQL
├── queries.sql         # Operational and analytical SQL queries
└── README.md           # Documentation
```

---

## 3. How to Run the Web Application

### Step 1: Open a terminal in this directory
```powershell
cd C:\Users\jaswa\.gemini\antigravity\scratch\placement-tracker-db
```

### Step 2: (Optional) Reset / Re-seed the Database
```powershell
python init_db.py
```

### Step 3: Start the Web Server
```powershell
python app.py
```

### Step 4: Access in your Browser
Open: **`http://127.0.0.1:5000`**
