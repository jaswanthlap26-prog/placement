-- =============================================================================
-- Operational & Analytical Queries: Internship & Placement Tracker
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. STUDENT PROGRESS TRACKER (Full Application Journey)
-- Returns the detailed progress of a specific student across all applied drives.
-- -----------------------------------------------------------------------------
SELECT 
    s.roll_no,
    s.first_name || ' ' || s.last_name AS student_name,
    c.name AS company_name,
    dr.title AS drive_title,
    dr.drive_type,
    r.status AS overall_status,
    dr_round.round_number,
    dr_round.round_name,
    rp.attendance,
    rp.score,
    rp.status AS round_outcome,
    rp.feedback
FROM students s
JOIN registrations r ON s.student_id = r.student_id
JOIN drives dr ON r.drive_id = dr.drive_id
JOIN companies c ON dr.company_id = c.company_id
LEFT JOIN round_progress rp ON r.registration_id = rp.registration_id
LEFT JOIN drive_rounds dr_round ON rp.round_id = dr_round.round_id
WHERE s.roll_no = '2024CS101' -- Replace with any student roll number
ORDER BY dr.drive_id, dr_round.round_number ASC;

-- -----------------------------------------------------------------------------
-- 2. DRIVE FUNNEL & CONVERSION ANALYSIS (Per Round Breakdown)
-- Tracks how many candidates entered, cleared, or were rejected in each round.
-- -----------------------------------------------------------------------------
SELECT 
    c.name AS company,
    dr.title AS drive,
    dr_r.round_number,
    dr_r.round_name,
    COUNT(rp.progress_id) AS candidates_appeared,
    COUNT(CASE WHEN rp.status = 'Cleared' THEN 1 END) AS cleared_count,
    COUNT(CASE WHEN rp.status = 'Rejected' THEN 1 END) AS rejected_count,
    ROUND(
        (COUNT(CASE WHEN rp.status = 'Cleared' THEN 1 END)::NUMERIC / 
        NULLIF(COUNT(rp.progress_id), 0)) * 100, 2
    ) AS pass_percentage
FROM drives dr
JOIN companies c ON dr.company_id = c.company_id
JOIN drive_rounds dr_r ON dr.drive_id = dr_r.drive_id
LEFT JOIN round_progress rp ON dr_r.round_id = rp.round_id
WHERE dr.drive_id = 2 -- Microsoft drive
GROUP BY c.name, dr.title, dr_r.round_number, dr_r.round_name
ORDER BY dr_r.round_number ASC;

-- -----------------------------------------------------------------------------
-- 3. CHECK ELIGIBLE STUDENTS FOR AN UPCOMING / OPEN DRIVE
-- Automatically identifies all students in the institution eligible to apply.
-- -----------------------------------------------------------------------------
SELECT 
    s.student_id,
    s.roll_no,
    s.first_name || ' ' || s.last_name AS full_name,
    d.dept_code,
    s.cgpa,
    s.active_backlogs,
    s.placement_status
FROM students s
JOIN departments d ON s.dept_id = d.dept_id
WHERE s.batch_year = (SELECT eligible_batch_year FROM drives WHERE drive_id = 3)
  AND s.cgpa >= (SELECT min_cgpa FROM drives WHERE drive_id = 3)
  AND s.active_backlogs <= (SELECT max_backlogs FROM drives WHERE drive_id = 3)
  AND s.dept_id IN (SELECT dept_id FROM drive_eligible_departments WHERE drive_id = 3)
  AND s.student_id NOT IN (SELECT student_id FROM registrations WHERE drive_id = 3)
ORDER BY s.cgpa DESC;

-- -----------------------------------------------------------------------------
-- 4. BATCH ADVANCEMENT: SHORTLIST CANDIDATES FOR NEXT ROUND
-- Selects students who cleared Round N and are ready to be enrolled into Round N+1.
-- -----------------------------------------------------------------------------
SELECT 
    r.registration_id,
    s.roll_no,
    s.first_name || ' ' || s.last_name AS student_name,
    s.email,
    s.phone,
    prev_rp.score AS last_round_score
FROM registrations r
JOIN students s ON r.student_id = s.student_id
JOIN round_progress prev_rp ON r.registration_id = prev_rp.registration_id
JOIN drive_rounds prev_r ON prev_rp.round_id = prev_r.round_id
WHERE r.drive_id = 2
  AND prev_r.round_number = 2       -- Cleared Round 2
  AND prev_rp.status = 'Cleared'
  AND NOT EXISTS (                   -- Not yet scheduled for Round 3
      SELECT 1 FROM round_progress next_rp
      JOIN drive_rounds next_r ON next_rp.round_id = next_r.round_id
      WHERE next_rp.registration_id = r.registration_id
        AND next_r.round_number = 3
  );

-- -----------------------------------------------------------------------------
-- 5. PLACEMENT & INTERNSHIP METRICS DASHBOARD
-- High-level institutional metrics for placement officers.
-- -----------------------------------------------------------------------------
SELECT 
    COUNT(DISTINCT s.student_id) AS total_enrolled_students,
    COUNT(DISTINCT CASE WHEN s.placement_status IN ('Placed', 'Dream_Placed') THEN s.student_id END) AS total_placed,
    COUNT(DISTINCT CASE WHEN s.placement_status = 'Internship_Only' THEN s.student_id END) AS total_interns_only,
    COUNT(DISTINCT CASE WHEN s.placement_status = 'Unplaced' THEN s.student_id END) AS total_unplaced,
    ROUND(
        (COUNT(DISTINCT CASE WHEN s.placement_status IN ('Placed', 'Dream_Placed') THEN s.student_id END)::NUMERIC / 
        NULLIF(COUNT(DISTINCT s.student_id), 0)) * 100, 2
    ) AS institutional_placement_rate,
    ROUND(AVG(o.offered_ctc), 2) AS average_ctc_lpa,
    MAX(o.offered_ctc) AS highest_ctc_lpa
FROM students s
LEFT JOIN offers o ON s.student_id = o.student_id AND o.acceptance_status = 'Accepted';

-- -----------------------------------------------------------------------------
-- 6. UNPLACED CANDIDATES WITH HIGH CGPA (Priority Attention List)
-- -----------------------------------------------------------------------------
SELECT 
    s.roll_no,
    s.first_name || ' ' || s.last_name AS student_name,
    d.dept_code,
    s.cgpa,
    s.active_backlogs,
    COUNT(r.registration_id) AS drives_applied,
    COUNT(CASE WHEN r.status = 'Rejected' THEN 1 END) AS rejections_count
FROM students s
JOIN departments d ON s.dept_id = d.dept_id
LEFT JOIN registrations r ON s.student_id = r.student_id
WHERE s.placement_status = 'Unplaced'
GROUP BY s.roll_no, s.first_name, s.last_name, d.dept_code, s.cgpa, s.active_backlogs
HAVING s.cgpa >= 7.50
ORDER BY s.cgpa DESC;
