-- ============================================================
-- TimeTableScheduler — Full DB Setup
-- Run this in SQL*Plus
-- ============================================================

-- ── TABLES ──────────────────────────────────────────────────

CREATE TABLE department (
    dept_id   NUMBER PRIMARY KEY,
    dept_name VARCHAR2(100) NOT NULL UNIQUE,
    building  VARCHAR2(50)
);

CREATE TABLE faculty (
    faculty_id   NUMBER PRIMARY KEY,
    faculty_name VARCHAR2(100) NOT NULL,
    designation  VARCHAR2(50),
    dept_id      NUMBER REFERENCES department(dept_id)
);

CREATE TABLE subject (
    subject_id   NUMBER PRIMARY KEY,
    subject_name VARCHAR2(100) NOT NULL,
    credits      NUMBER CHECK (credits BETWEEN 1 AND 5),
    dept_id      NUMBER REFERENCES department(dept_id)
);

CREATE TABLE class_batch (
    class_id   NUMBER PRIMARY KEY,
    class_name VARCHAR2(50) NOT NULL,
    semester   NUMBER CHECK (semester BETWEEN 1 AND 8),
    dept_id    NUMBER REFERENCES department(dept_id)
);

CREATE TABLE classroom (
    room_id     NUMBER PRIMARY KEY,
    room_number VARCHAR2(20) NOT NULL UNIQUE,
    capacity    NUMBER CHECK (capacity > 0)
);

CREATE TABLE timeslot (
    slot_id    NUMBER PRIMARY KEY,
    day        VARCHAR2(15) CHECK (day IN ('Monday','Tuesday','Wednesday','Thursday','Friday')),
    start_time VARCHAR2(10) NOT NULL,
    end_time   VARCHAR2(10) NOT NULL
);

CREATE TABLE timetable (
    timetable_id NUMBER PRIMARY KEY,
    class_id     NUMBER REFERENCES class_batch(class_id),
    subject_id   NUMBER REFERENCES subject(subject_id),
    faculty_id   NUMBER REFERENCES faculty(faculty_id),
    room_id      NUMBER REFERENCES classroom(room_id),
    slot_id      NUMBER REFERENCES timeslot(slot_id),
    CONSTRAINT uq_faculty_slot UNIQUE (faculty_id, slot_id),
    CONSTRAINT uq_room_slot    UNIQUE (room_id,    slot_id),
    CONSTRAINT uq_class_slot   UNIQUE (class_id,   slot_id)
);

-- Audit log
CREATE TABLE timetable_audit (
    audit_id    NUMBER PRIMARY KEY,
    action      VARCHAR2(50),
    faculty_id  NUMBER,
    slot_id     NUMBER,
    action_time TIMESTAMP DEFAULT SYSTIMESTAMP
);

-- ── SEQUENCES ───────────────────────────────────────────────

CREATE SEQUENCE timetable_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE audit_seq     START WITH 1 INCREMENT BY 1;

-- ── SAMPLE DATA ─────────────────────────────────────────────

INSERT INTO department VALUES (1, 'Computer Science', 'Block A');
INSERT INTO department VALUES (2, 'Artificial Intelligence & ML', 'Block B');
INSERT INTO department VALUES (3, 'Electronics & Communication', 'Block C');

INSERT INTO faculty VALUES (1, 'Dr. Sharma',  'Professor',       1);
INSERT INTO faculty VALUES (2, 'Dr. Rao',     'Assoc. Professor', 2);
INSERT INTO faculty VALUES (3, 'Prof. Mehta', 'Asst. Professor', 1);
INSERT INTO faculty VALUES (4, 'Dr. Nair',    'Professor',       3);

INSERT INTO subject VALUES (1, 'Database Systems',  4, 1);
INSERT INTO subject VALUES (2, 'Machine Learning',  4, 2);
INSERT INTO subject VALUES (3, 'Operating Systems', 3, 1);
INSERT INTO subject VALUES (4, 'Deep Learning',     3, 2);
INSERT INTO subject VALUES (5, 'Digital Circuits',  3, 3);

INSERT INTO class_batch VALUES (1, 'CSE-4A',  4, 1);
INSERT INTO class_batch VALUES (2, 'AIML-4A', 4, 2);
INSERT INTO class_batch VALUES (3, 'ECE-4A',  4, 3);

