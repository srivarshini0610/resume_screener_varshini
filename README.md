# Smart Resume Screener

An AI-powered resume screening, structured information extraction, and candidate ranking platform built with **FastAPI**, **MySQL 8+**, **SQLAlchemy ORM**, **PyMuPDF**, **Google Gemini LLM**, and a modern **Dark-Mode Single-Page Application (SPA)**.

---

## 1. Project Overview

Smart Resume Screener is designed to automate and standardize technical recruitment workflows. Traditional keyword-based applicant tracking systems (ATS) often suffer from high false-positive/false-negative rates, lack semantic understanding, fail on compound requirements, and cannot handle multi-format documents cleanly.

This platform provides:
- **Document Text Extraction**: PyMuPDF-powered document ingestion extracting text from supported `.pdf` and `.txt` resumes and job descriptions.
- **Strictly Schema-Constrained Information Extraction**: Structured candidate and job specification parsing into strongly typed Pydantic models.
- **Role-Targeted Candidate Association**: Explicit mapping of candidates to specific job openings, isolating candidate pools across different positions.
- **Deterministic Semantic Matching**: LLM-driven candidate-to-job matching combined with deterministic post-processing algorithms to eliminate hallucinations, enforce mutual exclusivity between matching and missing skills, and resolve compound requirements.
- **Evaluation Caching & Duplicate Prevention**: Database-level persistence ensuring repeat screenings for the same candidate against the same job reuse existing evaluations and avoid redundant LLM API calls.
- **Dynamic Ranked Leaderboards**: Real-time candidate ranking, score breakdowns (1.0–10.0 scale), status categorization (`SHORTLISTED`, `REVIEW`, `REJECTED`), and deep-dive evaluation modals.

---

## 2. Key Features

