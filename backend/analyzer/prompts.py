"""Prompt builders for Stage 0, Stage 1, Stage 2."""
from __future__ import annotations
import json

# ─────────────────────────────────────────────────────────────
# STAGE 0 — Project list extraction (fast, title+abstract only)
# ─────────────────────────────────────────────────────────────

STAGE_0_SYSTEM = """You are an expert research analyst helping a new graduate student understand their lab's research landscape.
Given a list of paper titles and abstracts, identify the distinct ongoing research projects or themes in the lab.
Return ONLY valid JSON with no markdown fences, no explanation."""


def build_stage0_prompt(title_abstracts: list[dict]) -> str:
    papers_text = ''
    for i, p in enumerate(title_abstracts, 1):
        papers_text += f'[Paper {i}] {p["filename"]}\nTitle: {p["title"]}\nAbstract: {p["abstract"]}\n\n'

    return f"""Below are titles and abstracts from a research lab's recent papers.
Identify ALL distinct ongoing research projects or themes in this lab. Aim for 4-10 projects.

CRITICAL RULES:
- Do NOT collapse different research axes into one project. If the lab works on both topic A and topic B, they must be separate projects.
- Each project should correspond to a meaningfully different research question, method, or application domain.
- Even if two papers share a broad field, split them if they use different methods or target different problems.
- Assign each paper to the most specific matching project.

PAPERS:
{papers_text}

Return a JSON object with this exact structure:
{{
  "lab_name_guess": "short lab name based on research topics",
  "projects": [
    {{
      "id": 1,
      "name": "short project name (5-10 words)",
      "description": "1-2 sentence description of what this project does",
      "related_papers": ["filename1.pdf", "filename2.pdf"]
    }}
  ]
}}"""


# ─────────────────────────────────────────────────────────────
# STAGE 1 — Per-paper deep analysis
# ─────────────────────────────────────────────────────────────

STAGE_1_SYSTEM = """You are an expert research analyst. Analyze the given academic paper and extract structured information.
Return ONLY valid JSON with no markdown fences, no explanation outside JSON."""


def build_stage1_prompt(filename: str, title: str, sections_text: str,
                        project_context: str = '', is_reference: bool = False) -> str:
    ref_note = '\n[NOTE: This is a professor-recommended reference paper, not from the lab itself. Mark it as reference=true in output.]' if is_reference else ''
    proj_note = f'\n[Lab context: The student may be assigned to: {project_context}]' if project_context else ''

    return f"""Analyze this academic paper and extract structured information.{ref_note}{proj_note}

Filename: {filename}
Title: {title}

Paper content:
{sections_text}

Return JSON with this exact structure:
{{
  "filename": "{filename}",
  "title": "{title}",
  "is_reference": {"true" if is_reference else "false"},
  "field": "detected research field (e.g., robotics, molecular biology, deep learning, materials science)",
  "method_tag": "2-3 word tag like DRL/Model-based/Neuroscience/etc",
  "techniques": ["technique1", "technique2"],
  "key_results": ["result1", "result2"],
  "limitations": ["limitation1", "limitation2"],
  "future_directions": ["direction1", "direction2"],
  "key_terms": ["term1", "term2"],
  "paper_type": "simulation | experimental | theoretical | review | mixed — choose the most accurate",
  "summary": "2-3 sentence summary of what this paper does and finds",
  "limitation_for_hypo": "the single most exploitable limitation or gap for a follow-up hypothesis"
}}"""


# ─────────────────────────────────────────────────────────────
# STAGE 2 — Synthesis + hypothesis generation
# ─────────────────────────────────────────────────────────────