INSERT INTO classroom VALUES (1, 'LH-101', 60);
INSERT INTO classroom VALUES (2, 'LH-102', 60);
INSERT INTO classroom VALUES (3, 'LH-201', 80);

INSERT INTO timeslot VALUES (1, 'Monday',    '09:00', '10:00');
INSERT INTO timeslot VALUES (2, 'Monday',    '10:00', '11:00');
INSERT INTO timeslot VALUES (3, 'Tuesday',   '09:00', '10:00');
INSERT INTO timeslot VALUES (4, 'Tuesday',   '10:00', '11:00');
INSERT INTO timeslot VALUES (5, 'Wednesday', '09:00', '10:00');
INSERT INTO timeslot VALUES (6, 'Wednesday', '11:00', '12:00');
INSERT INTO timeslot VALUES (7, 'Thursday',  '09:00', '10:00');
INSERT INTO timeslot VALUES (8, 'Friday',    '09:00', '10:00');
INSERT INTO timeslot VALUES (9, 'Friday',    '10:00', '11:00');

INSERT INTO timetable VALUES (timetable_seq.NEXTVAL, 1, 1, 1, 1, 1);
INSERT INTO timetable VALUES (timetable_seq.NEXTVAL, 1, 3, 3, 2, 3);
INSERT INTO timetable VALUES (timetable_seq.NEXTVAL, 2, 2, 2, 3, 2);
INSERT INTO timetable VALUES (timetable_seq.NEXTVAL, 2, 4, 2, 3, 5);
INSERT INTO timetable VALUES (timetable_seq.NEXTVAL, 3, 5, 4, 1, 7);
INSERT INTO timetable VALUES (timetable_seq.NEXTVAL, 1, 1, 1, 2, 8);
INSERT INTO timetable VALUES (timetable_seq.NEXTVAL, 2, 2, 2, 3, 9);

COMMIT;

-- ── PL/SQL PROCEDURE ────────────────────────────────────────

CREATE OR REPLACE PROCEDURE add_timetable_entry(
    p_class_id   IN NUMBER,
    p_subject_id IN NUMBER,
    p_faculty_id IN NUMBER,
    p_room_id    IN NUMBER,
    p_slot_id    IN NUMBER
) AS
    v_count NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_count FROM timetable
    WHERE faculty_id = p_faculty_id AND slot_id = p_slot_id;
    IF v_count > 0 THEN
        RAISE_APPLICATION_ERROR(-20001, 'FACULTY_CONFLICT');
    END IF;

    SELECT COUNT(*) INTO v_count FROM timetable
    WHERE room_id = p_room_id AND slot_id = p_slot_id;
    IF v_count > 0 THEN
        RAISE_APPLICATION_ERROR(-20002, 'ROOM_CONFLICT');
    END IF;

    SELECT COUNT(*) INTO v_count FROM timetable
    WHERE class_id = p_class_id AND slot_id = p_slot_id;
    IF v_count > 0 THEN
        RAISE_APPLICATION_ERROR(-20003, 'CLASS_CONFLICT');
    END IF;

    INSERT INTO timetable(timetable_id,class_id,subject_id,faculty_id,room_id,slot_id)
    VALUES(timetable_seq.NEXTVAL, p_class_id, p_subject_id, p_faculty_id, p_room_id, p_slot_id);
    COMMIT;
END add_timetable_entry;
/

-- ── PL/SQL FUNCTION ─────────────────────────────────────────

CREATE OR REPLACE FUNCTION get_faculty_hours(p_faculty_id IN NUMBER)
RETURN NUMBER AS
    v_hours NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_hours FROM timetable
    WHERE faculty_id = p_faculty_id;
    RETURN v_hours;
END get_faculty_hours;
/

-- ── TRIGGER ─────────────────────────────────────────────────

CREATE OR REPLACE TRIGGER trg_timetable_audit
AFTER INSERT ON timetable
FOR EACH ROW
BEGIN
    INSERT INTO timetable_audit(audit_id, action, faculty_id, slot_id)
    VALUES(audit_seq.NEXTVAL, 'INSERT', :NEW.faculty_id, :NEW.slot_id);
END;
/

COMMIT;

SELECT 'DATABASE SETUP COMPLETE' AS status FROM dual;
