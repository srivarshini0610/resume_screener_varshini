import json
import re
import ast
from typing import Dict, Any, List, Union, Tuple, Set
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.config import settings
from app.schemas.candidate_schema import CandidateProfile, CandidateParsedProfile, ExperienceItem, EducationItem
from app.schemas.job_schema import JobDescriptionExtract
from app.schemas.evaluation_schema import EvaluationResult

# ==============================================================================
# SCHEMA LABELS & FILTER CONSTANTS
# ==============================================================================

SCHEMA_LABELS = {
    "project_name",
    "technologies",
    "degree",
    "field",
    "institution",
    "cgpa",
    "percentage",
    "expected_graduation_year",
    "company",
    "company_or_organization",
    "duration",
    "description",
    "title",
    "type",
    "grade",
}

STANDALONE_TITLES = {
    "engineer", "developer", "student", "intern", "fresher",
    "software engineer", "full stack developer", "backend developer",
    "frontend developer", "coder", "programmer", "analyst", "candidate", "n/a", "none"
}

CANONICAL_ALIASES = {
    "git": ["git", "github", "gitlab", "git version control"],
    "fastapi": ["fastapi", "fast api"],
    "spring boot": ["spring boot", "springboot", "spring-boot"],
    "langchain": ["langchain", "lang chain"],
    "langgraph": ["langgraph", "lang graph"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "tensorflow": ["tensorflow", "tensor flow", "tf"],
    "pytorch": ["pytorch", "py torch"],
    "docker": ["docker", "docker container", "docker containers"],
    "kubernetes": ["kubernetes", "k8s"],
    "postgresql": ["postgresql", "postgres", "psql"],
    "mysql": ["mysql"],
    "mongodb": ["mongodb", "mongo db", "mongo"],
    "react": ["react", "reactjs", "react.js"],
    "angular": ["angular", "angularjs"],
    "vue": ["vue", "vuejs", "vue.js"],
    "node.js": ["nodejs", "node.js", "node js"],
    "rest apis": ["rest api", "rest apis", "restful api", "restful apis", "rest"],
    "graphql": ["graphql", "graph ql"],
    "aws": ["aws", "amazon web services"],
    "azure": ["azure", "microsoft azure"],
    "gcp": ["gcp", "google cloud", "google cloud platform"],
}

# ==============================================================================
# PROMPT DEFINITIONS
# ==============================================================================

# 1. Resume Information Extraction System Prompt
RESUME_EXTRACTION_SYSTEM_PROMPT = """You are an expert Resume Information Extractor.
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
"""

# 2. Job Description Information Extraction System Prompt
JOB_EXTRACTION_SYSTEM_PROMPT = """You are an expert Technical Job Specification Extractor.
Your task is to analyze the provided Job Description text and extract structured requirements into a strict JSON format.

CRITICAL EXTRACTION RULES:
1. Extract ONLY information explicitly supported by the job description text.
2. For "title": Extract the specific job title (e.g. "Senior Python Developer", "Java Backend Developer"). If the title is not clearly available, use "Uploaded Job Description" as a safe fallback.
3. For "required_skills": Extract a clean list of individual mandatory technical and professional skills mentioned in the JD (e.g. ["Python", "FastAPI", "SQL", "Docker"]). Do NOT hallucinate skills.
4. For "min_experience": Extract the minimum required years or level of experience if stated (e.g. "2+ years", "3 years", "Entry level"). If minimum experience is not mentioned in the text, set this to null or "".
5. For "description_text": Return the comprehensive job description text or summary of responsibilities.
"""

# 3. Candidate Resume-to-Job Matching System Prompt
CANDIDATE_MATCHING_SYSTEM_PROMPT = """You are an expert, objective Technical Recruiter and Resume Screening Engine.
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
"""

# ==============================================================================
# GEMINI CLIENT & ERROR HANDLING HELPERS
# ==============================================================================

def _get_gemini_client() -> genai.Client:
    """Initializes and returns the Google GenAI client using GEMINI_API_KEY."""
    api_key = settings.GEMINI_API_KEY
    if not api_key or not api_key.strip():
        raise ValueError("AI service configuration is invalid. Please check GEMINI_API_KEY in your .env file.")
    return genai.Client(api_key=api_key.strip())


def _format_gemini_error(e: Exception) -> ValueError:
    """Translates API exceptions into safe, user-friendly messages without leaking keys or internals."""
    err_str = str(e).lower()
    if "404" in err_str or "not_found" in err_str or "not found" in err_str or "no longer available" in err_str:
        return ValueError("The configured Gemini model is unavailable for this API key. Please update GEMINI_MODEL.")
    elif "api_key" in err_str or "api key" in err_str or "unauthenticated" in err_str or "401" in err_str or "403" in err_str:
        return ValueError("AI service configuration is invalid. Please check GEMINI_API_KEY in your .env file.")
    elif "429" in err_str or "quota" in err_str or "rate limit" in err_str or "resource_exhausted" in err_str:
        return ValueError("AI service rate limit exceeded or quota exhausted. Please try again shortly.")
    elif "500" in err_str or "503" in err_str or "unavailable" in err_str or "server" in err_str:
        return ValueError("AI service is temporarily unavailable. Please try again.")
    elif "timeout" in err_str or "timed out" in err_str:
        return ValueError("AI service request timed out. Please try again.")
    elif "connection" in err_str or "network" in err_str:
        return ValueError("Failed to connect to AI service. Please check your network connection.")
    else:
        return ValueError("AI service error occurred during processing. Please try again.")


# ==============================================================================
# POST-PROCESSING & VALIDATION HELPERS
# ==============================================================================

def _clean_and_normalize_skills(raw_skills: Any) -> List[str]:
    """Cleans, strips, and deduplicates extracted skills while filtering out schema labels."""
    if not isinstance(raw_skills, list):
        raw_skills = [str(raw_skills)] if raw_skills else []
    seen = set()
    cleaned = []
    for s in raw_skills:
        if not s or not isinstance(s, (str, int, float)):
            continue
        s_clean = str(s).strip()
        if not s_clean:
            continue
        s_lower = s_clean.lower()
        if s_lower in SCHEMA_LABELS:
            continue
        if s_lower not in seen:
            seen.add(s_lower)
            cleaned.append(s_clean)
    return cleaned


def _clean_and_normalize_experience(raw_exp: Any) -> List[Dict[str, Any]]:
    """
    Cleans and structures experience entries.
    Recovers structured records from flat label-value dumps and filters out isolated generic titles.
    """
    if not raw_exp:
        return []
    if not isinstance(raw_exp, list):
        raw_exp = [raw_exp]

    results: List[Dict[str, Any]] = []

    # Check if raw_exp is a flat list of strings with interleaved schema labels
    is_flat_schema_dump = any(
        isinstance(x, str) and x.strip().lower() in {"project_name", "technologies", "company_or_organization", "duration", "description"}
        for x in raw_exp
    )

    if is_flat_schema_dump:
        curr_item = {
            "type": "project",
            "title": "",
            "company_or_organization": "",
            "duration": "",
            "description": "",
            "technologies": []
        }
        current_mode = None

        for elem in raw_exp:
            if not isinstance(elem, str):
                continue
            text = elem.strip()
            if not text:
                continue
            norm_key = text.lower()

            if norm_key in {"project_name", "project", "title"}:
                if curr_item["title"] and (curr_item["title"].lower() not in SCHEMA_LABELS):
                    results.append(curr_item)
                    curr_item = {"type": "project", "title": "", "company_or_organization": "", "duration": "", "description": "", "technologies": []}
                current_mode = "title"
            elif norm_key in {"company", "company_or_organization", "organization"}:
                current_mode = "company"
            elif norm_key in {"technologies", "tech_stack", "tools"}:
                current_mode = "technologies"
            elif norm_key in {"duration", "dates", "period"}:
                current_mode = "duration"
            elif norm_key in {"description", "summary", "details"}:
                current_mode = "description"
            elif norm_key in {"type", "role"}:
                current_mode = "type"
            else:
                if current_mode == "title":
                    curr_item["title"] = text
                elif current_mode == "company":
                    curr_item["company_or_organization"] = text
                elif current_mode == "duration":
                    curr_item["duration"] = text
                elif current_mode == "description":
                    curr_item["description"] = text
                elif current_mode == "type":
                    curr_item["type"] = text
                elif current_mode == "technologies":
                    if text.lower() not in SCHEMA_LABELS and text not in curr_item["technologies"]:
                        curr_item["technologies"].append(text)
                else:
                    if not curr_item["title"]:
                        curr_item["title"] = text
                    else:
                        if text.lower() not in SCHEMA_LABELS and text not in curr_item["technologies"]:
                            curr_item["technologies"].append(text)

        if curr_item["title"] and (curr_item["title"].lower() not in SCHEMA_LABELS):
            results.append(curr_item)
        return results

    # Normal list of dicts or normal list of string descriptions
    for item in raw_exp:
        if isinstance(item, dict):
            exp_type = str(item.get("type") or "").strip()
            title = str(item.get("title") or item.get("project_name") or item.get("role") or item.get("job_title") or "").strip()
            company = str(item.get("company_or_organization") or item.get("company") or item.get("organization") or "").strip()
            duration = str(item.get("duration") or item.get("dates") or item.get("period") or "").strip()
            description = str(item.get("description") or item.get("summary") or "").strip()

            raw_techs = item.get("technologies") or item.get("tech_stack") or []
            if isinstance(raw_techs, str):
                techs = [t.strip() for t in raw_techs.split(",") if t.strip()]
            elif isinstance(raw_techs, list):
                techs = [str(t).strip() for t in raw_techs if str(t).strip()]
            else:
                techs = []

            # Clean out schema labels
            if exp_type.lower() in SCHEMA_LABELS: exp_type = ""
            if title.lower() in SCHEMA_LABELS: title = ""
            if company.lower() in SCHEMA_LABELS: company = ""
            if duration.lower() in SCHEMA_LABELS: duration = ""
            if description.lower() in SCHEMA_LABELS: description = ""
            techs = [t for t in techs if t.lower() not in SCHEMA_LABELS]

            # Filter standalone generic titles without context
            if title.lower() in STANDALONE_TITLES and not company and not duration and not description and not techs:
                continue

            if title or company or description or techs:
                results.append({
                    "type": exp_type or ("project" if ("project" in title.lower() or techs) else "job"),
                    "title": title,
                    "company_or_organization": company,
                    "duration": duration,
                    "description": description,
                    "technologies": techs,
                })
        elif isinstance(item, str):
            text = item.strip()
            if not text or text.lower() in SCHEMA_LABELS or text.lower() in STANDALONE_TITLES:
                continue
            results.append({
                "type": "experience",
                "title": text,
                "company_or_organization": "",
                "duration": "",
                "description": text,
                "technologies": [],
            })

    return results


def _clean_and_normalize_education(raw_edu: Any) -> List[Dict[str, Any]]:
    """
    Cleans and structures education entries.
    Recovers structured records from flat label-value dumps and filters out schema labels.
    """
    if not raw_edu:
        return []
    if not isinstance(raw_edu, list):
        raw_edu = [raw_edu]

    results: List[Dict[str, Any]] = []

    # Check if raw_edu is a flat list of strings with interleaved schema labels
    is_flat_schema_dump = any(
        isinstance(x, str) and x.strip().lower() in {"degree", "field", "institution", "cgpa", "percentage", "grade"}
        for x in raw_edu
    )

    if is_flat_schema_dump:
        curr_item = {"degree": "", "field": "", "institution": "", "duration": "", "grade": ""}
        current_mode = None

        for elem in raw_edu:
            if not isinstance(elem, str):
                continue
            text = elem.strip()
            if not text:
                continue
            norm_key = text.lower()

            if norm_key in {"degree", "qualification"}:
                if curr_item["degree"] and (curr_item["degree"].lower() not in SCHEMA_LABELS):
                    results.append(curr_item)
                    curr_item = {"degree": "", "field": "", "institution": "", "duration": "", "grade": ""}
                current_mode = "degree"
            elif norm_key in {"field", "branch", "stream", "specialization"}:
                current_mode = "field"
            elif norm_key in {"institution", "university", "college", "school"}:
                current_mode = "institution"
            elif norm_key in {"duration", "years", "graduation_year", "expected_graduation_year"}:
                current_mode = "duration"
            elif norm_key in {"grade", "cgpa", "percentage", "gpa", "score"}:
                current_mode = "grade"
            else:
                if current_mode == "degree":
                    curr_item["degree"] = text
                elif current_mode == "field":
                    curr_item["field"] = text
                elif current_mode == "institution":
                    curr_item["institution"] = text
                elif current_mode == "duration":
                    curr_item["duration"] = text
                elif current_mode == "grade":
                    curr_item["grade"] = text
                else:
                    if not curr_item["degree"]:
                        curr_item["degree"] = text
                    elif not curr_item["institution"]:
                        curr_item["institution"] = text

        if curr_item["degree"] and (curr_item["degree"].lower() not in SCHEMA_LABELS):
            results.append(curr_item)
        return results

    for item in raw_edu:
        if isinstance(item, dict):
            degree = str(item.get("degree") or item.get("qualification") or "").strip()
            field = str(item.get("field") or item.get("stream") or item.get("branch") or "").strip()
            institution = str(item.get("institution") or item.get("university") or item.get("college") or item.get("school") or "").strip()
            duration = str(item.get("duration") or item.get("years") or item.get("expected_graduation_year") or "").strip()
            grade = str(item.get("grade") or item.get("cgpa") or item.get("percentage") or item.get("gpa") or "").strip()

            if degree.lower() in SCHEMA_LABELS: degree = ""
            if field.lower() in SCHEMA_LABELS: field = ""
            if institution.lower() in SCHEMA_LABELS: institution = ""
            if duration.lower() in SCHEMA_LABELS: duration = ""
            if grade.lower() in SCHEMA_LABELS: grade = ""

            if degree or institution or field:
                results.append({
                    "degree": degree,
                    "field": field,
                    "institution": institution,
                    "duration": duration,
                    "grade": grade,
                })
        elif isinstance(item, str):
            text = item.strip()
            if not text or text.lower() in SCHEMA_LABELS:
                continue
            results.append({
                "degree": text,
                "field": "",
                "institution": "",
                "duration": "",
                "grade": "",
            })

    return results


def _parse_llm_json_response(raw_response: str) -> Dict[str, Any]:
    """
    Robust multi-stage JSON parser for LLM responses.
    Handles:
    - Markdown code fences (closed or unclosed, e.g. ```json ... ```)
    - Surrounding conversational text or introductory remarks
    - Trailing commas in arrays or objects
    - Smart/curly quotes (e.g. “ ”, ’)
    - Single-line or multi-line comments
    - Python single-quoted dictionary syntax fallback
    - Regex key-value extraction fallback
    """
    if not raw_response or not raw_response.strip():
        raise ValueError("LLM returned an empty response.")

    text = raw_response.strip()

    # Step 1: Normalize smart/curly quotes
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")

    # Step 2: Try extracting from markdown code block (closed or unclosed)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)(?:```|$)", text, re.IGNORECASE)
    extracted_block = fence_match.group(1).strip() if fence_match else text

    # Step 3: Find outermost JSON object braces { ... }
    first_brace = extracted_block.find("{")
    last_brace = extracted_block.rfind("}")

    candidates = []
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        candidates.append(extracted_block[first_brace : last_brace + 1])

    # Also search the full text in case markdown fence extraction was misaligned
    first_brace_all = text.find("{")
    last_brace_all = text.rfind("}")
    if first_brace_all != -1 and last_brace_all != -1 and last_brace_all > first_brace_all:
        candidates.append(text[first_brace_all : last_brace_all + 1])

    candidates.append(extracted_block)
    candidates.append(text)

    for cand in candidates:
        # A. Direct JSON parse
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # B. Clean comments & trailing commas
        cleaned = cand
        cleaned = re.sub(r"//.*?\n", "\n", cleaned)
        cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)

        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        # C. Python ast.literal_eval for single-quoted dict strings
        try:
            data = ast.literal_eval(cleaned)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    # Step 4: Key-Value Regex Fallback
    fallback_data: Dict[str, Any] = {}

    for field in ["full_name", "email", "phone", "title", "min_experience", "justification", "recommendation", "description_text"]:
        match = re.search(rf'[\*\"_`]*{field}[\*\"_`]*\s*[:=]\s*["\']?([^"\',\n\r]+)["\']?', text, re.IGNORECASE)
        if match:
            fallback_data[field] = match.group(1).strip()

    for list_field in ["skills", "required_skills", "experience", "education", "matching_skills", "missing_skills", "strengths", "weaknesses"]:
        match = re.search(rf'[\*\"_`]*{list_field}[\*\"_`]*\s*[:=]\s*\[([\s\S]*?)\]', text, re.IGNORECASE)
        if match:
            items_str = match.group(1)
            items = re.findall(r'["\']([^"\']+)["\']', items_str)
            if not items and items_str.strip():
                items = [i.strip() for i in items_str.split(",") if i.strip()]
            fallback_data[list_field] = items

    score_match = re.search(r'[\*\"_`]*match_score[\*\"_`]*\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
    if score_match:
        fallback_data["match_score"] = float(score_match.group(1))

    if fallback_data and ("full_name" in fallback_data or "skills" in fallback_data or "title" in fallback_data or "match_score" in fallback_data):
        return fallback_data

    raise ValueError(f"Failed to decode valid JSON from LLM response.\nRaw Output:\n{raw_response[:400]}")


# ==============================================================================
# COMPOUND REQUIREMENT & SKILL RECONCILIATION
# ==============================================================================

def _split_sub_technologies(text: str) -> List[str]:
    """Splits a clause containing multiple technologies separated by and, or, commas, slashes."""
    cleaned = re.sub(r"\b(e\.g\.?|including|such as|like|etc\.?)\b", "", text, flags=re.IGNORECASE).strip()
    raw_tokens = re.split(r"[,/|;+]|\band\b|\bor\b", cleaned, flags=re.IGNORECASE)
    sub_techs = []
    for token in raw_tokens:
        tok = token.strip().strip("'\"()[]{}")
        if tok and len(tok) > 1 and tok.lower() not in {"and", "or", "etc", "such as", "like", "including"}:
            sub_techs.append(tok)
    return sub_techs


def _decompose_compound_requirement(skill_str: str) -> Tuple[bool, List[str]]:
    """
    Determines if a skill string is a compound requirement (e.g. containing parenthetical examples
    or 'such as' clauses) and extracts its explicit component technologies.
    """
    s = skill_str.strip()

    # 1. Match parenthetical expressions: "(including LangChain and LangGraph)", "(e.g. MySQL, PostgreSQL)", etc.
    paren_match = re.search(r"\((?:including|e\.g\.?|such as|like)?\s*([^\)]+)\)", s, re.IGNORECASE)
    if paren_match:
        inner = paren_match.group(1).strip()
        tokens = _split_sub_technologies(inner)
        if len(tokens) >= 1:
            return True, tokens

    # 2. Match phrases like "... such as FastAPI and Flask", "... including React and Vue"
    phrase_match = re.search(r"\b(?:such as|including|like)\s+(.+)$", s, re.IGNORECASE)
    if phrase_match:
        after_phrase = phrase_match.group(1).strip()
        tokens = _split_sub_technologies(after_phrase)
        if len(tokens) >= 1:
            return True, tokens

    return False, []


def _is_exact_single_match(req_skill: str, cand_skill: str) -> bool:
    """Strict token and alias matching between required skill and candidate skill."""
    r = req_skill.strip().lower()
    c = cand_skill.strip().lower()

    if r == c:
        return True

    # Check aliases
    for canon, aliases in CANONICAL_ALIASES.items():
        if r in aliases and c in aliases:
            return True

    # Protect Java vs JavaScript
    if r == "java" and "javascript" in c:
        return False
    if r == "sql" and c in {"mysql", "postgresql", "nosql", "sqlite"}:
        return False

    return False


def _match_skill_against_candidate(
    req_skill: str,
    candidate_skills: List[str],
    candidate_exp: List[Any],
    raw_text: str
) -> Tuple[bool, str]:
    """
    Checks if a required skill is present in the candidate profile using exact/alias matching
    and strict word-boundary regex over text.
    """
    r_clean = req_skill.strip()
    r_lower = r_clean.lower()

    # 1. Direct candidate skills array check
    for cs in candidate_skills:
        if _is_exact_single_match(r_clean, cs):
            return True, cs

    # 2. Technologies in structured experience
    for exp in candidate_exp:
        if isinstance(exp, dict):
            techs = exp.get("technologies") or []
            for t in techs:
                if _is_exact_single_match(r_clean, t):
                    return True, t

    # 3. Word boundary regex in full resume text
    # Java protection
    if r_lower == "java":
        pattern = r"\bjava\b(?!script)"
    elif r_lower == "sql":
        pattern = r"(?<!my)(?<!postgre)(?<!no)(?<!pl/)\bsql\b(?!ite)"
    elif r_lower == "c":
        pattern = r"\bc\b(?![+#])"
    elif r_lower in CANONICAL_ALIASES:
        pattern = r"\b(" + "|".join(re.escape(a) for a in CANONICAL_ALIASES[r_lower]) + r")\b"
    else:
        pattern = rf"\b{re.escape(r_clean)}\b"

    full_text = f"{' '.join(candidate_skills)} {raw_text}"
    if re.search(pattern, full_text, re.IGNORECASE):
        return True, r_clean

    return False, ""


def reconcile_skills(
    job_skills: List[str],
    candidate_skills: List[str],
    candidate_exp: List[Any],
    raw_text: str,
    model_matching: List[str] = None
) -> Tuple[List[str], List[str]]:
    """
    Deterministic reconciliation of matching and missing skills.
    Decomposes compound skills and enforces strict mutual exclusivity.
    """
    final_matching = []
    final_missing = []

    model_matching_lower = {s.strip().lower() for s in (model_matching or [])}

    for req in job_skills:
        req_clean = req.strip()
        if not req_clean:
            continue

        is_compound, sub_techs = _decompose_compound_requirement(req_clean)

        if is_compound and sub_techs:
            # Evaluate each component sub-technology
            matched_subs = []
            missing_subs = []

            for sub in sub_techs:
                is_match, matched_name = _match_skill_against_candidate(sub, candidate_skills, candidate_exp, raw_text)
                if is_match or sub.lower() in model_matching_lower:
                    matched_subs.append(matched_name or sub)
                else:
                    missing_subs.append(sub)

            if len(matched_subs) == len(sub_techs):
                # All sub-techs satisfied! Add all to matching, none to missing
                for ms in matched_subs:
                    if ms not in final_matching:
                        final_matching.append(ms)
            elif len(matched_subs) > 0:
                # Partial match of compound requirement
                for ms in matched_subs:
                    if ms not in final_matching:
                        final_matching.append(ms)
                for mis in missing_subs:
                    if mis not in final_missing:
                        final_missing.append(mis)
            else:
                # None of the sub-techs matched
                final_missing.append(req_clean)
        else:
            # Single requirement
            is_match, matched_name = _match_skill_against_candidate(req_clean, candidate_skills, candidate_exp, raw_text)
            if is_match or req_clean.lower() in model_matching_lower:
                final_matching.append(matched_name or req_clean)
            else:
                final_missing.append(req_clean)

    # Clean duplicates and enforce strict mutual exclusivity
    matching_lower_map = {m.lower(): m for m in final_matching}
    cleaned_missing = []

    for mis in final_missing:
        mis_lower = mis.lower()
        # If the missing item or any of its sub-techs is in matching, remove it
        if mis_lower in matching_lower_map:
            continue
        # Also check if mis is a compound phrase whose sub-techs are all in matching
        is_comp, subs = _decompose_compound_requirement(mis)
        if is_comp and subs and all(sub.lower() in matching_lower_map for sub in subs):
            continue
        cleaned_missing.append(mis)

    return final_matching, cleaned_missing


def _sanitize_weaknesses(weaknesses: List[str], matching_skills: List[str], missing_skills: List[str]) -> List[str]:
    """
    Ensures weaknesses never contradict matching_skills.
    If a weakness claims the candidate lacks a matching skill, corrects or filters the statement.
    """
    matching_lower = {s.strip().lower() for s in matching_skills}
    cleaned_weaknesses = []

    for w in weaknesses:
        w_clean = w.strip()
        if not w_clean:
            continue

        contradictory = False
        for m_skill in matching_lower:
            pattern = rf"\b(lack|lacks|no|missing|without|limited)\b[\w\s,]*\b{re.escape(m_skill)}\b"
            if re.search(pattern, w_clean, re.IGNORECASE):
                genuine_missing = [ms for ms in missing_skills if re.search(rf"\b{re.escape(ms.lower())}\b", w_clean, re.IGNORECASE)]
                if genuine_missing:
                    w_clean = f"Lacks experience in required skill: {', '.join(genuine_missing)}"
                    contradictory = False
                    break
                else:
                    contradictory = True
                    break

        if not contradictory and w_clean not in cleaned_weaknesses:
            cleaned_weaknesses.append(w_clean)

    return cleaned_weaknesses


def _sanitize_justification(justification: str, matching_skills: List[str], missing_skills: List[str]) -> str:
    """Ensures justification text does not falsely claim the candidate lacks matching skills."""
    if not justification:
        return justification
    j_text = justification
    matching_lower = {s.strip().lower() for s in matching_skills}
    for m in matching_lower:
        pattern = rf"\b(lack|lacks|lacking|no)\s+(?:experience\s+in\s+|knowledge\s+of\s+)?{re.escape(m)}\b"
        if re.search(pattern, j_text, re.IGNORECASE):
            j_text = re.sub(pattern, f"demonstrated {m}", j_text, flags=re.IGNORECASE)
    return j_text


# ==============================================================================
# CORE GEMINI LLM SERVICES
# ==============================================================================

def extract_candidate_profile(resume_text: str) -> Dict[str, Any]:
    """
    Extracts structured candidate profile data from raw resume text using Google Gemini API.
    Applies strict validation and post-processing for structured experience, education, and skills.
    """
    if not resume_text or not resume_text.strip():
        raise ValueError("Cannot extract profile from empty resume text.")

    client = _get_gemini_client()

    user_content = f"Please extract structured profile information from the following resume text:\n\n{resume_text.strip()}"

    config = types.GenerateContentConfig(
        system_instruction=RESUME_EXTRACTION_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=CandidateProfile,
        temperature=0.1,
    )

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=user_content,
            config=config,
        )
        raw_output = response.text or ""
    except Exception as e:
        raise _format_gemini_error(e) from e

    parsed_json = _parse_llm_json_response(raw_output)

    # Post-process skills, experience, and education to ensure structured format
    cleaned_skills = _clean_and_normalize_skills(parsed_json.get("skills"))
    cleaned_experience = _clean_and_normalize_experience(parsed_json.get("experience"))
    cleaned_education = _clean_and_normalize_education(parsed_json.get("education"))

    raw_profile_dict = {
        "full_name": str(parsed_json.get("full_name") or "").strip(),
        "email": str(parsed_json.get("email") or "").strip(),
        "phone": str(parsed_json.get("phone") or "").strip(),
        "skills": cleaned_skills,
        "experience": cleaned_experience,
        "education": cleaned_education,
    }

    # Clean out schema labels from contact info
    if raw_profile_dict["full_name"].lower() in SCHEMA_LABELS: raw_profile_dict["full_name"] = ""
    if raw_profile_dict["email"].lower() in SCHEMA_LABELS: raw_profile_dict["email"] = ""
    if raw_profile_dict["phone"].lower() in SCHEMA_LABELS: raw_profile_dict["phone"] = ""

    # Validate through CandidateProfile Pydantic model
    try:
        profile = CandidateProfile.model_validate(raw_profile_dict)
    except Exception:
        exp_objs = [ExperienceItem.model_validate(x) if isinstance(x, dict) else ExperienceItem(title=str(x)) for x in cleaned_experience]
        edu_objs = [EducationItem.model_validate(x) if isinstance(x, dict) else EducationItem(degree=str(x)) for x in cleaned_education]
        profile = CandidateProfile(
            full_name=raw_profile_dict["full_name"],
            email=raw_profile_dict["email"],
            phone=raw_profile_dict["phone"],
            skills=cleaned_skills,
            experience=exp_objs,
            education=edu_objs,
        )

    return profile.model_dump()