STAGE_2_SYSTEM = """You are an expert research mentor helping a new graduate student in Korea find their first research hypothesis.

=== LANGUAGE RULE (MANDATORY) ===
Write ALL descriptive content in Korean (한국어).
Only these may remain in English: method/technique names, model names, paper titles, metric names, venue names, code/variable names.
Everything else — rationale, statements, descriptions, explanations, summaries, fallback plans — MUST be written in Korean.


Your goal: generate practical, feasible hypotheses grounded in the lab's existing work.
Philosophy: each paper has a limitation — the student only needs to take ONE step forward.
Return ONLY valid JSON with no markdown fences.

=== MANDATORY HYPOTHESIS QUALITY RULES ===

RULE 1 — NO VAGUE CLAIMS. REQUIRE METRICS + BASELINE.
Every hypothesis MUST specify:
  - evaluation_metrics: concrete quantitative metrics (e.g., "CoT error < 5 cm on 15° slope", "energy consumption (J/step)", "success rate (%) over 20 trials")
  - baseline: the specific paper, method, or condition being compared against (e.g., "vs. single-sensor slip detection in [paper X]", "vs. fixed-gain PPO in GainAdaptor")
  Vague statements like "performance will improve" or "A combined with B will be better" are STRICTLY FORBIDDEN.
  Every metric must be measurable and every baseline must be citable.

RULE 2 — MANDATORY FALLBACK PLAN.
Every hypothesis MUST include a fallback_plan field addressing:
  - What academically valid contribution can be extracted from simulation alone if real hardware experiments fail?
  - What is the minimum publishable unit if the main hypothesis is only partially validated?
  - What is the pivot strategy if the core assumption turns out to be wrong?
  The fallback_plan must be specific (e.g., "If real-robot validation fails: publish sim-only ablation study showing [X] metric improvement with statistical significance in Isaac Gym; target IEEE RA-L as simulation-validated contribution").

RULE 3 — BAN NAIVE SYSTEM INTEGRATION (A+B).
Hypotheses that merely combine two existing lab systems without a new algorithmic contribution are FORBIDDEN.
  Forbidden pattern: "Apply method from paper X to platform Y" or "Integrate system A with system B".
  Required instead: propose a NEW algorithm, a novel physics-informed formulation, a new learning objective, or a new theoretical framework that addresses a fundamental physical/dynamical limitation.
  Each hypothesis must articulate: "The novelty is [specific algorithmic/theoretical contribution], which is fundamentally different from simply combining [A] and [B] because [reason]."

RULE 4 — REAL-TIME CONTROL LATENCY (applies to robotics / embedded / cyber-physical systems).
If a hypothesis involves running a heavy model (VLM, LLM, large neural net) alongside a high-frequency control loop on edge hardware:
  - You MUST specify the asynchronous frequency split. Example: "VLM semantic reasoning runs at 1 Hz (low-frequency); RL locomotion controller runs at 500 Hz (high-frequency); integrated asynchronously via shared state buffer."
  - You MUST identify which computation runs on which processor (e.g., VLM on CPU/cloud, RL policy on GPU/MCU).
  - Hypotheses that ignore control-loop latency in hardware-in-the-loop contexts are FORBIDDEN.

RULE 5 — TARGET METRICS MUST BE GROUNDED IN CITED BASELINES.
Arbitrary percentage improvements ("30% better", "40% improvement") with no cited source are FORBIDDEN.
  Required: ground every target metric in a specific published result from the papers provided or a well-known benchmark.
  Example format: "ANYmal (RSS 2023) achieves X% terrain adaptation error on 20° slope; our method targets <Y% under the same protocol."
  If no direct prior number is available, cite the closest comparable result and explain the adjustment.

RULE 6 — HARDWARE RISK: REQUIRE CROSS-PLATFORM VALIDATION PLAN.
If a hypothesis depends on a custom or lab-built robot/hardware that may break or be unavailable:
  - The fallback_plan MUST include a cross-validation plan on a second platform (commercial robot or standard simulator).
  - Example: "Primary validation on SUBO-2; algorithm generalizability proven via identical test protocol on Unitree Go1 in Isaac Gym simulation, ensuring the contribution is platform-agnostic."
  - This cross-validation plan strengthens the paper's generalization claim and protects against hardware downtime.
"""

