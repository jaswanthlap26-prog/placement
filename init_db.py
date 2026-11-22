import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "tracker.db")

def init_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Drop existing tables
    cursor.executescript("""
    DROP TABLE IF EXISTS offers;
    DROP TABLE IF EXISTS round_progress;
    DROP TABLE IF EXISTS registrations;
    DROP TABLE IF EXISTS drive_rounds;
    DROP TABLE IF EXISTS drive_eligible_departments;
    DROP TABLE IF EXISTS drives;
    DROP TABLE IF EXISTS companies;
    DROP TABLE IF EXISTS students;
    DROP TABLE IF EXISTS departments;
    """)

    # Create Tables
    cursor.executescript("""
    CREATE TABLE departments (
        dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
        dept_code TEXT NOT NULL UNIQUE,
        dept_name TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE students (
        student_id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT NOT NULL UNIQUE,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        phone TEXT NOT NULL,
        dept_id INTEGER NOT NULL REFERENCES departments(dept_id) ON DELETE RESTRICT,
        batch_year INTEGER NOT NULL,
        cgpa REAL NOT NULL CHECK (cgpa >= 0.00 AND cgpa <= 10.00),
        active_backlogs INTEGER NOT NULL DEFAULT 0 CHECK (active_backlogs >= 0),
        placement_status TEXT NOT NULL DEFAULT 'Unplaced'
            CHECK (placement_status IN ('Unplaced', 'Internship_Only', 'Placed', 'Dream_Placed')),
        resume_url TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE companies (
        company_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        industry TEXT,
        website TEXT,
        hr_name TEXT,
        hr_email TEXT NOT NULL,
        hr_phone TEXT,
        company_tier TEXT DEFAULT 'Tier 2'
            CHECK (company_tier IN ('Tier 1', 'Tier 2', 'Tier 3', 'Startup')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE drives (
        drive_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        job_description TEXT,
        drive_type TEXT NOT NULL 
            CHECK (drive_type IN ('Internship', 'Full_Time', 'Internship_Plus_PPO')),
        stipend_monthly REAL DEFAULT 0.00,
        ctc_annual REAL DEFAULT 0.00,
        min_cgpa REAL NOT NULL DEFAULT 6.00 CHECK (min_cgpa >= 0.00 AND min_cgpa <= 10.00),
        max_backlogs INTEGER NOT NULL DEFAULT 0 CHECK (max_backlogs >= 0),
        eligible_batch_year INTEGER NOT NULL,
        work_location TEXT DEFAULT 'Flexible / Hybrid',
        reg_start_date DATETIME NOT NULL,
        reg_deadline DATETIME NOT NULL,
        status TEXT NOT NULL DEFAULT 'Registration_Open'
            CHECK (status IN ('Upcoming', 'Registration_Open', 'Ongoing', 'Completed', 'Cancelled')),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE drive_eligible_departments (
        drive_id INTEGER NOT NULL REFERENCES drives(drive_id) ON DELETE CASCADE,
        dept_id INTEGER NOT NULL REFERENCES departments(dept_id) ON DELETE CASCADE,
        PRIMARY KEY (drive_id, dept_id)
    );

    CREATE TABLE drive_rounds (
        round_id INTEGER PRIMARY KEY AUTOINCREMENT,
        drive_id INTEGER NOT NULL REFERENCES drives(drive_id) ON DELETE CASCADE,
        round_number INTEGER NOT NULL,
        round_name TEXT NOT NULL,
        round_mode TEXT NOT NULL DEFAULT 'Online' 
            CHECK (round_mode IN ('Online', 'Offline', 'Hybrid')),
        round_date DATETIME,
        venue TEXT,
        cutoff_score REAL,
        UNIQUE (drive_id, round_number)
    );

    CREATE TABLE registrations (
        registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
        drive_id INTEGER NOT NULL REFERENCES drives(drive_id) ON DELETE CASCADE,
        registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT NOT NULL DEFAULT 'Applied'
            CHECK (status IN ('Applied', 'In_Process', 'Selected', 'Rejected', 'Withdrawn')),
        UNIQUE (student_id, drive_id)
    );

    CREATE TABLE round_progress (
        progress_id INTEGER PRIMARY KEY AUTOINCREMENT,
        registration_id INTEGER NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
        round_id INTEGER NOT NULL REFERENCES drive_rounds(round_id) ON DELETE CASCADE,
        attendance TEXT DEFAULT 'Pending' 
            CHECK (attendance IN ('Pending', 'Present', 'Absent')),
        score REAL,
        status TEXT NOT NULL DEFAULT 'Pending'
            CHECK (status IN ('Pending', 'Cleared', 'Rejected', 'Waitlisted')),
        feedback TEXT,
        evaluated_at DATETIME,
        UNIQUE (registration_id, round_id)
    );

    CREATE TABLE offers (
        offer_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
        drive_id INTEGER NOT NULL REFERENCES drives(drive_id) ON DELETE CASCADE,
        offer_type TEXT NOT NULL 
            CHECK (offer_type IN ('Internship', 'Placement')),
        offered_stipend REAL DEFAULT 0.00,
        offered_ctc REAL DEFAULT 0.00,
        offer_letter_url TEXT,
        acceptance_status TEXT NOT NULL DEFAULT 'Pending'
            CHECK (acceptance_status IN ('Pending', 'Accepted', 'Declined', 'Revoked')),
        response_date DATETIME,
        issued_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (student_id, drive_id)
    );
    """)

    # Seed initial sample data
    cursor.executescript("""
    INSERT INTO departments (dept_code, dept_name) VALUES
    ('CSE', 'Computer Science & Engineering'),
    ('IT', 'Information Technology'),
    ('ECE', 'Electronics & Communication Engineering'),
    ('MECH', 'Mechanical Engineering');

    INSERT INTO students (roll_no, first_name, last_name, email, phone, dept_id, batch_year, cgpa, active_backlogs, placement_status) VALUES
    ('2025CS101', 'Aarav', 'Sharma',    'aarav.sharma@college.edu',   '9876543210', 1, 2025, 9.15, 0, 'Placed'),
    ('2025CS102', 'Priya', 'Patel',     'priya.patel@college.edu',    '9876543211', 1, 2025, 8.70, 0, 'Unplaced'),
    ('2025IT101', 'Rohan', 'Verma',     'rohan.verma@college.edu',    '9876543212', 2, 2025, 7.80, 0, 'Unplaced'),
    ('2025IT102', 'Sneha', 'Reddy',     'sneha.reddy@college.edu',    '9876543213', 2, 2025, 6.90, 1, 'Unplaced'),
    ('2025EC101', 'Vikram', 'Iyer',     'vikram.iyer@college.edu',    '9876543214', 3, 2025, 8.40, 0, 'Unplaced'),
    ('2025ME101', 'Arjun', 'Nair',      'arjun.nair@college.edu',     '9876543215', 4, 2025, 7.20, 0, 'Unplaced');

    INSERT INTO companies (name, industry, website, hr_name, hr_email, hr_phone, company_tier) VALUES
    ('Google India',       'Software / Internet',  'https://careers.google.com',    'Ananya Sen',     'ananya@google.com',    '9112233445', 'Tier 1'),
    ('Microsoft',          'Technology',           'https://careers.microsoft.com', 'David Miller',   'david@microsoft.com', '9112233446', 'Tier 1'),
    ('Tata Consultancy',   'IT Services',          'https://tcs.com/careers',       'Rajesh Gupta',   'rajesh@tcs.com',       '9112233447', 'Tier 3'),
    ('Qualcomm',           'Semiconductors / ECE', 'https://qualcomm.com',          'Meera Pillai',   'meera@qualcomm.com',   '9112233448', 'Tier 2');
    """)

    # Drives with dates relative to now
    now = datetime.now()
    d1_start = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    d1_end = (now + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    d2_start = (now - timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S")
    d2_end = (now + timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
    d3_start = (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    d3_end = (now + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO drives (company_id, title, job_description, drive_type, stipend_monthly, ctc_annual, min_cgpa, max_backlogs, eligible_batch_year, work_location, reg_start_date, reg_deadline, status) VALUES
    (1, 'Software Engineering Intern', '2-month summer internship for 2025 batch.', 'Internship', 110000.00, 0.00, 8.00, 0, 2025, 'Bangalore / Hybrid', ?, ?, 'Ongoing'),
    (2, 'Software Engineer (Full-Time)', 'Full-time graduate role with core engineering teams.', 'Full_Time', 0.00, 24.50, 7.50, 0, 2025, 'Hyderabad / Redmond', ?, ?, 'Ongoing'),
    (4, 'Hardware Firmware Associate', 'Embedded systems and ASIC validation.', 'Internship_Plus_PPO', 45000.00, 14.00, 7.00, 0, 2025, 'Bangalore / Chennai', ?, ?, 'Registration_Open')
    """, (d1_start, d1_end, d2_start, d2_end, d3_start, d3_end))

    # Eligible departments
    cursor.executescript("""
    INSERT INTO drive_eligible_departments (drive_id, dept_id) VALUES 
    (1, 1), (1, 2),
    (2, 1), (2, 2), (2, 3),
    (3, 1), (3, 3);

    -- Google rounds
    INSERT INTO drive_rounds (drive_id, round_number, round_name, round_mode, round_date, cutoff_score) VALUES
    (1, 1, 'Online Coding Assessment', 'Online', '2025-08-10 10:00:00', 75.00),
    (1, 2, 'Technical Interview 1',     'Online', '2025-08-15 14:00:00', 70.00),
    (1, 3, 'Technical Interview 2',     'Online', '2025-08-20 11:00:00', 70.00),
    (1, 4, 'Googliness & Leadership',   'Online', '2025-08-25 16:00:00', 60.00);

    -- Microsoft rounds
    INSERT INTO drive_rounds (drive_id, round_number, round_name, round_mode, round_date, cutoff_score) VALUES
    (2, 1, 'Online Test (DSA + CS Core)', 'Online', '2025-08-05 10:00:00', 70.00),
    (2, 2, 'System Design & Problem Solving', 'Online', '2025-08-12 11:30:00', 75.00),
    (2, 3, 'Director / Bar Raiser Interview', 'Online', '2025-08-18 15:00:00', 80.00);

    -- Qualcomm rounds
    INSERT INTO drive_rounds (drive_id, round_number, round_name, round_mode, round_date, cutoff_score) VALUES
    (3, 1, 'Aptitude & Digital Electronics Test', 'Online', '2025-08-30 09:30:00', 65.00),
    (3, 2, 'Verilog / C Embedded Interview',     'Offline', '2025-09-05 10:00:00', 70.00);

    -- Registrations
    INSERT INTO registrations (student_id, drive_id, status) VALUES
    (1, 1, 'In_Process'),
    (2, 1, 'In_Process'),
    (1, 2, 'Selected'),
    (2, 2, 'In_Process'),
    (3, 2, 'Rejected'),
    (5, 2, 'In_Process');

    -- Microsoft Round Progress
    -- Round 1 (Online Test - round_id 5)
    INSERT INTO round_progress (registration_id, round_id, attendance, score, status, feedback, evaluated_at) VALUES
    (3, 5, 'Present', 95.00, 'Cleared', 'Outstanding performance in algorithms', CURRENT_TIMESTAMP),
    (4, 5, 'Present', 88.00, 'Cleared', 'Solid problem solving',                 CURRENT_TIMESTAMP),
    (5, 5, 'Present', 55.00, 'Rejected', 'Failed threshold in tree problems',   CURRENT_TIMESTAMP),
    (6, 5, 'Present', 82.00, 'Cleared', 'Good core fundamentals',                CURRENT_TIMESTAMP);

    -- Round 2 (System Design - round_id 6)
    INSERT INTO round_progress (registration_id, round_id, attendance, score, status, feedback, evaluated_at) VALUES
    (3, 6, 'Present', 90.00, 'Cleared', 'Optimized data structures and clean code', CURRENT_TIMESTAMP),
    (4, 6, 'Present', 78.00, 'Cleared', 'Good communication, solved edge cases',    CURRENT_TIMESTAMP),
    (6, 6, 'Present', 60.00, 'Rejected', 'Struggled with concurrency questions',    CURRENT_TIMESTAMP);

    -- Round 3 (Bar Raiser - round_id 7)
    INSERT INTO round_progress (registration_id, round_id, attendance, score, status, feedback, evaluated_at) VALUES
    (3, 7, 'Present', 92.00, 'Cleared', 'Exceptional technical depth and leadership fit', CURRENT_TIMESTAMP);

    -- Offer
    INSERT INTO offers (student_id, drive_id, offer_type, offered_stipend, offered_ctc, offer_letter_url, acceptance_status, response_date) VALUES
    (1, 2, 'Placement', 0.00, 24.50, 'https://cdn.college.edu/offers/2025CS101_microsoft.pdf', 'Accepted', CURRENT_TIMESTAMP);
    """)

    conn.commit()
    conn.close()
    print("Database initialized successfully at:", DB_PATH)

if __name__ == "__main__":
    init_database()
