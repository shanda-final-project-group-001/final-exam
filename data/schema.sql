-- 志愿星演示数据库（全部为虚构数据）
-- 说明：剩余名额不落库，由 capacity 减去 confirmed 报名数实时计算，避免数据漂移。

DROP TABLE IF EXISTS hours;
DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS activities;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    student_id      TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    grade           TEXT NOT NULL,
    major           TEXT NOT NULL,
    interests       TEXT NOT NULL,   -- 逗号分隔
    available_slots TEXT NOT NULL    -- 逗号分隔
);

CREATE TABLE courses (
    course_id  TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    name       TEXT NOT NULL,
    weekday    TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time   TEXT NOT NULL,
    weeks      TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE TABLE activities (
    activity_id  TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    category     TEXT NOT NULL,
    date         TEXT NOT NULL,
    weekday      TEXT NOT NULL,
    start_time   TEXT NOT NULL,
    end_time     TEXT NOT NULL,
    location     TEXT NOT NULL,
    capacity     INTEGER NOT NULL,
    credit_hours REAL NOT NULL,
    tags         TEXT NOT NULL,
    description  TEXT NOT NULL,
    organizer    TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'open'   -- open / closed
);

CREATE TABLE enrollments (
    enrollment_id TEXT PRIMARY KEY,
    student_id    TEXT NOT NULL,
    activity_id   TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'confirmed',  -- confirmed / cancelled
    created_at    TEXT NOT NULL,
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (activity_id) REFERENCES activities(activity_id)
);

CREATE TABLE hours (
    record_id  TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    activity_id TEXT NOT NULL,
    hours      REAL NOT NULL,
    term       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'confirmed',
    FOREIGN KEY (student_id) REFERENCES students(student_id),
    FOREIGN KEY (activity_id) REFERENCES activities(activity_id)
);

CREATE INDEX idx_activities_date ON activities(date);
CREATE INDEX idx_activities_weekday ON activities(weekday);
CREATE INDEX idx_enrollments_student ON enrollments(student_id);
CREATE INDEX idx_enrollments_activity ON enrollments(activity_id);
CREATE INDEX idx_hours_student_term ON hours(student_id, term);
