
🧪 NBP Lab
A Reproducible Experiment Engine for Nano Banana Pro (Gemini 3 Pro Image)
NBP Lab is a controlled research framework for designing, running, analyzing, and publishing experiments on Nano Banana Pro.
It exists to answer structural questions like:
Does upload order actually matter?
Do early slots dominate later ones?
Does removing human references increase object fidelity?
When prompt and references disagree, who wins?
Are reference images influence… or structural instructions?
NBP Lab turns speculation into measurable evidence.

🎯 Mission
To quantify how:
Number of reference images
Type of reference images
Upload order
Reference quality (crop, blur, compression)
Ambiguity in references
Prompt/reference conflicts
Resolution tier / thinking level
Context persistence across scenes
affect Nano Banana Pro outputs.

🧠 Philosophy
NBP Lab is built on five principles:
Single-variable isolation
Repeat runs (no single-shot claims)
Full provenance logging
Toggleable telemetry transparency
Exportable, auditable research bundles
This is not an art tool.It is a measurement tool.

🧱 Core Hypothesis Model (Tested, Not Assumed)
NBP Lab is designed to test this working slot model:

NBP Lab allows you to validate, falsify, or refine this structure.

🔁 Experiment Architecture
Every experiment follows:
Experiment
  ├── Conditions (A / B / C)
  │     ├── Upload Plan (ordered array)
  │     ├── Prompt
  │     ├── Render Settings
  │     └── Telemetry Mode
  ├── Runs (repeat count)
  ├── Scores
  ├── Telemetry (optional)
  └── Export Bundle

🛠 Feature Overview

1️⃣ Experiment Designer
Drag-and-drop reference buckets
Deterministic upload array generation
Variable isolation (count, order, conflict, quality)
Repeat control
Render control (resolution, aspect ratio)
Telemetry toggle
Reference QC integration (Gemini analysis)

2️⃣ Reference QC Layer (Gemini Per-Image Analysis)
Before running experiments, each reference image is analyzed via Gemini.
This converts subjective input into structured variables.
Data Extracted Per Image
Role Inference
role_guess (human_identity / object_fidelity / environment_plate / style_look / composition_pose / texture_material / mixed)
role_confidence
mixed_roles
Quality Metrics
sharpness_level
motion_blur
compression_artifacts
lighting_quality
occlusion
noise_level
resolution_px
subject_size_ratio
Face / Identity Attributes
faces_count
dominant_face_count
head_angle
face_visibility
distinctive_features_present
Environment & Geometry
environment_type
camera_height_guess
lens_feel
perspective_strength
vanishing_lines_visible
Lighting Signature
key_light_direction
shadow_hardness
time_of_day_guess
color_temperature
contrast_level
Style Fingerprint
style_family
grade_notes
grain_presence
palette_summary
Ambiguity Score
ambiguity_score (0–1)
ambiguity_explanation

Why This Matters
You can now correlate:
Identity drift vs face_visibility
Hallucination vs ambiguity_score
Geometry coherence vs perspective_strength
Lighting override vs key_light_direction mismatch
This makes your experiments statistically meaningful.

3️⃣ Runner / Orchestrator
Executes all condition × repeat combinations.
Stores:
Prompt
Ordered reference list
Model settings
Output image
Optional telemetry (see below)
All runs reproducible via manifest JSON.

🔍 Telemetry Mode (Master Toggle)
NBP Lab includes a single master telemetry switch.

📴 Telemetry OFF (Black Box Mode)
When OFF:
No thought summaries requested
No thought signatures stored
No token usage metadata stored
No safety diagnostics stored
No latency breakdown shown
No allocation parsing
No internal reasoning shown
Stored data includes only:
Prompt
Reference list + order
Model settings
Output image
Zero under-the-hood exposure.

🟢 Telemetry ON (Glass Box Mode)
When ON:
Captured & Stored
Thought Summaries
includeThoughts: true
Raw thought content stored
Thought Signatures
Stored for multi-turn continuity
Enables “Context Locked” indicator
Token Usage Metadata
prompt_token_count
candidates_token_count
Raw usage object
Latency
Response time in ms
Thinking Level (if supported)
HIGH / MINIMAL
Safety Diagnostics
Harm categories
Probability levels
Resolution Tier
1K / 2K / 4K cost comparison
ALLOCATION_REPORT Parsing
Parsed JSON from structured reasoning trace
Claimed gate usage percentages
Claimed slot mappings

UI Indicators
🔒 Context Locked (thought signature active)
🧠 Thinking Level badge
📊 Token usage panel
🛑 Safety diagnostics panel
📦 Allocation report summary

🧪 Scoring System
Manual scoring:
Identity Stability (1–10)
Object Fidelity (1–10)
Style Adherence (1–10)
Environment Coherence (1–10)
Hallucination (Y/N)
Notes
Optional:
LLM Judge scoring
Blind scoring mode
Automated similarity metrics

📊 Analysis Engine
Generates:
Mean & standard deviation per condition
Win-rate comparisons
Drift frequency
Hallucination rate
Telemetry correlation tables
Token vs quality plots
Ambiguity vs hallucination correlation

📦 Export Bundle
Each experiment exports:
1) Image Grids
Condition × Repeat
2) Score Tables
CSV + summary charts
3) Manifest JSON
Full reproducibility spec:
Prompt
Upload array
Model
Telemetry state
4) Telemetry Appendix (if ON)
Token usage tables
Latency histograms
Allocation report summaries
Safety breakdown
Context persistence status

🗂 Data Model
Core Tables:
experiments
conditions
runs
assets
asset_qc (Gemini analysis results)
scores
Telemetry Tables (only when ON):
run_telemetry
telemetry_extractions
allocation_reports
safety_logs
If Telemetry OFF:
run_telemetry does not exist for that run.

🔬 Supported Experiment Templates
Slot Order Test
Prompt vs Reference Authority
Reallocation Test (unused slots)
Reference Quality Degradation
Ambiguity Impact Test
Multi-Face Contamination Test
Style Conflict Test
Environment Geometry Test
Context Persistence Test
Lighting Override Test

🧠 Advanced Developer Mode
Optional system instruction injection:
When generating an image, provide a brief 'Reasoning Trace'.
Explicitly state which images were used for:
- Character Identity
- Object Fidelity
- Global Physics
Output a JSON block labeled ALLOCATION_REPORT.
Parsed automatically when telemetry is ON.

📈 What This Enables
With NBP Lab you can publish claims like:
“Order matters more than count.”
“Ambiguous references increase hallucinations by 32%.”
“Removing identity references increases material fidelity but reduces pose stability.”
“Environment plates alter camera height inference.”
“Context locking reduces drift across scene chains.”

⚠️ Limitations
Thought summaries are model self-report, not guaranteed ground truth.
Telemetry may vary across API surfaces.
Image generation remains probabilistic.
Correlation ≠ causation (repeat counts matter).

🚀 Roadmap
Statistical significance testing
Multi-model comparison
Embedding-based geometry comparison
Automated hallucination detector
Public experiment repository

🧪 Final Statement
NBP Lab is not about proving a theory.
It is about building a measurement instrument capable of disproving one.