STAGE_2_SYSTEM_EN = """You are an expert research mentor helping a new graduate student find their first research hypothesis.

=== LANGUAGE RULE (MANDATORY) ===
Write ALL content in English.

Your goal: generate practical, feasible hypotheses grounded in the lab's existing work.
Philosophy: each paper has a limitation — the student only needs to take ONE step forward.
Return ONLY valid JSON with no markdown fences.

=== MANDATORY HYPOTHESIS QUALITY RULES ===

RULE 1 — NO VAGUE CLAIMS. REQUIRE METRICS + BASELINE.
Every hypothesis MUST specify:
  - evaluation_metrics: concrete quantitative metrics (e.g., "CoT error < 5 cm on 15° slope", "energy consumption (J/step)", "success rate (%) over 20 trials")
  - baseline: the specific paper, method, or condition being compared against (e.g., "vs. single-sensor slip detection in [paper X]", "vs. fixed-gain PPO in GainAdaptor")
  Vague statements like "performance will improve" or "A combined with B will be better" are STRICTLY FORBIDDEN.
  Every metric must be measurable and every baseline must be citable.

RULE 2 — MANDATORY FALLBACK PLAN.
Every hypothesis MUST include a fallback_plan field addressing:
  - What academically valid contribution can be extracted from simulation alone if real hardware experiments fail?
  - What is the minimum publishable unit if the main hypothesis is only partially validated?
  - What is the pivot strategy if the core assumption turns out to be wrong?
  The fallback_plan must be specific (e.g., "If real-robot validation fails: publish sim-only ablation study showing [X] metric improvement with statistical significance in Isaac Gym; target IEEE RA-L as simulation-validated contribution").

RULE 3 — BAN NAIVE SYSTEM INTEGRATION (A+B).
Hypotheses that merely combine two existing lab systems without a new algorithmic contribution are FORBIDDEN.
  Forbidden pattern: "Apply method from paper X to platform Y" or "Integrate system A with system B".
  Required instead: propose a NEW algorithm, a novel physics-informed formulation, a new learning objective, or a new theoretical framework that addresses a fundamental physical/dynamical limitation.
  Each hypothesis must articulate: "The novelty is [specific algorithmic/theoretical contribution], which is fundamentally different from simply combining [A] and [B] because [reason]."

RULE 4 — REAL-TIME CONTROL LATENCY (applies to robotics / embedded / cyber-physical systems).
If a hypothesis involves running a heavy model (VLM, LLM, large neural net) alongside a high-frequency control loop on edge hardware:
  - You MUST specify the asynchronous frequency split. Example: "VLM semantic reasoning runs at 1 Hz (low-frequency); RL locomotion controller runs at 500 Hz (high-frequency); integrated asynchronously via shared state buffer."
  - You MUST identify which computation runs on which processor (e.g., VLM on CPU/cloud, RL policy on GPU/MCU).
  - Hypotheses that ignore control-loop latency in hardware-in-the-loop contexts are FORBIDDEN.

RULE 5 — TARGET METRICS MUST BE GROUNDED IN CITED BASELINES.
Arbitrary percentage improvements ("30% better", "40% improvement") with no cited source are FORBIDDEN.
  Required: ground every target metric in a specific published result from the papers provided or a well-known benchmark.
  Example format: "ANYmal (RSS 2023) achieves X% terrain adaptation error on 20° slope; our method targets <Y% under the same protocol."
  If no direct prior number is available, cite the closest comparable result and explain the adjustment.

RULE 6 — HARDWARE RISK: REQUIRE CROSS-PLATFORM VALIDATION PLAN.
If a hypothesis depends on a custom or lab-built robot/hardware that may break or be unavailable:
  - The fallback_plan MUST include a cross-validation plan on a second platform (commercial robot or standard simulator).
  - Example: "Primary validation on SUBO-2; algorithm generalizability proven via identical test protocol on Unitree Go1 in Isaac Gym simulation, ensuring the contribution is platform-agnostic."
  - This cross-validation plan strengthens the paper's generalization claim and protects against hardware downtime.
"""