def extract_job_profile(jd_text: str) -> Dict[str, Any]:
    """
    Extracts structured job requirements (title, required_skills, min_experience, description_text)
    from raw job description text using Google Gemini API.
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("Cannot extract job profile from empty job description text.")

    client = _get_gemini_client()

    user_content = f"Please extract structured job requirements from the following job description text:\n\n{jd_text.strip()}"

    config = types.GenerateContentConfig(
        system_instruction=JOB_EXTRACTION_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=JobDescriptionExtract,
        temperature=0.1,
    )

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=user_content,
            config=config,
        )
        raw_output = response.text or ""
    except Exception as e:
        raise _format_gemini_error(e) from e

    parsed_json = _parse_llm_json_response(raw_output)

    title = str(parsed_json.get("title") or "").strip()
    if not title or title.lower() in {"n/a", "none", "unknown", ""}:
        title = "Uploaded Job Description"

    required_skills = parsed_json.get("required_skills")
    if not isinstance(required_skills, list):
        required_skills = [str(required_skills)] if required_skills else []
    required_skills = [str(s).strip() for s in required_skills if str(s).strip()]

    min_exp = parsed_json.get("min_experience")
    if min_exp is not None:
        min_exp = str(min_exp).strip()
        if min_exp.lower() in {"n/a", "none", "null", ""}:
            min_exp = None

    desc_text = str(parsed_json.get("description_text") or "").strip()
    if not desc_text:
        desc_text = jd_text.strip()

    return {
        "title": title,
        "required_skills": required_skills,
        "min_experience": min_exp,
        "description_text": desc_text,
    }


def evaluate_candidate(candidate: Any, job: Any) -> EvaluationResult:
    """
    Evaluates a candidate's profile against a job description using Google Gemini API.
    Features an automatic 1-retry mechanism with explicit fallback if the first attempt fails.

    Args:
        candidate: Candidate ORM object or dictionary with candidate details.
        job: JobDescription ORM object or dictionary with job details.

    Returns:
        EvaluationResult with match_score, justification, skills gap, strengths, weaknesses, and recommendation.

    Raises:
        ValueError: If Gemini calls fail or do not return valid EvaluationResult JSON.
    """
    client = _get_gemini_client()

    # 1. Normalize candidate details
    if hasattr(candidate, "full_name"):
        cand_name = candidate.full_name or "Candidate"
        cand_skills = candidate.skills or []
        cand_exp = candidate.experience or []
        cand_edu = candidate.education or []
        cand_raw = getattr(candidate, "raw_text", "")
    elif isinstance(candidate, dict):
        cand_name = candidate.get("full_name") or "Candidate"
        cand_skills = candidate.get("skills") or []
        cand_exp = candidate.get("experience") or []
        cand_edu = candidate.get("education") or []
        cand_raw = candidate.get("raw_text") or ""
    else:
        raise ValueError("Invalid candidate object provided.")

    # 2. Normalize job description details
    if hasattr(job, "title"):
        job_title = job.title or "Target Position"
        job_desc = job.description_text or ""
        job_skills = job.required_skills or []
        job_exp = job.min_experience or "Not specified"
    elif isinstance(job, dict):
        job_title = job.get("title") or "Target Position"
        job_desc = job.get("description_text") or ""
        job_skills = job.get("required_skills") or []
        job_exp = job.get("min_experience") or "Not specified"
    else:
        raise ValueError("Invalid job object provided.")

    # 3. Construct user evaluation prompt
    user_prompt = f"""TARGET JOB DESCRIPTION:
