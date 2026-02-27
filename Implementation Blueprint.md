Implementation Blueprint.md
NBP Lab — Nano Banana Pro Experiment Engine

1. Scope (MVP)
Objective
Build a reproducible experiment engine for Nano Banana Pro that:
Designs controlled experiments
Runs condition × repeat matrices
Scores outputs
Optionally captures full telemetry
Analyzes results
Exports publishable research bundles

Core MVP Features
Experiment Designer
Reference QC (Gemini per-image analysis)
Batch Runner / Orchestrator
Telemetry Mode (Master Toggle)
Scoring System
Export Bundle Generator

Non-Goals (MVP)
Multi-user auth
Cloud deployment
Advanced statistical significance engine
Automated CV similarity metrics
Multi-model comparison

2. System Architecture
Frontend (React)
    |
FastAPI Backend
    |
Postgres Database
    |
Background Worker (RQ / Celery / Arq)
    |
Nano Banana Pro API
    |
Gemini Vision API (Reference QC)

3. Authoritative Repository Structure
nbp-lab/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── telemetry/
│   │   ├── qc/
│   │   ├── scoring/
│   │   └── export/
│   ├── migrations/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── api/
│   │   └── utils/
│
├── exports/
├── scripts/
├── Implementation Blueprint.md
└── README.md
This structure is fixed. Copilot must not invent additional top-level folders.

4. Domain Model & Invariants
Core Entities
Experiment
id
name
hypothesis
telemetry_enabled (boolean)
model_name
render_settings (JSON)
created_at
Condition
id
experiment_id
name
prompt
upload_plan (ordered list of asset IDs)
created_at
Run
id
condition_id
repeat_index
status (queued, running, succeeded, failed)
output_image_path
latency_ms
created_at
Asset
id
file_path
hash
uploaded_at
AssetQC (Reference QC Layer)
id
asset_id
role_guess
role_confidence
ambiguity_score
quality_json
face_json
environment_json
lighting_json
style_json
created_at
Score
id
run_id
identity_score
object_score
style_score
environment_score
hallucination (boolean)
notes
created_at

5. Telemetry Mode — HARD INVARIANT
Rule
If experiment.telemetry_enabled == false:
No thought summaries requested
No telemetry persisted
No telemetry displayed
No telemetry exported
Telemetry data must not exist in DB for that run.

Telemetry Tables (Only When Enabled)
RunTelemetry
run_id
thought_summary_raw
thought_signature
usage_metadata_json
safety_metadata_json
thinking_level
latency_ms
allocation_report_json
If telemetry is OFF → RunTelemetry row must not exist.

6. Database Schema (Postgres)
Use SQLAlchemy + Alembic.
Enums:
run_status_enum
role_guess_enum
Indexes:
experiment_id
condition_id
run_id
asset_id
Foreign key relationships enforced.

7. Background Job Pipeline
States:
queued
running
succeeded
failed
Pipeline:
Create runs
Enqueue jobs
Worker executes:
Build request
Respect telemetry flag
Call Nano Banana Pro
Store output image
Store latency
If telemetry ON:
Store thought summary
Store thought signature
Store usage metadata
Store safety metadata
Parse ALLOCATION_REPORT (if present)
Update run status

8. API Contract
POST /experiments
Creates experiment.
GET /experiments/{id}
POST /experiments/{id}/conditions
POST /experiments/{id}/run
Creates runs and enqueues jobs.
GET /runs/{id}
POST /runs/{id}/score
POST /assets
Upload reference image.
POST /assets/{id}/analyze
Triggers Gemini Reference QC.
POST /experiments/{id}/export
Generates export bundle.
All endpoints must return structured JSON.

9. Reference QC Service (Gemini)
For each image, call Gemini Vision with strict JSON schema.
Extract:
role_guess
role_confidence
ambiguity_score
quality metrics
face metrics
environment metrics
lighting metrics
style metrics
Persist structured JSON in AssetQC table.

10. Telemetry Extraction Service
If telemetry ON:
Parse thought_summary_raw
Extract ALLOCATION_REPORT if present
Extract claimed slot usage
Extract claimed percentages
Persist structured telemetry_extractions

11. Frontend Screens
1. Experiment Builder
Create experiment
Toggle Telemetry
Add conditions
Assign upload order
2. Reference QC Panel
Show Gemini analysis per image
Show ambiguity warnings
3. Run Monitor
Show status grid
Show latency
If telemetry ON → show token usage + context lock indicator
4. Results Grid
Condition × Repeat layout
Score inputs
Telemetry panel (if enabled)
5. Export Screen
Generate bundle
Download ZIP

12. Export Bundle Specification
exports/
  experiment_name/
    manifest.json
    scores.csv
    image_grid.png
    runs/
      condition_A_run1.png
      condition_A_run2.png
      ...
    telemetry_appendix.csv (if ON)
    allocation_reports.jsonl (if ON)
manifest.json must include:
prompt
upload arrays
model
telemetry flag
timestamp

13. Acceptance Criteria
Telemetry OFF:
No RunTelemetry rows created
No telemetry shown in UI
Export contains no telemetry files
Telemetry ON:
Thought summaries stored
Usage metadata stored
Allocation report parsed
Export includes telemetry appendix
Experiment Reproducibility:
Rerunning same manifest reproduces same structure (not same image, but same conditions)
Reference QC:
Each uploaded image must have AssetQC row before experiment run allowed

14. Error Handling Rules
API failure → run status = failed
Safety block → store safety metadata (if telemetry ON)
Invalid ALLOCATION_REPORT → store raw but mark parse_status = invalid
Missing thought_signature → context lock = false

15. Build Order (For Copilot Agent)
Create backend structure
Implement DB schema + migrations
Implement experiment + condition routes
Implement asset upload
Implement Reference QC service
Implement runner + worker
Implement telemetry logic
Implement scoring
Implement export bundle
Build frontend screens

16. Critical Engineering Constraints
Telemetry must be globally gated by experiment.telemetry_enabled
No telemetry leakage when OFF
All experiment runs must be reproducible from manifest.json
DB schema must enforce foreign keys
No business logic in frontend

17. Future Extensions
Statistical significance engine
Automated similarity metrics
Multi-model comparison
Public experiment library
Cloud deployment

Final Directive
This document is authoritative.
Copilot must:
Follow this file structure
Follow this schema
Respect telemetry invariants
Not invent new architectural patterns