def build_stage2_prompt(paper_analyses: list[dict], assigned_project: str,
                        professor_instructions: str, detected_field: str,
                        language: str = "ko") -> str:
    analyses_json = json.dumps(paper_analyses, ensure_ascii=False, indent=2)
    assigned_note = f'The student has been assigned to work on: "{assigned_project}"' if assigned_project else 'No specific project has been assigned yet.'
    prof_note = f'\nProfessor\'s additional instructions: {professor_instructions}' if professor_instructions else ''
    field_note = f'Primary research field detected: {detected_field}'

    if language == "en":
        sim_note = 'For hypotheses derived from simulation-type papers, prioritize simulation validation over experimental validation.'
        cost_note = 'Cost estimates in USD'
        student_desc = 'a new graduate student'
        period_example = '3-6 months'
        impact_desc_example = 'Solid thesis material. Explainable in job interviews.'
        cost_field = '"estimated_usd"'
    else:
        sim_note = 'paper_type 필드가 "simulation"인 논문에서 파생된 가설은 실험적 검증보다 시뮬레이션 검증을 우선으로 설계하세요'
        cost_note = 'Cost estimates in KRW for Korean market'
        student_desc = 'a new Korean graduate student'
        period_example = '3~6개월'
        impact_desc_example = '졸업 안정적. 취직 시 논문으로 설명 가능'
        cost_field = '"estimated_krw"'

    return f"""You are helping {student_desc} find their first research hypothesis.

{assigned_note}{prof_note}
{field_note}

Here are the analyses of all lab papers (and any professor-recommended references):
{analyses_json}

Generate a comprehensive Research Starter Kit. Follow these rules:
- H1-H6: Safe, incremental hypotheses directly from paper limitations/gaps
- H7: One trendy/ambitious hypothesis using the latest 2023-2025 research trends
- If assigned_project is specified: generate H1-H4 focused on that project, H5-H7 on other lab projects
- If no assigned project: distribute hypotheses across all lab projects
- Impact stars: ★★☆☆☆=solid master's thesis topic, ★★★☆☆=strong thesis + employable, ★★★★☆=postdoc-level, career-defining
- Period estimates: time assuming techniques already mastered (note: actual time 2-3x with learning)
- {sim_note}
- IMPORTANT: Keep each hypothesis field CONCISE (2-3 sentences max per field) to ensure ALL 7 hypotheses fit within the response. Completeness of all 7 hypotheses is more important than length of each.
- {cost_note}
- STRICTLY FOLLOW the 3 mandatory rules defined in the system prompt (metrics+baseline, fallback plan, no naive A+B integration)

Return this exact JSON structure:
{{
  "lab_name": "...",
  "field": "...",
  "lab_overview": "2-3 sentence overview of what the lab does",
  "assigned_project": "{assigned_project}",
  "intro_for_undergrad": {{
    "what_is_research": "2 sentences max: what is academic research? Plain language for a 3rd-year undergrad.",
    "what_does_lab_do": "2 sentences max: what does THIS lab study and what big questions does it try to answer? No jargon.",
    "why_important": "2 sentences max: why does this research matter to society or daily life? Concrete and relatable.",
    "how_they_study": [
      {{"method": "method name", "plain_explanation": "1 sentence only: what this method does in plain language."}}
    ]
  }},
  "projects": [
    {{"id": 1, "name": "...", "description": "...", "related_papers": ["..."]}}
  ],
  "lab_capabilities": {{
    "techniques": [
      {{"name": "...", "description": "one-sentence plain-language explanation of what this IS", "lab_status": "what the lab has built/done with it"}}
    ],
    "equipment_or_models": [
      {{"name": "...", "description": "one-sentence plain-language explanation", "notes": "lab-specific notes"}}
    ]
  }},
  "paper_summaries": [
    {{"filename": "...", "title": "...", "method_tag": "...", "summary": "1 sentence", "key_finding": "1 sentence", "limitation": "1 sentence"}}
  ],
  "hypotheses": [
    {{
      "id": "H1",
      "name": "short hypothesis name",
      "project_id": 1,
      "feasibility": "Easy & Fast",
      "period": "{period_example}",
      "impact_stars": "★★★☆☆",
      "impact_desc": "{impact_desc_example}",
      "statement": "Falsifiable hypothesis: specific claim + expected direction of change. 2 sentences max.",
      "novelty": "1-2 sentences: the NEW algorithmic/theoretical contribution. Why NOT a simple A+B integration.",
      "rationale": "1-2 sentences: research gap from specific papers.",
      "evaluation_metrics": [
        {{"metric": "metric name", "target": "concrete target value", "measurement_method": "brief method"}}
      ],
      "baseline": "Cite a specific paper + its reported metric value. E.g., 'ANYmal (RSS 2023): 12% slip rate on 20° slope'.",
      "resources": "Key equipment or tools only.",
      "control_loop_design": "If real-time control is involved: specify frequency split (e.g., 'VLM @ 1Hz async / RL controller @ 500Hz'). Write 'N/A' if not applicable.",
      "fallback_plan": "1-2 sentences: minimum viable contribution if main experiment fails, including cross-platform validation plan (e.g., Unitree Go1 sim). Target venue."
    }}
  ],
  "costs": [
    {{"item": "...", "category": "Low/Medium/High", {cost_field}: "...", "note": "..."}}
  ]
}}"""