- **Document Parsing**: Ingests multi-page resumes and job descriptions in `.pdf` and `.txt` formats with structural text preservation.
- **Structured Profile Normalization**: Extracts candidate contact details, technical skills, categorized work experience/projects, and multi-tier education (degree, institution, GPA/grade, graduation years).
- **Permanent Sequential UI Job Numbering**: Assigns permanent sequential identifiers (`Job 1`, `Job 2`, `Job 4`) that preserve sequence gaps when jobs are deleted, completely decoupled from internal database primary keys.
- **Clean Display Indexing**: Zero `#` symbols across the entire user interface, utilizing clean descriptors (`Job 1`, `Candidate 1`, `Rank 1`).
- **Compound Skill Matching**: Decomposes complex multi-part requirements (e.g., *"Generative AI (LangChain, LangGraph)"*) into individual components for accurate credit assignment.
- **Deterministic Skill Reconciliation**: Enforces mathematical mutual exclusivity between `matching_skills` and `missing_skills`.
- **False-Positive Token Guards**: Strict word-boundary protections preventing false overlaps (e.g., Java vs. JavaScript, SQL vs. MySQL/PostgreSQL, C vs. C++/C#).
- **Idempotent Database Migrations**: Self-healing SQLAlchemy startup routines that automatically create missing tables, add columns, and seed sequences without requiring manual migration scripts.

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   Frontend UI Layer (Modern Vanilla SPA)                 │
│         ├── Role Management & Job Uploader (PDF / TXT / Manual)          │
│         ├── Candidate Resume Ingestion (Auto-linked to Active Job)       │
│         ├── Candidate Grouped Overview & Selective Checkbox Pool         │
│         └── Ranked Evaluation Leaderboard & Deep-Dive Modals             │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │ REST HTTP / JSON
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                           FastAPI Backend                                │
│  ├── Routers: /api/jobs | /api/candidates | /api/screening               │
│  ├── Document Engine: PyMuPDF (fitz) Text Extraction                     │
│  ├── Validation Layer: Pydantic v2 DTOs & Schema Serializers             │
│  └── Middleware: CORS, Exception Handlers, Static File Servicing         │
└───────────────────┬───────────────────────────────────┬──────────────────┘
                    │                                   │
                    ▼                                   ▼
┌──────────────────────────────────────┐  ┌────────────────────────────────┐
│          AI & LLM Services           │  │       MySQL 8+ Database        │
│  ├── Google Gemini Flash Provider    │  │  ├── job_descriptions          │
│  ├── Structured JSON Schema Mode     │  │  ├── job_counters              │
│  ├── 1-Retry Fallback Engine         │  │  ├── candidates                │
│  ├── Compound Skill Decomposer       │  │  ├── candidate_jobs            │
│  └── Deterministic Reconciler        │  │  └── evaluations (Cache)       │
└──────────────────────────────────────┘  └────────────────────────────────┘
```

---

## 4. Complete Data Flow

The lifecycle of an application from raw PDF ingestion to final leaderboard ranking follows this deterministic pipeline:

```
[Resume PDF Document]
         │
         ▼
 1. PyMuPDF Ingestion ───────────► Raw Plain Text Extracted
         │
         ▼
 2. Gemini Extraction ───────────► Structured JSON (Skills, Experience, Education)
         │
         ▼
 3. Pydantic Sanitizer ──────────► CandidateProfile Schema Validated
         │
         ▼
 4. MySQL Persistence ───────────► Saved to `candidates` & Linked via `candidate_jobs`
         │
         ▼
 5. Target Job Selection ────────► Candidate Profile + Job Requirements Paired
         │
         ▼
 6. Screening Engine Cache Check ──► [Evaluation exists?] ──YES──► Return Cached Record
         │ (NO)                                                          │
         ▼                                                               │
 7. Gemini Matching Evaluation ──► Match Score, Justification, Skill Gap         │
         │                                                               │
         ▼                                                               │
 8. Deterministic Reconciliation─► Mutual Exclusivity, Token Guards, Sanitization│
         │                                                               │
         ▼                                                               │
 9. MySQL Evaluation Cache ──────► Persisted to `evaluations` Table              │
         │                                                               │
         └───────────────────────────────┬───────────────────────────────┘
                                         ▼
10. Dynamic Leaderboard ─────────► Sorted Descending by Score (Rank 1, Rank 2, ...)
```

---

## 5. Backend Architecture

The backend is structured modularly under [`backend/app/`](backend/app):

- **`config.py`**: Centralized configuration management using `pydantic-settings`. Loads environment variables from `.env` with strict type enforcement.
- **`database.py`**: SQLAlchemy engine configuration, connection pooling (`pool_pre_ping=True`, `pool_recycle=3600`), and automatic idempotent table creation/migration via `create_tables()`.
- **`models/`**: SQLAlchemy declarative ORM models defining table schemas, unique constraints, and foreign key relationships with cascading deletes.
- **`routers/`**:
  - `jobs.py`: CRUD endpoints for job descriptions, file upload handling, and permanent sequential UI job numbering.
  - `candidates.py`: Multi-format resume uploads, candidate listings, role-specific queries, and grouped-by-job views.
  - `applications.py`: Explicit candidate-to-job linking endpoints.
  - `screening.py`: Batch screening execution and ranked leaderboard retrieval.
- **`schemas/`**: Pydantic models validating incoming requests and standardizing outbound API responses.
- **`services/`**:
  - `pdf_parser.py`: PyMuPDF document parsing engine.
  - `llm_service.py`: Google Gemini API client, prompts, JSON extractors, compound skill analyzers, and deterministic reconciliation routines.
  - `screening_engine.py`: Screening orchestration, database evaluation caching, and cache-bypass detection.

---

## 6. Database Design

The relational database is implemented in **MySQL 8.0+** using the `InnoDB` engine with `utf8mb4` encoding:

```
┌──────────────────────────┐             ┌──────────────────────────┐
│     job_descriptions     │ 1         * │      candidate_jobs      │
│──────────────────────────│─────────────│──────────────────────────│
│ id (PK, INT AUTO_INC)    │             │ id (PK, INT AUTO_INC)    │
│ job_number (INT, UNIQUE) │             │ job_id (FK -> jobs.id)   │
│ title (VARCHAR)          │             │ candidate_id (FK -> cand)│
│ description_text (LONG)  │             │ created_at (DATETIME)    │
│ required_skills (JSON)   │             └─────────────┬────────────┘
│ min_experience (VARCHAR) │                           │
│ created_at (DATETIME)    │                           │
└────────────┬─────────────┘                           │
             │ 1                                       │ *
             │                               ┌─────────┴────────────────┐
             │ *                             │        candidates        │
┌────────────┴─────────────┐                 │──────────────────────────│
│       evaluations        │ *             1 │ id (PK, INT AUTO_INC)    │
│──────────────────────────│─────────────────│ full_name (VARCHAR)      │
│ id (PK, INT AUTO_INC)    │                 │ email (VARCHAR)          │
│ candidate_id (FK -> cand)│                 │ phone (VARCHAR)          │
│ job_id (FK -> jobs.id)   │                 │ raw_text (LONGTEXT)      │
│ match_score (DECIMAL)    │                 │ skills (JSON)            │
│ justification (TEXT)     │                 │ experience (JSON)        │
│ matching_skills (JSON)   │                 │ education (JSON)         │
│ missing_skills (JSON)    │                 │ file_path (VARCHAR)      │
│ strengths (JSON)         │                 │ created_at (DATETIME)    │
│ weaknesses (JSON)        │                 └──────────────────────────┘
│ status (ENUM)            │
│ evaluated_at (DATETIME)  │
└──────────────────────────┘
```

### Table Specifications:
1. **`job_descriptions`**: Stores job roles with required technical skills, minimum experience, and permanent sequential `job_number`.
2. **`job_counters`**: Single-row tracking table (`id=1, last_job_number=N`) ensuring sequential UI numbers are never reused even if jobs are deleted.
3. **`candidates`**: Stores extracted candidate profiles, parsed contact info, raw resume text, and structured JSON arrays for skills, experience, and education.
4. **`candidate_jobs`**: Junction table establishing role-targeted applications with a unique constraint `uq_candidate_job (candidate_id, job_id)` and cascade deletion.
5. **`evaluations`**: Evaluation cache storing match scores, structured skill breakdowns, justifications, strengths, weaknesses, and recommendation statuses.

---

## 7. Resume Extraction Pipeline

1. **Document Upload**: Multi-part upload receives `.pdf` or `.txt` file.
2. **PyMuPDF Ingestion**: `extract_text_from_file()` extracts raw text content while filtering empty byte payloads.
3. **LLM Extraction**: Google Gemini processes raw text under `RESUME_EXTRACTION_SYSTEM_PROMPT` using JSON Schema Mode.
4. **Schema Label Scrubbing**: Post-processor filters out schema property names (`degree`, `institution`, `technologies`) if mistakenly returned as content.
5. **Experience & Education Structuring**:
   - Classifies experience items into `job`, `internship`, or `project`.
   - Normalizes education into `degree`, `field`, `institution`, `duration`, and `grade`.
6. **Persistence**: Record inserted into `candidates` table and associated with the active `job_id` via `candidate_jobs`.

---

## 8. Job Description Extraction Pipeline

1. **Upload or Text Submission**: Accepts uploaded JD document or manual form inputs.
2. **Text Normalization**: Parses plain text or PyMuPDF extracted document stream.
3. **AI Requirements Analysis**: LLM extracts structured title, mandatory technical skills list, minimum required experience, and comprehensive role description.
4. **Permanent Sequence Assignment**: `get_next_job_number()` increments `job_counters.last_job_number` and assigns the permanent `job_number`.
5. **Database Storage**: Saved to `job_descriptions` table.

---

## 9. Candidate-JD Association

- **Role Targeting**: When a candidate resume is uploaded, it is bound to the currently selected active job role in the frontend.
- **Role Isolation**: Candidates uploaded for *Job 1* will not appear in the candidate selection list or leaderboard for *Job 2*.
- **Grouped Hierarchical View**: `/api/candidates/grouped-by-job` queries all jobs and their respective candidate pools, displaying complete organizational status across all openings.

---

## 10. Candidate Screening Pipeline

1. **Trigger**: User selects one, multiple, or all candidates under an active job and clicks **"Screen Candidates"**.
2. **Batch Isolation**: Backend filters the target candidate list to ensure only candidates assigned to the specified `job_id` are evaluated.
3. **Cache-First Evaluation**:
   - Queries `evaluations` table for existing `(candidate_id, job_id)` pair.
   - If evaluation exists, it is loaded directly from MySQL (0 LLM API calls).
   - If evaluation is missing, the candidate profile and job requirements are sent to Google Gemini.
4. **Deterministic Skills Reconciliation**: Raw LLM output is processed through compound skill decomposition and token guards.
5. **Atomic Persistence**: New evaluations are stored in `evaluations` and returned in the batch response.

---

## 11. LLM Architecture

- **Provider**: Google Gemini API via official `google-genai` SDK.
- **Model**: `gemini-3.5-flash` (Configurable via `GEMINI_MODEL` in `.env`).
- **Generation Settings**: Low temperature (`0.1`) to prioritize deterministic extraction, factual adherence, and strict schema compliance.
- **Structured Schema Mode**: Uses Pydantic schemas (`response_schema=CandidateProfile`, `response_schema=JobDescriptionExtract`, `response_schema=EvaluationResult`) with `response_mime_type="application/json"`.

---

## 12. Resume Extraction Prompt

### Objective
Parse unstructured resume text into a structured, typed JSON schema containing candidate contact details, skills, work experience, projects, and education history.

### System Prompt (`RESUME_EXTRACTION_SYSTEM_PROMPT`)
```text
You are an expert Resume Information Extractor.
Your task is to parse the provided resume text and extract structured candidate information into a strict JSON format.

CRITICAL SCHEMA LABEL INSTRUCTION:
The JSON property names ('type', 'title', 'company_or_organization', 'duration', 'description', 'technologies', 'degree', 'field', 'institution', 'grade') are schema keys only.
They are NOT resume content.
NEVER return schema field names as array elements or values.
FORBIDDEN schema-label values: project_name, technologies, degree, field, institution, cgpa, percentage, expected_graduation_year, company, company_or_organization, duration, description, title, type, grade.

CRITICAL EXPERIENCE RULES:
1. Only include actual work experience, internship, employment, or clearly identified project experience.
2. Each experience or project must be a structured JSON object inside the "experience" array.
3. For projects:
   {
     "type": "project",
     "title": "Plant Disease Detection & RAG Chatbot System",
     "company_or_organization": "",
     "duration": "",
     "description": "Plant disease classification and RAG chatbot",
     "technologies": ["Python", "TensorFlow/Keras", "LangChain", "FAISS", "Google Gemini", "NLP"]
   }
4. For employment / internships:
   {
     "type": "internship" or "job",
     "title": "Software Development Intern",
     "company_or_organization": "ABC Technologies",
     "duration": "6 months",
     "description": "Built REST APIs and database pipelines",
     "technologies": ["Python", "SQL"]
   }
5. NEVER create an experience item from a person's job title alone (e.g. NEVER return {"title": "Engineer"} with no details).
6. NEVER return isolated words ("Engineer", "Developer", "Student", "Fresher") as experience.
7. Do NOT split a single project into multiple records simply because it has multiple technologies. Keep one structured project object.
8. If no actual work experience or projects exist, return an empty array [].
9. Preserve the candidate's actual wording where possible.

CRITICAL EDUCATION RULES:
1. Education must be represented as structured JSON objects inside the "education" array.
2. Each object contains:
   - "degree": Degree, Certificate, or Level (e.g., "B.Tech", "XII", "X", "B.S.", "M.S.")
   - "field": Field of study, major, or stream (e.g., "Computer Science & Engineering (AI & ML)")
   - "institution": School, College, or University name (e.g., "VIT-AP University", "Tirumala Junior College, AP")
   - "duration": Years attended or graduation year (e.g., "2023-2027", "2022")
   - "grade": CGPA, percentage, or score if stated (e.g., "8.97/10", "93.8%", "10/10")
3. Create separate structured records for each distinct level of education (e.g. B.Tech, Class XII, Class X).
4. If a field is not available, set it to "" (empty string). Do NOT invent missing dates or grades.

CRITICAL SKILL RULES:
1. Extract skills explicitly present in the resume.
2. Do NOT invent or hallucinate skills.
3. Do NOT treat every random noun/keyword as a skill.
4. Remove duplicate skills.
5. Preserve distinct technologies and frameworks (e.g. Python, TensorFlow/Keras, LangChain, FAISS, Google Gemini, MySQL, Git).
```

---

## 13. Job Description Extraction Prompt

### Objective
Extract key job metadata, mandatory technical skills, and experience criteria from raw job postings.

### System Prompt (`JOB_EXTRACTION_SYSTEM_PROMPT`)
```text
You are an expert Technical Job Specification Extractor.
Your task is to analyze the provided Job Description text and extract structured requirements into a strict JSON format.

CRITICAL EXTRACTION RULES:
1. Extract ONLY information explicitly supported by the job description text.
2. For "title": Extract the specific job title (e.g. "Senior Python Developer", "Java Backend Developer"). If the title is not clearly available, use "Uploaded Job Description" as a safe fallback.
3. For "required_skills": Extract a clean list of individual mandatory technical and professional skills mentioned in the JD (e.g. ["Python", "FastAPI", "SQL", "Docker"]). Do NOT hallucinate skills.
4. For "min_experience": Extract the minimum required years or level of experience if stated (e.g. "2+ years", "3 years", "Entry level"). If minimum experience is not mentioned in the text, set this to null or "".
5. For "description_text": Return the comprehensive job description text or summary of responsibilities.
```

---

## 14. Candidate Matching Prompt

### Objective
Produce an objective, structured evaluation comparing a candidate profile against target job requirements on a 1.0–10.0 scale.

### System Prompt (`CANDIDATE_MATCHING_SYSTEM_PROMPT`)
```text
You are an expert, objective Technical Recruiter and Resume Screening Engine.
Your task is to compare the candidate information against the job description and produce an objective structured evaluation.

MANDATORY EXECUTION RULES:
1. You MUST perform the evaluation even if the candidate is a poor, zero-experience, or completely irrelevant fit.
2. NEVER refuse the task.
3. NEVER ask questions or offer follow-up assistance.
4. NEVER respond conversationally or with statements like "I cannot evaluate...". An irrelevant candidate is STILL a valid evaluation.

EVALUATION SCORING RUBRIC (1.0 - 10.0 scale):
- 9.0–10.0: Exceptional fit. Candidate satisfies nearly all mandatory requirements and has highly relevant experience. Recommendation: SHORTLISTED.
- 7.5–8.9: Strong fit. Candidate satisfies the core requirements with only minor gaps. Recommendation: SHORTLISTED.
- 5.0–7.4: Potential fit / Review. Candidate has some relevant skills but meaningful gaps remain. Recommendation: REVIEW.
- 1.0–4.9: Poor / Irrelevant fit. Candidate lacks important required skills, experience, or qualifications. Recommendation: REJECTED.

CRITICAL SKILL MATCHING & CONSISTENCY RULES:
1. If the candidate has NO relevant skills or experience:
   - "matching_skills" must be []
   - "missing_skills" must list all required skills from the job description
   - "match_score" should reflect the poor fit (e.g. 1.0 - 4.9)
   - "recommendation" must be "REJECTED"
2. If the candidate has partial relevance, evaluate the partial fit normally.
3. Every skill in "matching_skills" MUST NOT appear in "missing_skills". A skill can NEVER be in both lists simultaneously.
4. If a technology/skill is in "matching_skills", "weaknesses" MUST NEVER claim that the candidate lacks that skill.
5. If a required skill is in "missing_skills", it may be mentioned as a weakness (e.g., "Lacks required experience in Spring Boot").
6. Do NOT claim lack of experience with any technology explicitly demonstrated in the resume.
7. "missing_skills" must represent ONLY mandatory required skills from the Job Description. Preferred skills (like Docker if optional) MUST NOT be placed in "missing_skills".
8. Gaps in preferred/optional skills may be noted under "weaknesses", but clearly identify them as preferred.
9. Perform case-insensitive matching across candidate skills, experience, projects, and resume text. Recognize direct variants (e.g., "Git" = "git" = "Git version control"; "Python" = "Python programming"; "FastAPI" = "Fast API"; "LangChain" = "langchain").
10. COMPOUND SKILL REQUIREMENTS:
    When a JD requirement is compound (e.g., "Generative AI tools and frameworks (including LangChain and LangGraph)" or "Python frameworks such as FastAPI and Flask"):
    - If candidate has the component technologies (e.g. LangChain and LangGraph), add them to "matching_skills".
    - Do NOT report the parent descriptive phrase as missing when the candidate satisfies its explicitly specified components.
    - If only some components are present (e.g. FastAPI present, Flask missing), add FastAPI to matching_skills and Flask to missing_skills.
11. DO NOT conflate distinct technologies (e.g. SQL != MySQL; Java != JavaScript; MySQL != PostgreSQL; React != React Native).
12. The "recommendation" field must be EXACTLY one of: "SHORTLISTED", "REVIEW", "REJECTED".
    - If match_score >= 7.5: recommendation must be "SHORTLISTED"
    - If 5.0 <= match_score < 7.5: recommendation must be "REVIEW"
    - If match_score < 5.0: recommendation must be "REJECTED"
```

---

## 15. JSON Validation & Retry Strategy

To handle LLM formatting anomalies defensively:
1. **Multi-Stage JSON Extraction (`_parse_llm_json_response`)**:
   - Strips markdown code blocks (````json ... ````).
   - Regex-extracts outermost balanced `{ ... }` blocks to discard conversational preambles.
   - Cleans trailing commas before closing brackets.
   - Falls back to `ast.literal_eval` for valid Python dictionaries formatted with single quotes.
2. **Automatic 1-Retry Fallback Engine**:
   - If Attempt 1 returns non-JSON text or fails validation, Attempt 2 immediately triggers with an explicit enforcement prompt:
     ```text
     Your previous response was invalid because it did not contain a JSON evaluation.
     You MUST evaluate the candidate against the job description.
     Even if there is zero compatibility or the candidate is completely irrelevant, you must return a valid evaluation.
     Return ONLY valid raw JSON starting with '{' and ending with '}'.
     ```
3. **Pydantic Validation**:
   - Validates ranges (`match_score: 1.0–10.0`), rounds scores to 1 decimal place, and enforces strict recommendation enum values (`SHORTLISTED`, `REVIEW`, `REJECTED`).

---

## 16. Deterministic Skill Reconciliation

While LLMs provide semantic evaluation, statistical language models can occasionally produce contradictory lists (e.g., listing *FastAPI* under both matching and missing skills).

The platform enforces deterministic post-processing via `reconcile_skills()`:
1. **Strict Mutual Exclusivity**: If a skill exists in `matching_skills`, it is mathematically scrubbed from `missing_skills`.
2. **Weakness Sanitization (`_sanitize_weaknesses`)**: Scans candidate weaknesses using regex patterns (`lack|lacks|no|missing|without`). If a weakness claims the candidate lacks a skill that is verified in `matching_skills`, the statement is automatically purged or rewritten.
3. **Justification Alignment (`_sanitize_justification`)**: Ensures justification narrative text does not contradict the finalized skill lists.

---

## 17. Compound Skill Matching

Job specifications often group skills into parenthetical or conjunction phrases (e.g., *"Generative AI tools (LangChain, LangGraph)"*, *"Web Frameworks such as FastAPI, Flask"*).

The algorithm (`_decompose_compound_requirement`):
1. Detects pattern indicators (`( ... )`, `such as`, `including`, `like`, `/`).
2. Extracts constituent sub-technologies.
3. Matches candidate skills against each component individually.
4. **Scoring Logic**:
   - **Full Match**: If candidate has all components, components are added to `matching_skills`; parent phrase is omitted from `missing_skills`.
   - **Partial Match**: Matched components go to `matching_skills`, missing components go to `missing_skills`.
   - **Zero Match**: Entire requirement is placed in `missing_skills`.

---

## 18. False-Positive Protections

The matching engine enforces strict word-boundary regular expressions and token isolation:
- **Java vs. JavaScript**: Protected via negative lookahead `r"\bjava\b(?!script)"`. A candidate with JavaScript will never match a Java requirement.
- **SQL vs. Dialects**: Protected via negative lookbehind `r"(?<!my)(?<!postgre)(?<!no)(?<!pl/)\bsql\b(?!ite)"`. Ensures generic SQL requirements are evaluated accurately against dialect-specific claims.
- **C vs. C++ / C#**: Protected via negative lookahead `r"\bc\b(?![+#])"`.
- **Canonical Aliases**: Standardizes equivalent industry nomenclature (`git` = `github` = `gitlab`; `k8s` = `kubernetes`; `fastapi` = `fast api`; `aws` = `amazon web services`).

---

## 19. Screening Cache & Duplicate Prevention

To avoid unnecessary LLM calls and improve response times:
- When a screening request is received for `(candidate_id, job_id)`, the backend checks the `evaluations` table.
- If a record exists, the LLM invocation is bypassed and the previously computed evaluation is returned directly from the database.
- Repeated screening runs for the same candidate against the same job role reuse existing records without initiating new LLM requests.

---

## 20. Ranked Leaderboard Behavior

- **Score-Based Sorting**: Leaderboard entries are sorted in descending order by `match_score`.
- **Status Thresholds**:
  - `SHORTLISTED` (Score >= 7.5): Green badge.
  - `REVIEW` (5.0 <= Score < 7.5): Amber badge.
  - `REJECTED` (Score < 5.0): Rose badge.
- **UI Distinctions**:
  - **`Job Number` vs `Database ID`**: UI displays permanent sequential numbers (`Job 1`, `Job 2`), while database primary keys remain internal.
  - **`Candidate Number` vs `Leaderboard Rank`**: `Candidate 1` denotes the applicant's permanent pool index, whereas `Rank 1` denotes their performance position on that specific role's leaderboard.

---

## 21. API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/jobs/upload` | Ingests a PDF/TXT JD; extracts requirements via Gemini and assigns a sequential `job_number`. |
| `POST` | `/api/jobs/` | Manually creates a Job Description. |
| `GET` | `/api/jobs/` | Lists all stored Job Descriptions sorted by creation date. |
| `GET` | `/api/jobs/{job_id}` | Retrieves details of a specific Job Description by ID. |
| `DELETE` | `/api/jobs/{job_id}` | Cascades deletion of a Job Description, its candidate links, and evaluations. |
| `POST` | `/api/candidates/upload` | Ingests a PDF/TXT resume; parses profile and auto-links to target `job_id`. |
| `GET` | `/api/candidates/` | Lists all registered candidates. |
| `GET` | `/api/candidates/job/{job_id}` | Lists candidates associated with a specific job ID. |
| `GET` | `/api/candidates/grouped-by-job` | Retrieves all candidates grouped hierarchically by their assigned job roles. |
| `POST` | `/api/screening/evaluate` | Evaluates selected candidates against a job (uses cache to skip existing evaluations). |
| `GET` | `/api/screening/results/{job_id}` | Retrieves ranked screening results and leaderboard for a job. |

---

## 22. Testing

The project includes an automated test suite located in [`backend/tests/`](backend/tests) covering all functional areas:

```bash
# Run all tests from project root
pytest backend/tests

# Or run from backend directory
cd backend
python -m pytest tests
```

### Test Suite Modules:
- `test_database.py`: MySQL connection, table schemas, and foreign-key cascade deletions.
- `test_document_parser.py`: PyMuPDF PDF and TXT text extraction and error validation.
- `test_file_uploads.py`: Multipart resume & JD uploads and Pydantic validation.
- `test_job_management.py`: Job CRUD, permanent sequential numbering, and deletion gap preservation.
- `test_candidate_workflow.py`: Candidate pool indexing, multi-job mapping, and role isolation.
- `test_skill_matching.py`: Compound skill decomposition and deterministic reconciliation.
- `test_screening_and_cache.py`: Evaluation caching, skip-logic on duplicates, and leaderboard ranking.
- `test_llm_service.py`: Gemini provider initialization, structured extraction, JSON sanitization, and 1-retry fallback.

---

## 23. Installation and Setup

### Prerequisites
- Python 3.11+
- MySQL Server 8.0+
- Google Gemini API Key ([Google AI Studio](https://aistudio.google.com/))

### 1. Clone & Environment Setup
```bash
# Create conda environment
conda create -n resume-screener python=3.11 -y
conda activate resume-screener

# Install dependencies
cd backend
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy `.env.example` to `.env` in the project root:
```bash
cp .env.example .env
```
Configure your credentials in `.env`:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=resume_screener_db

GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash
```

### 3. Database Initialization
Create the MySQL database:
```sql
CREATE DATABASE IF NOT EXISTS resume_screener_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
*(Tables and sequences are created automatically on FastAPI startup).*

### 4. Start Backend Server
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
- API URL: `http://127.0.0.1:8000`
- Swagger UI Docs: `http://127.0.0.1:8000/docs`

### 5. Start Frontend Dashboard
```bash
cd frontend
python -m http.server 3000
```
Open `http://localhost:3000` in your web browser.

---

## 24. Example Structured Outputs

### Candidate Profile JSON (`CandidateProfile`)
```json
{
  "full_name": "Alex Johnson",
  "email": "alex@example.com",
  "phone": "+91-9876543210",
  "skills": [
    "Python",
    "FastAPI",
    "MySQL",
    "Docker",
    "LangChain",
    "FAISS",
    "Git"
  ],
  "experience": [
    {
      "type": "project",
      "title": "Plant Disease Detection & RAG Chatbot",
      "company_or_organization": "",
      "duration": "2024",
      "description": "RAG Chatbot built with LangChain, FAISS, and Gemini.",
      "technologies": ["Python", "LangChain", "FAISS", "Gemini"]
    }
  ],
  "education": [
    {
      "degree": "B.Tech",
      "field": "Computer Science & Engineering",
      "institution": "VIT-AP University",
      "duration": "2020-2024",
      "grade": "8.97 CGPA"
    }
  ]
}
```

### Candidate Evaluation JSON (`EvaluationResult`)
```json
{
  "match_score": 9.2,
  "justification": "The candidate demonstrates strong alignment with backend engineering requirements, possessing production experience with Python, FastAPI, and MySQL alongside modern LLM toolchains.",
  "matching_skills": [
    "Python",
    "FastAPI",
    "MySQL",
    "Docker",
    "Git"
  ],
  "missing_skills": [
    "Kubernetes"
  ],
  "strengths": [
    "Extensive FastAPI and relational database experience",
    "Practical implementation of RAG pipelines and vector search"
  ],
  "weaknesses": [
    "Lacks documented experience with Kubernetes container orchestration"
  ],
  "recommendation": "SHORTLISTED"
}
```

---

## 25. Limitations and Future Improvements

- **OCR for Image-Based Resumes**: Current document extraction relies on PyMuPDF text stream parsing; integrating Tesseract OCR or multimodal Gemini vision inputs would enable extraction from scanned image resumes.
- **Async Task Queues**: For high-volume batch processing, decoupling LLM calls into asynchronous distributed worker queues (e.g., Celery/Redis) would enhance background throughput.
- **Weights-Adjustable Scoring**: Allowing recruiters to customize relative scoring weights (e.g., skills, experience duration, education) via the UI.
- **Custom Feedback Export**: Exporting evaluation summaries, candidate scorecards, and ranking spreadsheets directly to PDF/CSV.


