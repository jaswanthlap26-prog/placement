-- =============================================================================
-- Sample Seed Data: Internship & Placement Tracker
-- Populates departments, students, companies, drives, rounds, registrations,
-- round progress, and final job/internship offers.
-- =============================================================================

-- 1. Insert Departments
INSERT INTO departments (dept_code, dept_name) VALUES
('CSE', 'Computer Science & Engineering'),
('IT',  'Information Technology'),
('ECE', 'Electronics & Communication Engineering'),
('MECH', 'Mechanical Engineering');

-- 2. Insert Students
INSERT INTO students (roll_no, first_name, last_name, email, phone, dept_id, batch_year, cgpa, active_backlogs, placement_status) VALUES
('2024CS101', 'Aarav', 'Sharma',    'aarav.sharma@college.edu',   '9876543210', 1, 2025, 9.15, 0, 'Unplaced'),
('2024CS102', 'Priya', 'Patel',     'priya.patel@college.edu',    '9876543211', 1, 2025, 8.70, 0, 'Unplaced'),
('2024IT101', 'Rohan', 'Verma',     'rohan.verma@college.edu',    '9876543212', 2, 2025, 7.80, 0, 'Unplaced'),
('2024IT102', 'Sneha', 'Reddy',     'sneha.reddy@college.edu',    '9876543213', 2, 2025, 6.90, 1, 'Unplaced'),
('2024EC101', 'Vikram', 'Iyer',     'vikram.iyer@college.edu',    '9876543214', 3, 2025, 8.40, 0, 'Unplaced'),
('2024ME101', 'Arjun', 'Nair',      'arjun.nair@college.edu',     '9876543215', 4, 2025, 7.20, 0, 'Unplaced');

-- 3. Insert Companies
INSERT INTO companies (name, industry, website, hr_name, hr_email, hr_phone, company_tier) VALUES
('Google India',       'Software / Internet',  'https://careers.google.com',    'Ananya Sen',     'ananya@google.com',    '9112233445', 'Tier 1'),
('Microsoft',          'Technology',           'https://careers.microsoft.com', 'David Miller',   'david@microsoft.com', '9112233446', 'Tier 1'),
('Tata Consultancy',   'IT Services',          'https://tcs.com/careers',       'Rajesh Gupta',   'rajesh@tcs.com',       '9112233447', 'Tier 3'),
('Qualcomm',           'Semiconductors / ECE', 'https://qualcomm.com',          'Meera Pillai',   'meera@qualcomm.com',   '9112233448', 'Tier 2');

-- 4. Insert Drives
-- Drive 1: Google Summer Internship 2025
INSERT INTO drives (company_id, title, job_description, drive_type, stipend_monthly, ctc_annual, min_cgpa, max_backlogs, eligible_batch_year, reg_start_date, reg_deadline, status) VALUES
(1, 'Software Engineering Intern', '2-month summer internship for 2025 batch.', 'Internship', 110000.00, 0.00, 8.00, 0, 2025, CURRENT_TIMESTAMP - INTERVAL '10 days', CURRENT_TIMESTAMP + INTERVAL '10 days', 'Ongoing'),
-- Drive 2: Microsoft Full-Time SDE
(2, 'Software Engineer (Full-Time)', 'Full-time graduate role with core engineering teams.', 'Full_Time', 0.00, 24.50, 7.50, 0, 2025, CURRENT_TIMESTAMP - INTERVAL '15 days', CURRENT_TIMESTAMP + INTERVAL '5 days', 'Ongoing'),
-- Drive 3: Qualcomm Hardware & Embedded Engineer
(4, 'Hardware Firmware Associate', 'Embedded systems and ASIC validation.', 'Internship_Plus_PPO', 45000.00, 14.00, 7.00, 0, 2025, CURRENT_TIMESTAMP - INTERVAL '5 days', CURRENT_TIMESTAMP + INTERVAL '12 days', 'Registration_Open');

-- 5. Eligible Departments per Drive
-- Google: CSE (1), IT (2)
INSERT INTO drive_eligible_departments (drive_id, dept_id) VALUES (1, 1), (1, 2);
-- Microsoft: CSE (1), IT (2), ECE (3)
INSERT INTO drive_eligible_departments (drive_id, dept_id) VALUES (2, 1), (2, 2), (2, 3);
-- Qualcomm: ECE (3), CSE (1)
INSERT INTO drive_eligible_departments (drive_id, dept_id) VALUES (3, 3), (3, 1);

