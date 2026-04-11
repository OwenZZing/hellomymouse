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
- WEIGHT BY PAPER COUNT: If only 1 paper covers a topic while 5+ papers cover another, the single-paper topic is likely a minor/collaborative/one-off contribution, NOT a main lab project. Mark it as a secondary theme or merge it into a broader project. Do NOT treat a single paper as equal weight to a well-established research line.

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

EXTRACTION HINTS:
- `equipment_details`: Search Methods/Materials for reagents, antibodies, instruments with their manufacturer and catalog numbers (commonly written as "from Sigma-Aldrich (Cat# XXXX)", "Leica SP8 confocal microscope", "anti-GFP antibody (Abcam, ab32572)"). If the paper doesn't list a manufacturer or catalog, use empty strings — DO NOT invent.
- `software_and_tools`: Search Methods (and sometimes Results/figure captions) for software names. Common phrasings: "analyzed using GraphPad Prism 9.0", "simulated in MATLAB R2022b / Simulink", "implemented in PyTorch", "processed with ImageJ", "statistical analysis in R (v4.2)", "ANSYS Workbench", "Gaussian 16", "ROOT 6.24". Include libraries/frameworks (PyTorch, HuggingFace, scipy), stats software (Prism, SPSS, R, SAS), simulation tools (MATLAB, Simulink, Isaac Sim, MuJoCo, ANSYS, OpenFOAM, Gaussian, VASP), image/data analysis tools (ImageJ/Fiji, Origin), and CAD/design tools (SolidWorks). Capture the version if stated. If the paper doesn't mention any software explicitly, return an empty array — DO NOT invent.

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
  "equipment_details": [
    {{"name": "equipment/reagent/model name", "manufacturer": "company name if stated in paper (e.g., Sigma-Aldrich, Thermo Fisher, Zeiss) — empty string if not mentioned", "catalog_number": "catalog/part number if stated (e.g., Cat# A12379, #ab32572) — empty string if not mentioned", "purpose": "1-phrase what it's used for in this paper"}}
  ],
  "software_and_tools": [
    {{"name": "software/library name as stated in the paper (e.g., GraphPad Prism, MATLAB, PyTorch, ImageJ, ROOT, ANSYS, R, Python)", "version": "version string if stated (e.g., '9.0', 'R2022b') — empty string if not mentioned", "purpose": "1-phrase what it was used for in this paper (e.g., 'two-way ANOVA', 'PPO training', 'FEM simulation')"}}
  ],
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

=== JARGON ACCESSIBILITY RULE (MANDATORY) ===
When a domain-specific term (jargon) appears for the FIRST TIME in any descriptive text, you MUST add a short plain-language explanation in parentheses.
Example: "아티팩트(영상에 나타나는 인위적 왜곡/노이즈)", "팬텀(실제 인체를 대신하여 실험에 사용하는 모형)"
This applies to ALL sections: overview, summaries, hypotheses, background knowledge, etc.
Do NOT assume the reader knows field-specific vocabulary. The target reader may be a senior undergraduate who has never encountered these terms.

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

RULE 7 — REALISTIC TIMELINE ESTIMATES.
Period estimates MUST account for the student's learning curve, NOT assume full mastery.
  - For beginner students (학부 졸업, 분야 처음): multiply base estimate by 2-3x and explicitly note what skills need to be learned first (e.g., "딥러닝 프레임워크 학습 1-2개월 선행 필요").
  - For intermediate students (관련 수업 수강): multiply by 1.5x.
  - For advanced students (석사 이상, 연구 경험): base estimate is appropriate.
"""

STAGE_2_SYSTEM_EN = """You are an expert research mentor helping a new graduate student find their first research hypothesis.

=== LANGUAGE RULE (MANDATORY) ===
Write ALL content in English.

Your goal: generate practical, feasible hypotheses grounded in the lab's existing work.
Philosophy: each paper has a limitation — the student only needs to take ONE step forward.
Return ONLY valid JSON with no markdown fences.

=== JARGON ACCESSIBILITY RULE (MANDATORY) ===
When a domain-specific term (jargon) appears for the FIRST TIME in any descriptive text, you MUST add a short plain-language explanation in parentheses.
Example: "artifact (unwanted distortion/noise in images)", "phantom (a physical model used in place of a human body for testing)"
This applies to ALL sections: overview, summaries, hypotheses, background knowledge, etc.
Do NOT assume the reader knows field-specific vocabulary. The target reader may be a senior undergraduate who has never encountered these terms.

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

