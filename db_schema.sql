-- db_schema.sql
-- Creates one PostgreSQL database with three logical table groups:
--   1) open-ended tables
--   2) mcq tables
--   3) final summary/leaderboard tables

-- NOTE: Run this in psql as a user with CREATE DATABASE rights.

CREATE DATABASE interview_coach;

\connect interview_coach
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Open-ended tables
CREATE TABLE IF NOT EXISTS oe_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_name VARCHAR(200) NOT NULL,
    student_email VARCHAR(200) NOT NULL,
    skills_tested TEXT[],
    mode VARCHAR(20) NOT NULL DEFAULT 'open_ended',
    total_questions INT DEFAULT 0,
    total_answered INT DEFAULT 0,
    total_score FLOAT,
    overall_label VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active','completed','abandoned')),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS oe_session_questions (
    session_question_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    skill VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    question_text TEXT NOT NULL,
    difficulty VARCHAR(20),
    b_param FLOAT,
    type VARCHAR(50),
    model_answer TEXT,
    hints TEXT[],
    source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oe_session_questions_session ON oe_session_questions(session_id);
CREATE INDEX IF NOT EXISTS idx_oe_session_questions_skill ON oe_session_questions(skill);

CREATE TABLE IF NOT EXISTS oe_responses (
    response_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    session_question_id UUID NOT NULL,
    skill VARCHAR(100) NOT NULL,
    answer_text TEXT NOT NULL,
    confidence INT CHECK (confidence BETWEEN 1 AND 5),
    score FLOAT,
    feedback TEXT,
    evaluator_model VARCHAR(100),
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oe_responses_session ON oe_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_oe_responses_question ON oe_responses(session_question_id);

-- MCQ tables
CREATE TABLE IF NOT EXISTS mcq_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_name VARCHAR(200) NOT NULL,
    student_email VARCHAR(200) NOT NULL,
    skills_tested TEXT[],
    mode VARCHAR(20) NOT NULL DEFAULT 'mcq',
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active','completed','abandoned')),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    total_answered INT DEFAULT 0,
    total_correct INT DEFAULT 0,
    theta_overall FLOAT,
    proficiency_score FLOAT,
    proficiency_label VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS mcq_questions (
    question_id VARCHAR(50) PRIMARY KEY,
    skill VARCHAR(100) NOT NULL,
    category VARCHAR(100),
    question_text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct_option CHAR(1) NOT NULL CHECK (correct_option IN ('a','b','c','d')),
    explanation TEXT,
    b_param FLOAT NOT NULL CHECK (b_param BETWEEN -2.0 AND 2.0),
    difficulty_tier VARCHAR(10) GENERATED ALWAYS AS (
        CASE
            WHEN b_param < -0.5 THEN 'easy'
            WHEN b_param > 0.5 THEN 'hard'
            ELSE 'medium'
        END
    ) STORED,
    response_count INT DEFAULT 0,
    correct_count INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcq_questions_skill ON mcq_questions(skill);
CREATE INDEX IF NOT EXISTS idx_mcq_questions_b_param ON mcq_questions(b_param);

CREATE TABLE IF NOT EXISTS mcq_responses (
    response_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    question_id VARCHAR(50) NOT NULL,
    skill VARCHAR(100) NOT NULL,
    selected_option CHAR(1),
    is_correct BOOLEAN NOT NULL,
    b_used FLOAT NOT NULL,
    theta_before FLOAT NOT NULL,
    theta_after FLOAT NOT NULL,
    p_correct_irt FLOAT NOT NULL,
    surprise FLOAT NOT NULL,
    proficiency_before FLOAT,
    proficiency_after FLOAT,
    answered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mcq_responses_session ON mcq_responses(session_id);
CREATE INDEX IF NOT EXISTS idx_mcq_responses_skill ON mcq_responses(skill);
CREATE INDEX IF NOT EXISTS idx_mcq_responses_question ON mcq_responses(question_id);

CREATE TABLE IF NOT EXISTS mcq_skill_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    student_name VARCHAR(200) NOT NULL,
    student_email VARCHAR(200) NOT NULL,
    skill VARCHAR(100) NOT NULL,
    theta_final FLOAT NOT NULL,
    proficiency_score FLOAT NOT NULL,
    proficiency_label VARCHAR(50) NOT NULL,
    questions_answered INT DEFAULT 0,
    questions_correct INT DEFAULT 0,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (session_id, skill)
);

CREATE INDEX IF NOT EXISTS idx_mcq_skill_profiles_skill ON mcq_skill_profiles(skill);
CREATE INDEX IF NOT EXISTS idx_mcq_skill_profiles_theta ON mcq_skill_profiles(theta_final DESC);

-- Final / summary tables
CREATE TABLE IF NOT EXISTS final_sessions (
    final_session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_name VARCHAR(200) NOT NULL,
    student_email VARCHAR(200) NOT NULL,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('mcq','open_ended','combined')),
    oe_session_id UUID,
    mcq_session_id UUID,
    total_questions INT DEFAULT 0,
    total_answered INT DEFAULT 0,
    total_correct INT DEFAULT 0,
    final_score FLOAT,
    overall_label VARCHAR(50),
    proficiency_score FLOAT,
    proficiency_label VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active','completed','abandoned')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_final_sessions_oe_session ON final_sessions(oe_session_id);
CREATE INDEX IF NOT EXISTS idx_final_sessions_mcq_session ON final_sessions(mcq_session_id);
