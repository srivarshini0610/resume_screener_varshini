-- =============================================================================
-- Database Schema for Smart Resume Screener (MySQL 8+)
-- =============================================================================

CREATE DATABASE IF NOT EXISTS resume_screener_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE resume_screener_db;

-- 1. Job Descriptions Table
CREATE TABLE IF NOT EXISTS job_descriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_number INT NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    description_text LONGTEXT NOT NULL,
    required_skills JSON NULL,
    min_experience VARCHAR(100) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_job_number (job_number),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Job Counters Table (Persistent Sequential UI Numbering Tracker)
CREATE TABLE IF NOT EXISTS job_counters (
    id INT PRIMARY KEY DEFAULT 1,
    last_job_number INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed default JobCounter if not present
INSERT IGNORE INTO job_counters (id, last_job_number) VALUES (1, 0);

-- 3. Candidates Table
CREATE TABLE IF NOT EXISTS candidates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    full_name VARCHAR(255) NULL,
    email VARCHAR(255) NULL,
    phone VARCHAR(50) NULL,
    raw_text LONGTEXT NOT NULL,
    skills JSON NULL,
    experience JSON NULL,
    education JSON NULL,
    file_path VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_cand_email (email),
    INDEX idx_cand_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Candidate-Job Association (CandidateJob / Application Link)
CREATE TABLE IF NOT EXISTS candidate_jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT NOT NULL,
    job_id INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_candidate_job UNIQUE (candidate_id, job_id),
    CONSTRAINT fk_cj_candidate FOREIGN KEY (candidate_id)
        REFERENCES candidates (id) ON DELETE CASCADE,
    CONSTRAINT fk_cj_job FOREIGN KEY (job_id)
        REFERENCES job_descriptions (id) ON DELETE CASCADE,
    INDEX idx_cj_job_id (job_id),
    INDEX idx_cj_candidate_id (candidate_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Evaluations Table (LLM Candidate Match Results & Leaderboard)
CREATE TABLE IF NOT EXISTS evaluations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    candidate_id INT NOT NULL,
    job_id INT NOT NULL,
    match_score DECIMAL(3, 1) NOT NULL,
    justification TEXT NOT NULL,
    matching_skills JSON NULL,
    missing_skills JSON NULL,
    strengths JSON NULL,
    weaknesses JSON NULL,
    status ENUM('SHORTLISTED', 'REVIEW', 'REJECTED') NOT NULL DEFAULT 'REVIEW',
    evaluated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_eval_candidate FOREIGN KEY (candidate_id)
        REFERENCES candidates (id) ON DELETE CASCADE,
    CONSTRAINT fk_eval_job FOREIGN KEY (job_id)
        REFERENCES job_descriptions (id) ON DELETE CASCADE,
    INDEX idx_eval_job_candidate (job_id, candidate_id),
    INDEX idx_eval_match_score (match_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