# ─────────────────────────────────────────────────────────────
# STAGE 2B — Checklist / Background / Roadmap (separate call)
# ─────────────────────────────────────────────────────────────

STAGE_2B_SYSTEM = """You are a research mentor helping a Korean graduate student prepare for their first research project.
Write ALL content in Korean (한국어) except technical terms, model names, metric names, and venue names.
Return ONLY valid JSON with no markdown fences, no explanation."""

STAGE_2B_SYSTEM_EN = """You are a research mentor helping a graduate student prepare for their first research project.
Write ALL content in English.
Return ONLY valid JSON with no markdown fences, no explanation."""


def build_stage2b_prompt(hypotheses_summary: str, detected_field: str, assigned_project: str,
                         language: str = "ko") -> str:
    if language == "en":
        student_desc = "a graduate student"
        hardware_note = """HARDWARE_NOTE: If the field involves physical hardware (robotics, mechanical systems, lab equipment, sensors, etc.), the checklist MUST include items like:
- Confirm with senior lab members or the PI whether the robots/equipment/sensors from the papers still exist in the lab
- Check whether upgrades, replacements, or aging hardware require modifications to the experimental methods
- Verify whether missing sensors/components can be replaced with a simulator (e.g., Isaac Gym, Gazebo, MuJoCo)
- Confirm budget and lead time for consumables/parts needed for experiments"""
        checklist_example = '"Action item 1", "Action item 2"'
        concept_example = '{"concept": "concept name", "description": "one-line explanation", "why_needed": "which hypothesis requires this"}'
        journal_example = '{"name": "journal name", "field": "field", "why": "reason"}'
        roadmap_example = '[{"period": "Month 1", "tasks": ["Task 1", "Task 2"]}, {"period": "Month 2", "tasks": ["Task 1", "Task 2"]}, {"period": "Month 3", "tasks": ["Task 1", "Task 2"]}]'
    else:
        student_desc = "a Korean graduate student"
        hardware_note = """HARDWARE_NOTE: If the field involves physical hardware (robotics, mechanical systems, lab equipment, sensors, etc.), the checklist MUST include items like:
- 논문에 등장한 로봇/장비/센서가 현재 랩에 그대로 존재하는지 선배 또는 교수님께 직접 확인
- 장비가 업그레이드·교체·노후화로 달라졌을 경우 실험 방법 수정 필요 여부 확인
- 특정 센서나 부품이 다른 로봇에 이전돼 사용 불가능한 경우 시뮬레이터(예: Isaac Gym, Gazebo, MuJoCo)로 대체 가능한지 확인
- 실험에 필요한 소모품·부품 구매 예산 및 리드타임 확인"""
        checklist_example = '"확인 사항 1 (한국어로 작성)", "확인 사항 2"'
        concept_example = '{"concept": "개념명", "description": "한 줄 한국어 설명", "why_needed": "어떤 가설에 필요한지"}'
        journal_example = '{"name": "저널명", "field": "분야", "why": "이유 (한국어)"}'
        roadmap_example = '[{"period": "1개월차", "tasks": ["할 일 1 (한국어)", "할 일 2"]}, {"period": "2개월차", "tasks": ["할 일 1", "할 일 2"]}, {"period": "3개월차", "tasks": ["할 일 1", "할 일 2"]}]'

    return f"""Based on the following hypothesis list for {student_desc}, generate supporting study materials.

Field: {detected_field}
Assigned project: {assigned_project or 'None (general lab research)'}

Hypotheses summary:
{hypotheses_summary}

{hardware_note}

Return ONLY valid JSON (no markdown fences):
{{
  "checklist": [{checklist_example}],
  "background_knowledge": {{
    "core_concepts": [{concept_example}],
    "search_keywords": ["keyword1", "keyword2"],
    "recommended_journals": [{journal_example}]
  }},
  "roadmap": {roadmap_example}
}}

IMPORTANT: You MUST populate ALL three sections (checklist, background_knowledge, roadmap) with real content.
- checklist: minimum 8 items
- core_concepts: minimum 5 concepts
- search_keywords: minimum 8 keywords
- recommended_journals: minimum 3 journals
- roadmap: exactly 3 months, each with at least 3 tasks"""
