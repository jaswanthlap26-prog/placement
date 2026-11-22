-- =============================================================================
-- Database Project: Internship & Placement Tracker
-- Description: Complete relational schema for managing company recruitment drives,
--              student registrations, multi-round progress tracking, and offers.
-- Compatible with: PostgreSQL / Modern Relational DBMS
-- =============================================================================

-- Drop tables if they already exist (in reverse dependency order)
DROP TABLE IF EXISTS offers CASCADE;
DROP TABLE IF EXISTS round_progress CASCADE;
DROP TABLE IF EXISTS registrations CASCADE;
DROP TABLE IF EXISTS drive_rounds CASCADE;
DROP TABLE IF EXISTS drive_eligible_departments CASCADE;
DROP TABLE IF EXISTS drives CASCADE;
DROP TABLE IF EXISTS companies CASCADE;
DROP TABLE IF EXISTS students CASCADE;
DROP TABLE IF EXISTS departments CASCADE;

-- -----------------------------------------------------------------------------
-- 1. DEPARTMENTS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE departments (
    dept_id SERIAL PRIMARY KEY,
    dept_code VARCHAR(10) NOT NULL UNIQUE,
    dept_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 2. STUDENTS TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE students (
    student_id SERIAL PRIMARY KEY,
    roll_no VARCHAR(20) NOT NULL UNIQUE,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(15) NOT NULL,
    dept_id INT NOT NULL REFERENCES departments(dept_id) ON DELETE RESTRICT,
    batch_year INT NOT NULL,
    cgpa NUMERIC(4, 2) NOT NULL CHECK (cgpa >= 0.00 AND cgpa <= 10.00),
    active_backlogs INT NOT NULL DEFAULT 0 CHECK (active_backlogs >= 0),
    placement_status VARCHAR(20) NOT NULL DEFAULT 'Unplaced'
        CHECK (placement_status IN ('Unplaced', 'Internship_Only', 'Placed', 'Dream_Placed')),
    resume_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 3. COMPANIES TABLE
-- -----------------------------------------------------------------------------
CREATE TABLE companies (
    company_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    industry VARCHAR(100),
    website VARCHAR(150),
    hr_name VARCHAR(100),
    hr_email VARCHAR(100) NOT NULL,
    hr_phone VARCHAR(20),
    company_tier VARCHAR(20) DEFAULT 'Tier 2'
        CHECK (company_tier IN ('Tier 1', 'Tier 2', 'Tier 3', 'Startup')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 4. DRIVES (Job / Internship Openings)
-- -----------------------------------------------------------------------------
CREATE TABLE drives (
    drive_id SERIAL PRIMARY KEY,
    company_id INT NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    title VARCHAR(150) NOT NULL,
    job_description TEXT,
    drive_type VARCHAR(30) NOT NULL 
        CHECK (drive_type IN ('Internship', 'Full_Time', 'Internship_Plus_PPO')),
    stipend_monthly NUMERIC(10, 2) DEFAULT 0.00,
    ctc_annual NUMERIC(12, 2) DEFAULT 0.00,
    min_cgpa NUMERIC(4, 2) NOT NULL DEFAULT 6.00 CHECK (min_cgpa >= 0.00 AND min_cgpa <= 10.00),
    max_backlogs INT NOT NULL DEFAULT 0 CHECK (max_backlogs >= 0),
    eligible_batch_year INT NOT NULL,
    work_location VARCHAR(100) DEFAULT 'Flexible / Hybrid',
    reg_start_date TIMESTAMP NOT NULL,
    reg_deadline TIMESTAMP NOT NULL,
    status VARCHAR(25) NOT NULL DEFAULT 'Upcoming'
        CHECK (status IN ('Upcoming', 'Registration_Open', 'Ongoing', 'Completed', 'Cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_dates CHECK (reg_deadline > reg_start_date)
);

-- -----------------------------------------------------------------------------
-- 5. DRIVE ELIGIBLE DEPARTMENTS (Junction Table)
-- -----------------------------------------------------------------------------
CREATE TABLE drive_eligible_departments (
    drive_id INT NOT NULL REFERENCES drives(drive_id) ON DELETE CASCADE,
    dept_id INT NOT NULL REFERENCES departments(dept_id) ON DELETE CASCADE,
    PRIMARY KEY (drive_id, dept_id)
);

-- -----------------------------------------------------------------------------
-- 6. DRIVE ROUNDS (Workflow Stages)
-- -----------------------------------------------------------------------------
CREATE TABLE drive_rounds (
    round_id SERIAL PRIMARY KEY,
    drive_id INT NOT NULL REFERENCES drives(drive_id) ON DELETE CASCADE,
    round_number INT NOT NULL,
    round_name VARCHAR(100) NOT NULL,
    round_mode VARCHAR(20) NOT NULL DEFAULT 'Online' 
        CHECK (round_mode IN ('Online', 'Offline', 'Hybrid')),
    round_date TIMESTAMP,
    venue VARCHAR(100),
    cutoff_score NUMERIC(5, 2),
    UNIQUE (drive_id, round_number)
);

-- -----------------------------------------------------------------------------
-- 7. REGISTRATIONS (Student Application to Drive)
-- -----------------------------------------------------------------------------
CREATE TABLE registrations (
    registration_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    drive_id INT NOT NULL REFERENCES drives(drive_id) ON DELETE CASCADE,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(25) NOT NULL DEFAULT 'Applied'
        CHECK (status IN ('Applied', 'In_Process', 'Selected', 'Rejected', 'Withdrawn')),
    UNIQUE (student_id, drive_id)
);

-- -----------------------------------------------------------------------------
-- 8. ROUND PROGRESS (Tracking progress across rounds)
-- -----------------------------------------------------------------------------
CREATE TABLE round_progress (
    progress_id SERIAL PRIMARY KEY,
    registration_id INT NOT NULL REFERENCES registrations(registration_id) ON DELETE CASCADE,
    round_id INT NOT NULL REFERENCES drive_rounds(round_id) ON DELETE CASCADE,
    attendance VARCHAR(15) DEFAULT 'Pending' 
        CHECK (attendance IN ('Pending', 'Present', 'Absent')),
    score NUMERIC(5, 2),
    status VARCHAR(20) NOT NULL DEFAULT 'Pending'
        CHECK (status IN ('Pending', 'Cleared', 'Rejected', 'Waitlisted')),
    feedback TEXT,
    evaluated_at TIMESTAMP,
    UNIQUE (registration_id, round_id)
);

-- -----------------------------------------------------------------------------
-- 9. OFFERS (Final Selection & Acceptance)
-- -----------------------------------------------------------------------------
CREATE TABLE offers (
    offer_id SERIAL PRIMARY KEY,
    student_id INT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    drive_id INT NOT NULL REFERENCES drives(drive_id) ON DELETE CASCADE,
    offer_type VARCHAR(20) NOT NULL 
        CHECK (offer_type IN ('Internship', 'Placement')),
    offered_stipend NUMERIC(10, 2) DEFAULT 0.00,
    offered_ctc NUMERIC(12, 2) DEFAULT 0.00,
    offer_letter_url VARCHAR(255),
    acceptance_status VARCHAR(20) NOT NULL DEFAULT 'Pending'
        CHECK (acceptance_status IN ('Pending', 'Accepted', 'Declined', 'Revoked')),
    response_date TIMESTAMP,
    issued_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (student_id, drive_id)
);

-- =============================================================================
-- INDEXES FOR HIGH QUERY PERFORMANCE
-- =============================================================================
CREATE INDEX idx_students_roll_no ON students(roll_no);
CREATE INDEX idx_students_dept ON students(dept_id);
CREATE INDEX idx_students_batch ON students(batch_year);
CREATE INDEX idx_drives_company ON drives(company_id);
CREATE INDEX idx_drives_status ON drives(status);
CREATE INDEX idx_registrations_student ON registrations(student_id);
CREATE INDEX idx_registrations_drive ON registrations(drive_id);
CREATE INDEX idx_round_progress_reg ON round_progress(registration_id);
CREATE INDEX idx_round_progress_round ON round_progress(round_id);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- View 1: Real-time Student Application & Live Progress Status
CREATE OR REPLACE VIEW vw_student_progress_tracker AS
SELECT 
    s.student_id,
    s.roll_no,
    s.first_name || ' ' || s.last_name AS student_name,
    d.dept_code,
    c.name AS company_name,
    dr.title AS drive_title,
    dr.drive_type,
    r.registration_id,
    r.registered_at,
    r.status AS application_status,
    COALESCE(curr_round.round_name, 'Registration Stage') AS latest_evaluated_round,
    COALESCE(rp.status, 'Applied') AS latest_round_status,
    o.acceptance_status AS offer_status,
    o.offered_ctc
FROM registrations r
JOIN students s ON r.student_id = s.student_id
JOIN departments d ON s.dept_id = d.dept_id
JOIN drives dr ON r.drive_id = dr.drive_id
JOIN companies c ON dr.company_id = c.company_id
LEFT JOIN (
    -- Get highest round evaluated for this registration
    SELECT DISTINCT ON (rp_inner.registration_id)
        rp_inner.registration_id,
        rp_inner.round_id,
        rp_inner.status,
        dr_inner.round_number
    FROM round_progress rp_inner
    JOIN drive_rounds dr_inner ON rp_inner.round_id = dr_inner.round_id
    ORDER BY rp_inner.registration_id, dr_inner.round_number DESC
) rp ON r.registration_id = rp.registration_id
LEFT JOIN drive_rounds curr_round ON rp.round_id = curr_round.round_id
LEFT JOIN offers o ON r.student_id = o.student_id AND r.drive_id = o.drive_id;

-- View 2: Drive Funnel & Conversion Analytics
CREATE OR REPLACE VIEW vw_drive_funnel_summary AS
SELECT 
    dr.drive_id,
    c.name AS company_name,
    dr.title AS drive_title,
    dr.drive_type,
    COUNT(DISTINCT r.registration_id) AS total_applicants,
    COUNT(DISTINCT CASE WHEN r.status = 'In_Process' THEN r.registration_id END) AS currently_in_process,
    COUNT(DISTINCT CASE WHEN r.status = 'Selected' THEN r.registration_id END) AS total_selected,
    COUNT(DISTINCT CASE WHEN r.status = 'Rejected' THEN r.registration_id END) AS total_rejected,
    COUNT(DISTINCT o.offer_id) AS offers_issued,
    COUNT(DISTINCT CASE WHEN o.acceptance_status = 'Accepted' THEN o.offer_id END) AS offers_accepted
FROM drives dr
JOIN companies c ON dr.company_id = c.company_id
LEFT JOIN registrations r ON dr.drive_id = r.drive_id
LEFT JOIN offers o ON dr.drive_id = o.drive_id
GROUP BY dr.drive_id, c.name, dr.title, dr.drive_type;

-- View 3: Department-wise Placement Statistics
CREATE OR REPLACE VIEW vw_department_placement_stats AS
SELECT 
    d.dept_code,
    d.dept_name,
    COUNT(s.student_id) AS total_students,
    COUNT(CASE WHEN s.placement_status IN ('Placed', 'Dream_Placed') THEN 1 END) AS students_placed,
    COUNT(CASE WHEN s.placement_status = 'Internship_Only' THEN 1 END) AS internship_only,
    ROUND(
        (COUNT(CASE WHEN s.placement_status IN ('Placed', 'Dream_Placed') THEN 1 END)::NUMERIC / 
        NULLIF(COUNT(s.student_id), 0)) * 100, 2
    ) AS placement_percentage,
    ROUND(AVG(o.offered_ctc), 2) AS average_ctc_in_lpa,
    MAX(o.offered_ctc) AS highest_ctc_in_lpa
FROM departments d
LEFT JOIN students s ON d.dept_id = s.dept_id
LEFT JOIN offers o ON s.student_id = o.student_id AND o.acceptance_status = 'Accepted'
GROUP BY d.dept_code, d.dept_name;

-- =============================================================================
-- TRIGGERS & BUSINESS LOGIC (PostgreSQL Syntax)
-- =============================================================================

-- Trigger Function 1: Check student eligibility before registration
CREATE OR REPLACE FUNCTION fn_check_student_eligibility()
RETURNS TRIGGER AS $$
DECLARE
    v_cgpa NUMERIC(4, 2);
    v_backlogs INT;
    v_batch INT;
    v_dept INT;
    v_min_cgpa NUMERIC(4, 2);
    v_max_backlogs INT;
    v_eligible_batch INT;
    v_reg_deadline TIMESTAMP;
    v_dept_eligible BOOLEAN;
BEGIN
    -- Fetch student details
    SELECT cgpa, active_backlogs, batch_year, dept_id
    INTO v_cgpa, v_backlogs, v_batch, v_dept
    FROM students WHERE student_id = NEW.student_id;

    -- Fetch drive requirements
    SELECT min_cgpa, max_backlogs, eligible_batch_year, reg_deadline
    INTO v_min_cgpa, v_max_backlogs, v_eligible_batch, v_reg_deadline
    FROM drives WHERE drive_id = NEW.drive_id;

    -- Check 1: Deadline validation
    IF CURRENT_TIMESTAMP > v_reg_deadline THEN
        RAISE EXCEPTION 'Registration deadline has passed for this drive.';
    END IF;

    -- Check 2: CGPA validation
    IF v_cgpa < v_min_cgpa THEN
        RAISE EXCEPTION 'Student CGPA (%) is below minimum required CGPA (%).', v_cgpa, v_min_cgpa;
    END IF;

    -- Check 3: Active backlogs validation
    IF v_backlogs > v_max_backlogs THEN
        RAISE EXCEPTION 'Student has % backlogs. Allowed limit is %.', v_backlogs, v_max_backlogs;
    END IF;

    -- Check 4: Batch year
    IF v_batch <> v_eligible_batch THEN
        RAISE EXCEPTION 'Student batch (%) does not match drive eligible batch (%).', v_batch, v_eligible_batch;
    END IF;

    -- Check 5: Department eligibility
    SELECT EXISTS (
        SELECT 1 FROM drive_eligible_departments 
        WHERE drive_id = NEW.drive_id AND dept_id = v_dept
    ) INTO v_dept_eligible;

    IF NOT v_dept_eligible THEN
        RAISE EXCEPTION 'Student department is not eligible for this drive.';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_verify_eligibility_before_register
BEFORE INSERT ON registrations
FOR EACH ROW
EXECUTE FUNCTION fn_check_student_eligibility();

-- Trigger Function 2: Update student placement status when an offer is accepted
CREATE OR REPLACE FUNCTION fn_update_placement_status_on_offer()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.acceptance_status = 'Accepted' THEN
        IF NEW.offer_type = 'Internship' THEN
            UPDATE students 
            SET placement_status = CASE 
                WHEN placement_status IN ('Placed', 'Dream_Placed') THEN placement_status
                ELSE 'Internship_Only'
            END
            WHERE student_id = NEW.student_id;
        ELSIF NEW.offer_type = 'Placement' THEN
            UPDATE students 
            SET placement_status = CASE 
                WHEN NEW.offered_ctc >= 15.00 THEN 'Dream_Placed'
                ELSE 'Placed'
            END
            WHERE student_id = NEW.student_id;
        END IF;

        -- Update registration status to 'Selected'
        UPDATE registrations
        SET status = 'Selected'
        WHERE student_id = NEW.student_id AND drive_id = NEW.drive_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_on_offer_acceptance
AFTER INSERT OR UPDATE OF acceptance_status ON offers
FOR EACH ROW
EXECUTE FUNCTION fn_update_placement_status_on_offer();