- Title: {job_title}
- Minimum Experience: {job_exp}
- Mandatory Required Skills: {json.dumps(job_skills) if isinstance(job_skills, list) else job_skills}
- Job Description Details:
{job_desc}

CANDIDATE PROFILE:
- Name: {cand_name}
- Candidate Skills: {json.dumps(cand_skills) if isinstance(cand_skills, list) else cand_skills}
- Work Experience & Projects: {json.dumps(cand_exp) if isinstance(cand_exp, list) else cand_exp}
- Education: {json.dumps(cand_edu) if isinstance(cand_edu, list) else cand_edu}
- Resume Excerpt:
{cand_raw[:1500] if cand_raw else "N/A"}

Please evaluate this candidate against the job description and return the structured JSON evaluation following all consistency rules."""

    def _process_and_validate(parsed_json: Dict[str, Any]) -> EvaluationResult:
        """Internal helper to sanitize and validate candidate evaluation dictionary."""
        # Reconcile matching and missing skills with compound-skill aware decomposition
        if isinstance(job_skills, list) and len(job_skills) > 0:
            model_matching = parsed_json.get("matching_skills") or []
            final_matching, final_missing = reconcile_skills(
                job_skills=job_skills,
                candidate_skills=cand_skills,
                candidate_exp=cand_exp,
                raw_text=cand_raw,
                model_matching=model_matching
            )
            parsed_json["matching_skills"] = final_matching
            parsed_json["missing_skills"] = final_missing

        # Sanitize weaknesses to remove contradictions with matching skills
        raw_weaknesses = parsed_json.get("weaknesses") if isinstance(parsed_json.get("weaknesses"), list) else []
        parsed_json["weaknesses"] = _sanitize_weaknesses(
            raw_weaknesses,
            parsed_json.get("matching_skills", []),
            parsed_json.get("missing_skills", []),
        )

        # Sanitize justification text
        raw_just = parsed_json.get("justification") or ""
        parsed_json["justification"] = _sanitize_justification(
            raw_just,
            parsed_json.get("matching_skills", []),
            parsed_json.get("missing_skills", [])
        )

        # Ensure match_score is within bounds [1.0, 10.0]
        raw_score = float(parsed_json.get("match_score", 5.0))
        clamped_score = max(1.0, min(10.0, round(raw_score, 1)))
        parsed_json["match_score"] = clamped_score

        # Harmonize recommendation with score
        rec = str(parsed_json.get("recommendation", "")).strip().upper()
        if rec not in {"SHORTLISTED", "REVIEW", "REJECTED"}:
            if clamped_score >= 7.5:
                rec = "SHORTLISTED"
            elif clamped_score >= 5.0:
                rec = "REVIEW"
            else:
                rec = "REJECTED"
        parsed_json["recommendation"] = rec

        # Ensure list fields are lists
        for list_field in ["matching_skills", "missing_skills", "strengths", "weaknesses"]:
            if not isinstance(parsed_json.get(list_field), list):
                parsed_json[list_field] = [str(parsed_json[list_field])] if parsed_json.get(list_field) else []

        return EvaluationResult.model_validate(parsed_json)

    # --- Attempt 1: Standard Evaluation ---
    config_attempt1 = types.GenerateContentConfig(
        system_instruction=CANDIDATE_MATCHING_SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=EvaluationResult,
        temperature=0.1,
    )

    raw_output_attempt1 = ""
    try:
        response1 = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=user_prompt,
            config=config_attempt1,
        )
        raw_output_attempt1 = response1.text or ""
        parsed_json1 = _parse_llm_json_response(raw_output_attempt1)
        return _process_and_validate(parsed_json1)
    except Exception as first_err:
        # Fall through to Attempt 2 (Safe Retry)
        pass

    # --- Attempt 2: Explicit Single Retry ---
    retry_system_prompt = (
        "Your previous response was invalid because it did not contain a JSON evaluation.\n"
        "You MUST evaluate the candidate against the job description.\n"
        "Even if there is zero compatibility or the candidate is completely irrelevant, you must return a valid evaluation.\n"
        "Return ONLY valid raw JSON starting with '{' and ending with '}'.\n"
        "Do not refuse. Do not explain. Do not ask questions."
    )

    config_attempt2 = types.GenerateContentConfig(
        system_instruction=retry_system_prompt,
        response_mime_type="application/json",
        response_schema=EvaluationResult,
        temperature=0.1,
    )

    raw_output_attempt2 = ""
    try:
        response2 = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=user_prompt,
            config=config_attempt2,
        )
        raw_output_attempt2 = response2.text or ""
        parsed_json2 = _parse_llm_json_response(raw_output_attempt2)
        return _process_and_validate(parsed_json2)
    except Exception as final_err:
        preview = (raw_output_attempt2 if raw_output_attempt2 else raw_output_attempt1)[:150].replace("\n", " ").strip()
        if preview:
            raise ValueError(
                f"LLM evaluation failed after one retry because the model did not return valid EvaluationResult JSON. (Preview: '{preview}')"
            ) from final_err
        else:
            raise _format_gemini_error(final_err) from final_err