RULE 7 — REALISTIC TIMELINE ESTIMATES.
Period estimates MUST account for the student's learning curve, NOT assume full mastery.
  - For beginner students (fresh undergrad, new to the field): multiply base estimate by 2-3x and explicitly note what skills need to be learned first (e.g., "1-2 months of deep learning framework study required first").
  - For intermediate students (relevant coursework taken): multiply by 1.5x.
  - For advanced students (master's+, research experience): base estimate is appropriate.
"""


def build_stage2_prompt(paper_analyses: list[dict], assigned_project: str,
                        professor_instructions: str, detected_field: str,
                        language: str = "ko", student_level: str = "beginner") -> str:
    analyses_json = json.dumps(paper_analyses, ensure_ascii=False, indent=2)
    assigned_note = f'The student has been assigned to work on: "{assigned_project}"' if assigned_project else 'No specific project has been assigned yet.'
    prof_note = f'\nProfessor\'s additional instructions: {professor_instructions}' if professor_instructions else ''
    field_note = f'Primary research field detected: {detected_field}'

    # Output-budget guardrail: with many papers, paper_summaries alone can
    # balloon the response and cause JSON truncation. Sonnet now gets 64K
    # output headroom, so this only kicks in for extreme runs (15+ papers).
    paper_count = len(paper_analyses)
    if paper_count >= 15:
        budget_warning = (
            f"\n\n=== OUTPUT BUDGET CRITICAL ({paper_count} papers) ===\n"
            "The response token budget is TIGHT. Truncated JSON = total failure.\n"
            "HARD LIMITS for this run:\n"
            "- paper_summaries: each of summary / key_finding / limitation = ONE short sentence (max 20 words).\n"
            "- hypotheses: statement / novelty / rationale / fallback_plan = 1 short sentence each, no filler.\n"
            "- intro_for_undergrad fields: 1 sentence each; how_they_study: at most 3 methods.\n"
            "- lab_capabilities.techniques / equipment_or_models: at most 4 items each.\n"
            "- costs: at most 5 items.\n"
            "- lab_overview: 2 sentences max.\n"
            "COMPLETENESS of the full JSON structure (all 7 hypotheses, all required fields closed, all brackets balanced) is FAR MORE IMPORTANT than prose detail. "
            "If you feel you are running out of budget, cut prose — never leave a field incomplete. "
            "Return ONLY the JSON object with NO preamble text, NO markdown fences, NO trailing commentary."
        )
    else:
        budget_warning = ""

    level_map = {
        "beginner": "a complete beginner (senior undergrad, first time in this research field, no prior research experience). Explain ALL jargon. Timeline estimates must include learning overhead (2-3x base).",
        "intermediate": "an intermediate student (has taken relevant coursework but limited research experience). Explain uncommon jargon. Timeline estimates should be 1.5x base.",
        "advanced": "an advanced student (master's level or above, has research experience in a related field). Jargon explanation optional. Base timeline estimates are fine.",
    }
    level_note = f'Student background level: {level_map.get(student_level, level_map["beginner"])}'

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
{level_note}{budget_warning}

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
- EQUIPMENT EXTRACTION: For `lab_capabilities.equipment_or_models`, directly reuse the `equipment_details` arrays from each paper analysis. Preserve the `manufacturer` and `catalog_number` fields EXACTLY as reported in the source papers — do NOT invent company names or catalog numbers. If a paper didn't mention a manufacturer or catalog, leave those fields as empty strings. Deduplicate entries that refer to the same product across multiple papers by merging them into a single row (keep the most complete manufacturer/catalog info). New grad students rely on these fields for lab inventory management, so accuracy and completeness are more important than prose.

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
      {{"name": "...", "manufacturer": "company name if any paper stated it (e.g., Sigma-Aldrich, Thermo Fisher, Zeiss). Empty string if unknown.", "catalog_number": "catalog/part number if any paper stated it (e.g., Cat# A12379). Empty string if unknown.", "description": "one-sentence plain-language explanation", "notes": "lab-specific notes, or a purpose/use hint. Mention which paper(s) cited this equipment if relevant."}}
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
When a domain-specific term appears for the first time, add a short plain-language explanation in parentheses.
Return ONLY valid JSON with no markdown fences, no explanation."""

STAGE_2B_SYSTEM_EN = """You are a research mentor helping a graduate student prepare for their first research project.
Write ALL content in English.
When a domain-specific term appears for the first time, add a short plain-language explanation in parentheses.
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


# ─────────────────────────────────────────────────────────────
# STAGE 2C — Starter tasks (undergraduate-level warmup)
# ─────────────────────────────────────────────────────────────

STAGE_2C_SYSTEM = """You are a research mentor helping a Korean undergraduate student (or a brand-new research intern) take their very first steps toward research.

Your job: generate 4-6 "Starter Tasks" — doable warmup activities that a student with NO research experience can realistically complete ALONE, using free/public resources. These are stepping stones toward the full research hypotheses, NOT the hypotheses themselves.

=== LANGUAGE RULE ===
Write ALL descriptive content in Korean (한국어).
Only these may remain in English: dataset names, library names, technique names, model names, paper titles, URLs, and variable names.
When a domain-specific term appears for the first time, add a short plain-language explanation in parentheses.
Assume the reader has never taken a research methods class and doesn't know what "baseline", "hypothesis", or "ablation" means.

=== STARTER TASK RULES (MANDATORY) ===

RULE 1 — ZERO-INFRASTRUCTURE START.
Tasks must be doable with a personal laptop and free online tools. NO lab equipment, NO advisor supervision, NO paid APIs, NO institutional access required (except arXiv, which is free).
At least 2 of the tasks must use PUBLIC datasets the student can download TODAY.

RULE 2 — CITE SPECIFIC PUBLIC RESOURCES.
"Use a public dataset" is BANNED. Every public_data task MUST name a specific dataset with a URL. Examples by field:
- Neuroscience: Allen Brain Atlas, NeuroMorpho.Org, OpenNeuro, HCP (Human Connectome Project)
- ML/CV: ImageNet (subset), CIFAR-10, COCO, HuggingFace Datasets Hub
- Robotics: D4RL, RoboMimic, ROS bag repositories, Isaac Gym tutorials
- Bioinformatics: NCBI GEO, ENCODE, TCGA, UniProt, PhysioNet
- General ML: Kaggle, UCI ML Repository, Papers with Code
Pick datasets that match the LAB's actual field (from the paper analyses).

RULE 3 — JARGON-FREE WHAT-TO-DO.
The `what_to_do` field must read like a recipe for a first-year undergrad. If you use a term like "convolutional neural network" or "ablation study", IMMEDIATELY follow it with a parenthetical plain-language explanation ("합성곱 신경망 — 이미지를 작은 조각으로 나눠 학습하는 모델").

RULE 4 — CONCRETE DELIVERABLE.
Every task must produce something the student can SHOW their advisor. Examples:
- "Jupyter 노트북 1개 + 결과 그래프 3개"
- "1쪽짜리 기법 요약 문서 (PDF)"
- "5편 논문 표 형식 정리 (Notion 또는 Word)"
Vague deliverables like "이해하기" or "공부하기" are BANNED.

RULE 5 — REALISTIC HOURS FOR BEGINNERS.
Include learning overhead. If installing Python + running first notebook takes a beginner 5 hours, count it. Typical range: 8~30 hours per task.

RULE 6 — BRIDGE TO HYPOTHESES.
Every task's `leads_to` field must explicitly name which hypothesis (H1~H7) this prepares the student for, and HOW (e.g., "H3의 baseline 재현 실습이 됩니다").

RULE 7 — CATEGORY COVERAGE.
Use at least 3 different categories from: public_data, technique_study, data_analysis, literature_review.
At least 2 tasks must be `public_data` (lowest entry barrier — student can start immediately).

RULE 8 — LAB-SPECIFIC TOOL STARTER TASK (DATA-DRIVEN).
The "Software/tools cited in the lab's papers (frequency-ranked)" line in the lab context is the AUTHORITATIVE source — it was extracted directly from each paper's Methods section. You MUST include at least ONE starter task that teaches the student the basics of the MOST FREQUENTLY cited software from that list (or one of the top 3, if they serve different purposes — e.g., a stats tool + a simulation tool).

How to apply:
  1. Read the frequency-ranked software list in the lab context.
  2. Pick the top 1~2 tools the student will realistically touch on day one (stats/plotting tools, simulation frameworks, ML frameworks, imaging tools — whatever dominates).
  3. Create a concrete technique_study task: "install [tool] + follow [specific official tutorial] + produce [deliverable]". Name the actual tutorial if you know one (e.g., "PyTorch 공식 60-min blitz", "GraphPad Prism basic t-test tutorial", "MATLAB Onramp", "Isaac Sim tutorial — load a robot scene").
  4. Skip tools the student almost certainly already knows (Python, git, Microsoft Word). Focus on the field-specific ones.
  5. If the same tool is cited with a clear purpose (e.g., "MATLAB — FEM simulation", "Prism — two-way ANOVA"), use that purpose to anchor the task.

FALLBACK (only if the software list is empty or "(no software explicitly mentioned in any paper)"):
  - Default to Python + NumPy + Matplotlib + pandas + Jupyter. It works for every quantitative field and never misfires the way a field-specific tool would.
  - Do NOT guess field-specific tools from the detected field alone — if the papers didn't name them, neither should you.

CRITICAL: Never recommend a tool that contradicts the lab's actual stack. If the lab uses MATLAB/ANSYS, don't recommend GraphPad Prism. If the lab uses Prism/ImageJ, don't recommend ROS2. Match reality, not a field stereotype.

Return ONLY valid JSON with no markdown fences, no explanation."""

STAGE_2C_SYSTEM_EN = """You are a research mentor helping an undergraduate student (or brand-new research intern) take their very first steps toward research.

Your job: generate 4-6 "Starter Tasks" — doable warmup activities that a student with NO research experience can realistically complete ALONE, using free/public resources. These are stepping stones toward the full research hypotheses, NOT the hypotheses themselves.

Write ALL content in English. When a domain-specific term appears for the first time, add a short plain-language explanation in parentheses.

=== STARTER TASK RULES ===
1. ZERO-INFRASTRUCTURE START — personal laptop + free online tools only. At least 2 tasks must use PUBLIC datasets downloadable today.
2. CITE SPECIFIC RESOURCES — every public_data task must name a specific dataset with URL (Kaggle, UCI ML, HuggingFace, Allen Brain Atlas, ENCODE, etc.), matched to the lab's field.
3. JARGON-FREE what_to_do — explain every technical term inline in parentheses.
4. CONCRETE DELIVERABLE — must produce something showable (notebook, PDF summary, table). "Understand X" is banned.
5. REALISTIC HOURS — include learning overhead (typical: 8-30 hours).
6. BRIDGE TO HYPOTHESES — leads_to must name which H1~H7 this prepares for, and how.
7. CATEGORY COVERAGE — use at least 3 categories: public_data, technique_study, data_analysis, literature_review. At least 2 must be public_data.
8. LAB-SPECIFIC TOOL TASK (DATA-DRIVEN) — include AT LEAST ONE task that teaches the MOST FREQUENTLY cited software from the lab context's "Software/tools cited in the lab's papers (frequency-ranked)" line. That list was extracted directly from each paper's Methods section and is authoritative. Pick the top 1~2 tools the student will realistically use on day one, name a specific official tutorial, and produce a concrete deliverable. Skip tools the student already knows (Python, git, Word). If the software list is empty, fall back to Python + NumPy + Matplotlib + pandas + Jupyter. NEVER guess field-specific tools (Prism, MATLAB, ROS) from the detected field alone — if the papers didn't name them, don't recommend them.

Return ONLY valid JSON."""


def _summarize_lab_context(paper_analyses: list[dict]) -> str:
    """Extract lab techniques, key terms, and actual software/tools used
    (aggregated from each paper's Methods) for grounding Stage 2C."""
    techniques: list[str] = []
    seen_tech: set[str] = set()
    key_terms: list[str] = []
    seen_term: set[str] = set()
    paper_types: dict[str, int] = {}
    # Software: count frequency across papers (case-insensitive key) and
    # remember one canonical name + purpose example per tool.
    sw_count: dict[str, int] = {}
    sw_display: dict[str, str] = {}
    sw_purpose: dict[str, str] = {}

    for p in paper_analyses:
        for t in p.get('techniques', []) or []:
            if t and t not in seen_tech:
                seen_tech.add(t)
                techniques.append(t)
        for k in p.get('key_terms', []) or []:
            if k and k not in seen_term:
                seen_term.add(k)
                key_terms.append(k)
        pt = (p.get('paper_type') or '').strip().lower().split()[0] if p.get('paper_type') else ''
        if pt:
            paper_types[pt] = paper_types.get(pt, 0) + 1
        for sw in p.get('software_and_tools', []) or []:
            name = (sw.get('name') or '').strip()
            if not name:
                continue
            key = name.lower()
            sw_count[key] = sw_count.get(key, 0) + 1
            if key not in sw_display:
                sw_display[key] = name
                sw_purpose[key] = (sw.get('purpose') or '').strip()

    # Sort by frequency desc, then by first-seen order.
    ranked = sorted(sw_count.items(), key=lambda kv: (-kv[1], kv[0]))
    software_lines = []
    for key, cnt in ranked[:15]:
        display = sw_display[key]
        purpose = sw_purpose[key]
        suffix = f" — {purpose}" if purpose else ''
        software_lines.append(f"{display} (×{cnt}){suffix}")
    software_str = '; '.join(software_lines) if software_lines else '(no software explicitly mentioned in any paper)'

    return (
        f"- Core techniques used by the lab: {', '.join(techniques[:20]) or '(none detected)'}\n"
        f"- Key domain terms: {', '.join(key_terms[:25]) or '(none detected)'}\n"
        f"- Paper type distribution: {', '.join(f'{k}×{v}' for k, v in paper_types.items()) or '(unknown)'}\n"
        f"- Software/tools cited in the lab's papers (frequency-ranked): {software_str}"
    )


def build_stage2c_prompt(paper_analyses: list[dict], hypotheses_summary: str,
                         detected_field: str, assigned_project: str,
                         language: str = "ko") -> str:
    lab_context = _summarize_lab_context(paper_analyses)
    assigned_note = assigned_project or 'General lab research (no specific assignment)'

    if language == "en":
        task_example = (
            '{\n'
            '      "id": "S1",\n'
            '      "name": "concrete task name",\n'
            '      "category": "public_data | technique_study | data_analysis | literature_review",\n'
            '      "difficulty": "undergrad sophomore+ / junior+ / senior+",\n'
            '      "estimated_hours": "10-15 hours (including setup)",\n'
            '      "what_to_do": "1-2 sentences — concrete steps, explain jargon in parentheses",\n'
            '      "why_it_helps": "1 sentence — why this prepares for the hypotheses",\n'
            '      "resources": ["specific dataset name + URL", "tutorial name + URL"],\n'
            '      "deliverable": "what the student shows the advisor when done",\n'
            '      "leads_to": "H? — one line: how this task bridges to that hypothesis"\n'
            '    }'
        )
    else:
        task_example = (
            '{\n'
            '      "id": "S1",\n'
            '      "name": "구체적 과제명 (한국어)",\n'
            '      "category": "public_data | technique_study | data_analysis | literature_review",\n'
            '      "difficulty": "학부 2~3학년 가능 / 4학년 가능 등",\n'
            '      "estimated_hours": "10~15시간 (환경 설치 포함)",\n'
            '      "what_to_do": "1~2문장: 구체적 단계, jargon은 괄호로 쉽게 설명 (한국어)",\n'
            '      "why_it_helps": "1문장: 이 과제가 왜 아래 가설 준비에 도움 되는지",\n'
            '      "resources": ["구체적 데이터셋/튜토리얼 이름 + URL"],\n'
            '      "deliverable": "끝나면 손에 남는 것 (예: Jupyter 노트북 + 1쪽 요약 PDF)",\n'
            '      "leads_to": "H? — 한 줄: 이 과제가 해당 가설과 어떻게 연결되는지"\n'
            '    }'
        )

    return f"""Lab context (use this to pick grounded, field-appropriate starter tasks):
- Primary field: {detected_field}
- Assigned project: {assigned_note}
{lab_context}

The full research hypotheses (the DESTINATION these starter tasks must bridge toward):
{hypotheses_summary}

Generate 4-6 starter tasks for an undergraduate or brand-new research intern. Remember: these tasks are the DIDIMDOL (stepping stones), NOT research itself. Aim for "doable in a few weekends alone with a laptop".

Return ONLY valid JSON (no markdown fences):
{{
  "starter_tasks": [
    {task_example}
  ]
}}

HARD REQUIREMENTS:
- Exactly 4-6 tasks.
- At least 2 tasks with category "public_data" that cite a specific downloadable dataset (name + URL).
- At least 3 distinct categories across all tasks.
- Every task's `leads_to` must name a specific hypothesis id (H1, H2, ..., H7).
- Every task's `resources` must include at least one specific named resource (dataset, tutorial, paper, library) — no generic "Google it"."""
