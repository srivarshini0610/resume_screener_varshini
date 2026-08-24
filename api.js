/**
 * TalentLens AI - API Client
 * Backend: http://127.0.0.1:8002
 */
const API_BASE_URL = window.API_BASE_URL || "http://127.0.0.1:8002";

const ApiService = {
    async uploadResume(file, jobId = null) {
        const fd = new FormData();
        fd.append("file", file);
        if (jobId) fd.append("job_id", jobId);
        const r = await fetch(`${API_BASE_URL}/api/candidates/upload`, { method: "POST", body: fd });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Upload failed (${r.status})`);
        return d;
    },
    async getCandidates() {
        const r = await fetch(`${API_BASE_URL}/api/candidates/`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async getCandidatesByJob(jobId) {
        const r = await fetch(`${API_BASE_URL}/api/candidates/job/${jobId}`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async getCandidatesGroupedByJob() {
        const r = await fetch(`${API_BASE_URL}/api/candidates/grouped-by-job`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async uploadJobDescription(file) {
        const fd = new FormData();
        fd.append("file", file);
        const r = await fetch(`${API_BASE_URL}/api/jobs/upload`, { method: "POST", body: fd });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async getJobs() {
        const r = await fetch(`${API_BASE_URL}/api/jobs/`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async createJob(jobData) {
        const r = await fetch(`${API_BASE_URL}/api/jobs/`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(jobData),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async deleteJob(jobId) {
        const r = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`, { method: "DELETE" });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async screenCandidates(jobId, candidateIds = null) {
        const payload = { job_id: jobId };
        if (candidateIds && candidateIds.length > 0) payload.candidate_ids = candidateIds;
        const r = await fetch(`${API_BASE_URL}/api/screening/evaluate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async getScreeningResults(jobId) {
        const r = await fetch(`${API_BASE_URL}/api/screening/results/${jobId}`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
    async getEvaluation(evaluationId) {
        const r = await fetch(`${API_BASE_URL}/api/screening/evaluation/${evaluationId}`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `Failed (${r.status})`);
        return d;
    },
};
window.ApiService = ApiService;