-- 6. Insert Drive Rounds
-- Google Intern Rounds
INSERT INTO drive_rounds (drive_id, round_number, round_name, round_mode, round_date, cutoff_score) VALUES
(1, 1, 'Online Coding Assessment', 'Online', CURRENT_TIMESTAMP - INTERVAL '4 days', 75.00),
(1, 2, 'Technical Interview 1',     'Online', CURRENT_TIMESTAMP - INTERVAL '2 days', 70.00),
(1, 3, 'Technical Interview 2',     'Online', CURRENT_TIMESTAMP + INTERVAL '1 day',  70.00),
(1, 4, 'Googliness & Leadership',   'Online', CURRENT_TIMESTAMP + INTERVAL '3 days', 60.00);

-- Microsoft SDE Rounds
INSERT INTO drive_rounds (drive_id, round_number, round_name, round_mode, round_date, cutoff_score) VALUES
(2, 1, 'Online Test (DSA + CS Core)', 'Online', CURRENT_TIMESTAMP - INTERVAL '7 days', 70.00),
(2, 2, 'System Design & Problem Solving', 'Online', CURRENT_TIMESTAMP - INTERVAL '3 days', 75.00),
(2, 3, 'Director / Bar Raiser Interview', 'Online', CURRENT_TIMESTAMP - INTERVAL '1 day', 80.00);

-- 7. Insert Registrations
-- Temporarily register students (Disable eligibility trigger if needed during migration, or register students that fulfill criteria)
INSERT INTO registrations (student_id, drive_id, status) VALUES
(1, 1, 'In_Process'), -- Aarav in Google
(2, 1, 'In_Process'), -- Priya in Google
(1, 2, 'Selected'),   -- Aarav in Microsoft
(2, 2, 'In_Process'), -- Priya in Microsoft
(3, 2, 'Rejected'),   -- Rohan in Microsoft (CGPA 7.80 meets 7.50 min)
(5, 2, 'In_Process'); -- Vikram (ECE) in Microsoft

-- 8. Insert Round Progress
-- Microsoft Drive Progress
-- Round 1: Online Test
INSERT INTO round_progress (registration_id, round_id, attendance, score, status, feedback, evaluated_at) VALUES
(3, 5, 'Present', 95.00, 'Cleared', 'Outstanding performance in algorithms', CURRENT_TIMESTAMP - INTERVAL '6 days'), -- Aarav
(4, 5, 'Present', 88.00, 'Cleared', 'Solid problem solving',                 CURRENT_TIMESTAMP - INTERVAL '6 days'), -- Priya
(5, 5, 'Present', 55.00, 'Rejected', 'Failed threshold in tree problems',   CURRENT_TIMESTAMP - INTERVAL '6 days'), -- Rohan
(6, 5, 'Present', 82.00, 'Cleared', 'Good fundamentals',                     CURRENT_TIMESTAMP - INTERVAL '6 days'); -- Vikram

-- Round 2: Problem Solving
INSERT INTO round_progress (registration_id, round_id, attendance, score, status, feedback, evaluated_at) VALUES
(3, 6, 'Present', 90.00, 'Cleared', 'Optimized data structures and clean code', CURRENT_TIMESTAMP - INTERVAL '2 days'),
(4, 6, 'Present', 78.00, 'Cleared', 'Good communication, solved corner cases',  CURRENT_TIMESTAMP - INTERVAL '2 days'),
(6, 6, 'Present', 60.00, 'Rejected', 'Struggled with concurrency questions',    CURRENT_TIMESTAMP - INTERVAL '2 days');

-- Round 3: Bar Raiser
INSERT INTO round_progress (registration_id, round_id, attendance, score, status, feedback, evaluated_at) VALUES
(3, 7, 'Present', 92.00, 'Cleared', 'Exceptional fit and vision', CURRENT_TIMESTAMP - INTERVAL '1 day');

-- 9. Insert Final Offers
INSERT INTO offers (student_id, drive_id, offer_type, offered_stipend, offered_ctc, offer_letter_url, acceptance_status, response_date) VALUES
(1, 2, 'Placement', 0.00, 24.50, 'https://cdn.college.edu/offers/2024CS101_msft.pdf', 'Accepted', CURRENT_TIMESTAMP);
