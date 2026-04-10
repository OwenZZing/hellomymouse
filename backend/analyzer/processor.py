"""Analysis pipeline: Stage 0, Stage 1, Stage 2."""
from __future__ import annotations
import json
import re
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from parser.pdf_reader import extract_title_abstract, extract_full_text
from parser.section_splitter import split_sections, get_key_sections
from analyzer.api_client import APIClient
from analyzer.prompts import (
    STAGE_0_SYSTEM, build_stage0_prompt,
    STAGE_1_SYSTEM, build_stage1_prompt,
    STAGE_2_SYSTEM, STAGE_2_SYSTEM_EN, build_stage2_prompt,
    STAGE_2B_SYSTEM, STAGE_2B_SYSTEM_EN, build_stage2b_prompt,
    STAGE_2C_SYSTEM, STAGE_2C_SYSTEM_EN, build_stage2c_prompt,
)

ProgressCallback = Callable[[str, int], None]


def _recover_truncated_json(text: str) -> dict:
    """Recover a truncated/malformed JSON object by backtracking to the last
    safe cut point and closing open brackets.

    A "safe cut point" is a position where we can chop the string and still
    produce valid JSON by appending closing brackets:
      - Right after a closing `}` or `]` (at any depth)
      - Right BEFORE a `,` at depth >= 1 (drops the incomplete key/value
        that was being written when truncation happened)

    Snapshots the stack state at each safe cut point, then tries them in
    reverse order (latest first) until json.loads succeeds.
    """
    # Collect (cut_pos_exclusive, stack_at_that_point) for every safe cut.
    snapshots: list[tuple[int, list[str]]] = []
    stack: list[str] = []
    in_string = False
    escape = False

    for i, c in enumerate(text):
        if escape:
            escape = False
            continue
        if in_string:
            if c == '\\':
                escape = True
            elif c == '"':
                in_string = False
            continue
        # not in string
        if c == '"':
            in_string = True
        elif c == '{' or c == '[':
            stack.append(c)
            # Snapshot right after opening: allows cutting to an empty
            # container if nothing valid comes after (extreme truncation).
            snapshots.append((i + 1, list(stack)))
        elif c == '}' or c == ']':
            if stack:
                stack.pop()
            snapshots.append((i + 1, list(stack)))
        elif c == ',' and stack:
            # Cut just before the comma — drops the partial element after it.
            snapshots.append((i, list(stack)))

    # Also try the full text as-is (in case it was actually valid).
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try each snapshot in reverse (prefer the longest recoverable prefix).
    for cut_pos, snap_stack in reversed(snapshots):
        candidate = text[:cut_pos]
        for opener in reversed(snap_stack):
            candidate += '}' if opener == '{' else ']'
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise json.JSONDecodeError('Could not recover truncated JSON', text[:200], 0)


def _parse_json_response(text: str) -> dict:
    """Robustly parse a possibly-noisy LLM JSON response.

    Handles, in order:
      1. Markdown fences (```json ... ```).
      2. Preamble/trailing text (e.g. "Here's the JSON: {...} done!").
      3. Preambles that themselves contain `{` characters — tries each
         `{` position in the text as a candidate JSON start.
      4. Truncation (mid-string, mid-value) via _recover_truncated_json
         backtracking to the last safe cut point.
    """
    if not text:
        raise json.JSONDecodeError('Empty response', '', 0)

    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()

    # Fast path: entire text is already valid JSON.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    brace_positions = [i for i, c in enumerate(text) if c == '{']
    if not brace_positions:
        raise json.JSONDecodeError('No JSON object found', text[:200], 0)

    # Step 1: Try the FIRST `{` position. This is almost always the real
    # JSON start. Try raw_decode first (handles trailing text), then
    # truncation recovery (handles mid-value cuts). Doing this before
    # trying later `{` positions prevents returning an inner nested
    # object when the outer object is merely truncated.
    first_pos = brace_positions[0]
    first_candidate = text[first_pos:]
    try:
        obj, _end = decoder.raw_decode(first_candidate)
        if isinstance(obj, dict) and obj:
            return obj
    except json.JSONDecodeError:
        pass
    try:
        recovered = _recover_truncated_json(first_candidate)
        if recovered:  # non-empty: trust it
            return recovered
    except (json.JSONDecodeError, ValueError):
        pass

    # Step 2: The first `{` was probably preamble junk (e.g. "{ literal }"
    # in prose). Try later `{` positions with raw_decode. This correctly
    # finds the real JSON when it comes after a brace-containing preamble.
    for pos in brace_positions[1:]:
        candidate = text[pos:]
        try:
            obj, _end = decoder.raw_decode(candidate)
            if isinstance(obj, dict) and obj:
                return obj
        except json.JSONDecodeError:
            continue

    # Step 3: Absolute last resort — accept an empty dict from recovery
    # so callers don't crash (they can still try again, and the .get()
    # pattern won't KeyError).
    try:
        return _recover_truncated_json(first_candidate)
    except (json.JSONDecodeError, ValueError):
        pass

    raise json.JSONDecodeError('Could not parse JSON response', text[:200], 0)


class AnalysisPipeline:
    def __init__(self, api_client: APIClient, progress_callback: ProgressCallback | None = None):
        self.api = api_client
        self._cb = progress_callback or (lambda msg, pct: None)

    def _progress(self, msg: str, pct: int):
        self._cb(msg, pct)

    def _log_parse_failure(self, tag: str, response: str, err: Exception):
        """Write the failing response + error to a debug log for diagnosis."""
        try:
            _log_path = os.path.join(os.path.expanduser('~'), 'HypothesisMaker_debug.log')
            resp_len = len(response) if response else 0
            head = (response or '')[:1500]
            tail = (response or '')[-1500:] if resp_len > 3000 else ''
            with open(_log_path, 'a', encoding='utf-8') as f:
                f.write(f'\n========== [{tag}] PARSE FAILURE ==========\n')
                f.write(f'provider={self.api.provider} model={self.api.model}\n')
                f.write(f'response_length={resp_len}\n')
                f.write(f'error={err}\n')
                f.write(f'--- response head (first 1500 chars) ---\n{head}\n')
                if tail:
                    f.write(f'--- response tail (last 1500 chars) ---\n{tail}\n')
                f.write('========== END ==========\n')
        except Exception:
            pass  # Never let logging kill the pipeline

    def _format_parse_failure_message(self) -> str:
        """User-facing message for Stage 2 parse failure — suggest alternative
        models that exclude the one the user is already on."""
        provider = (self.api.provider or '').lower()
        model = (self.api.model or '').lower()

        # Build an alternatives list that excludes the current provider/model
        alternatives: list[str] = []
        if provider != 'claude' or 'opus' not in model:
            alternatives.append('Claude Opus')
        if provider != 'claude' or 'sonnet' not in model:
            alternatives.append('Claude Sonnet')
        if provider != 'openai':
            alternatives.append('GPT-4o')
        if provider != 'gemini':
            alternatives.append('Gemini 2.5 Pro')

        alt_str = ' / '.join(alternatives[:3]) if alternatives else '다른 모델'
        return (
            'AI가 올바른 JSON 형식으로 응답하지 않았습니다. '
            f'논문 수를 줄이거나 다른 모델({alt_str})을 사용해보세요.'
        )

    def _with_keepalive(self, start_pct: int, end_pct: int,
                        msgs: list[str], fn: Callable):
        """Run fn() with a background thread that slowly advances the progress
        bar so the frontend doesn't appear frozen during long blocking calls.
        Critical for Stage 2 — especially the retry path, which previously
        had no keepalive and appeared stuck at 72% for minutes."""
        _stop = threading.Event()

        def _keepalive():
            pct = start_pct
            while not _stop.is_set() and pct < end_pct:
                time.sleep(10)
                if not _stop.is_set():
                    idx = min((pct - start_pct) // 5, len(msgs) - 1)
                    self._progress(msgs[idx], pct)
                    pct += 1

        threading.Thread(target=_keepalive, daemon=True).start()
        try:
            return fn()
        finally:
            _stop.set()

    # ──────────────────────────────────────────────
    # Stage 0: Fast project scan
    # ──────────────────────────────────────────────
    def run_stage0(self, pdf_paths: list[str]) -> dict:
        """Extract title+abstract from all PDFs, detect projects."""
        self._progress('Stage 0: 논문 제목/초록 추출 중...', 5)

        title_abstracts = []
        for i, path in enumerate(pdf_paths):
            try:
                data = extract_title_abstract(path)
                title_abstracts.append(data)
                pct = 5 + int((i + 1) / len(pdf_paths) * 20)
                self._progress(f'  읽는 중: {os.path.basename(path)}', pct)
            except Exception as e:
                self._progress(f'  ⚠ 파싱 실패: {os.path.basename(path)} — {e}', 5)

        if not title_abstracts:
            raise RuntimeError('읽을 수 있는 PDF가 없습니다.')

        self._progress('Stage 0: AI 프로젝트 분석 중...', 25)

        # Gemini: File API로 PDF 직접 전송 (텍스트 payload 과부하 방지)
        if self.api.provider == 'gemini':
            try:
                self._progress('Stage 0: Gemini File API로 PDF 업로드 중...', 22)
                uploaded_files = self.api.upload_files_for_gemini(pdf_paths)
                filenames = [os.path.basename(p) for p in pdf_paths]
                prompt = (
                    f"아래 {len(pdf_paths)}편의 연구 논문 PDF를 분석해 연구실 프로젝트를 파악해주세요.\n"
                    f"파일 목록: {', '.join(filenames)}\n\n"
                    "각 논문의 제목과 초록을 읽고 연구 주제를 분류하세요."
                )
                response = self.api.call_with_files(prompt, STAGE_0_SYSTEM,
                                                    files=uploaded_files, max_tokens=2048)
            except Exception as e:
                # File API 실패 시 텍스트 방식으로 fallback
                self._progress(f'  File API 실패, 텍스트 방식으로 재시도 중... ({e})', 22)
                prompt = build_stage0_prompt(title_abstracts)
                response = self.api.call(prompt, STAGE_0_SYSTEM, max_tokens=2048)
        else:
            prompt = build_stage0_prompt(title_abstracts)
            response = self.api.call(prompt, STAGE_0_SYSTEM, max_tokens=2048)

        try:
            result = _parse_json_response(response)
        except json.JSONDecodeError:
            # Fallback: return single project
            result = {
                'lab_name_guess': 'Research Lab',
                'projects': [{'id': 1, 'name': 'General Lab Research', 'description': 'All lab projects', 'related_papers': [p['filename'] for p in title_abstracts]}]
            }

        result['_title_abstracts'] = title_abstracts
        self._progress('Stage 0 완료: 프로젝트 목록 파악됨', 30)
        return result

    # ──────────────────────────────────────────────
    # Stage 1: Per-paper deep analysis
    # ──────────────────────────────────────────────
    def _analyze_single_paper(self, path: str, project_context: str, is_reference: bool) -> dict | None:
        try:
            full_text = extract_full_text(path)
            sections = split_sections(full_text)
            key_text = get_key_sections(sections, max_chars=6000)

            # Get title from first extraction attempt
            ta = extract_title_abstract(path)
            title = ta['title']
            filename = os.path.basename(path)

            prompt = build_stage1_prompt(filename, title, key_text, project_context, is_reference)
            response = self.api.call(prompt, STAGE_1_SYSTEM, max_tokens=2048)
            return _parse_json_response(response)
        except Exception as e:
            return {
                'filename': os.path.basename(path),
                'title': os.path.basename(path),
                'is_reference': is_reference,
                'error': str(e),
                'field': 'unknown',
                'method_tag': '?',
                'techniques': [],
                'key_results': [],
                'limitations': [],
                'future_directions': [],
                'key_terms': [],
                'summary': f'[분석 실패: {e}]',
                'limitation_for_hypo': '',
            }

    def run_stage1(self, lab_pdf_paths: list[str], ref_pdf_paths: list[str],
                   assigned_project: str = '') -> list[dict]:
        """Analyze each paper concurrently."""
        total = len(lab_pdf_paths) + len(ref_pdf_paths)
        self._progress('Stage 1: 논문 심층 분석 시작...', 30)

        all_paths = [(p, False) for p in lab_pdf_paths] + [(p, True) for p in ref_pdf_paths]
        results = [None] * len(all_paths)
        completed = 0

        def analyze(idx_path_ref):
            idx, (path, is_ref) = idx_path_ref
            return idx, self._analyze_single_paper(path, assigned_project, is_ref)

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {executor.submit(analyze, (i, item)): i for i, item in enumerate(all_paths)}
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result
                completed += 1
                fname = os.path.basename(all_paths[idx][0])
                tag = '[참조]' if all_paths[idx][1] else ''
                pct = 30 + int(completed / total * 40)
                self._progress(f'  완료 {tag}: {fname}', pct)

        self._progress('Stage 1 완료', 70)
        return [r for r in results if r is not None]

    # ──────────────────────────────────────────────
    # Stage 2: Synthesis + report generation
    # ──────────────────────────────────────────────
    def run_stage2(self, paper_analyses: list[dict], assigned_project: str,
                   professor_instructions: str, language: str = "ko",
                   student_level: str = "beginner") -> dict:
        """Synthesize all analyses into final report data."""
        self._progress('Stage 2: 가설 및 리포트 생성 중... (1-3분 소요)', 70)

        stage2_msgs = [
            'AI가 논문들을 종합 분석 중...',
            'AI가 연구 가설을 설계 중...',
            'AI가 평가 지표와 Baseline 작성 중...',
            'AI가 리포트 구조를 완성 중...',
        ]

        # Detect dominant field
        fields = [p.get('field', '') for p in paper_analyses if p.get('field')]
        detected_field = max(set(fields), key=fields.count) if fields else 'STEM research'

        system2 = STAGE_2_SYSTEM_EN if language == "en" else STAGE_2_SYSTEM
        prompt = build_stage2_prompt(paper_analyses, assigned_project,
                                     professor_instructions, detected_field, language,
                                     student_level)
        # Request a large output budget; api_client clamps to per-model _MAX_TOKENS.
        # Sonnet-4.6: 64K, Opus-4.6: 32K, Haiku-4.5: 16K. Passing 64000 lets
        # Sonnet use its full headroom so 10+ papers don't truncate the JSON.
        stage2_max_tokens = 64000

        response = self._with_keepalive(
            71, 89, stage2_msgs,
            lambda: self.api.call(prompt, system2, max_tokens=stage2_max_tokens),
        )

        # Try parsing; if it fails, retry once with a stronger concision
        # directive. Retry also runs inside keepalive so progress keeps moving.
        result = None
        for attempt in range(2):
            try:
                result = _parse_json_response(response)
                break
            except (json.JSONDecodeError, ValueError) as parse_err:
                # Log the failing response so we can diagnose bad outputs.
                self._log_parse_failure(f'Stage2A attempt {attempt + 1}',
                                        response, parse_err)
                if attempt == 0:
                    self._progress('JSON 파싱 실패 — 자동 재시도 중...', 72)
                    retry_msgs = [
                        'AI가 응답을 다시 생성 중...',
                        '재시도: 가설 구조 재작성 중...',
                        '재시도: JSON 포맷 정리 중...',
                    ]
                    # Stronger retry: prepend a critical notice that forces
                    # JSON-only, terse output so the second attempt is more
                    # likely to produce parseable, non-truncated JSON.
                    retry_system = system2 + (
                        "\n\n=== CRITICAL RETRY NOTICE ===\n"
                        "Your previous response FAILED to parse as valid JSON. "
                        "This is your FINAL attempt. Obey these rules strictly:\n"
                        "1. Return ONLY the JSON object. Start with `{` and end with `}`.\n"
                        "2. NO preamble text, NO 'Here is the JSON', NO markdown fences, NO explanations.\n"
                        "3. Every field MUST be a SINGLE short sentence. No multi-paragraph prose.\n"
                        "4. COMPLETENESS of the JSON structure (every bracket closed, every field present) is more important than prose quality.\n"
                        "5. Escape all `\"` inside string values as `\\\"`. Do not use unescaped quotes inside strings.\n"
                        "6. Do not exceed 12000 output tokens. Compress aggressively if needed."
                    )
                    try:
                        response = self._with_keepalive(
                            73, 87, retry_msgs,
                            lambda: self.api.call(prompt, retry_system,
                                                  max_tokens=stage2_max_tokens),
                        )
                    except Exception as retry_err:
                        raise RuntimeError(f'재시도 중 API 오류: {retry_err}')
                else:
                    # Both attempts failed. Suggest model alternatives that
                    # exclude whatever the user is already on.
                    raise RuntimeError(self._format_parse_failure_message())

        self._progress('Stage 2A 완료 — 체크리스트·배경지식·로드맵 생성 중...', 88)

        # Build a compact hypothesis summary used by both 2B and 2C
        hypo_summary = '\n'.join(
            f"- {h.get('id','')}: {h.get('name','')} [{h.get('feasibility','')}]"
            for h in result.get('hypotheses', [])
        )

        # Stage 2B: checklist / background / roadmap (separate smaller call)
        try:
            self._progress('Stage 2B: 체크리스트·배경지식·로드맵 생성 중...', 89)
            system2b = STAGE_2B_SYSTEM_EN if language == "en" else STAGE_2B_SYSTEM
            prompt2b = build_stage2b_prompt(hypo_summary, detected_field, assigned_project, language)
            response2b = self.api.call(prompt2b, system2b, max_tokens=8192)
            result2b = _parse_json_response(response2b)
            checklist = result2b.get('checklist', [])
            bg = result2b.get('background_knowledge', {})
            roadmap = result2b.get('roadmap', [])
            result['checklist'] = checklist
            result['background_knowledge'] = bg
            result['roadmap'] = roadmap
            self._progress(
                f'Stage 2B 완료: 체크리스트 {len(checklist)}개, '
                f'개념 {len(bg.get("core_concepts", []))}개, '
                f'로드맵 {len(roadmap)}개월', 91
            )
        except Exception as e:
            import traceback, os
            _log_path = os.path.join(os.path.expanduser('~'), 'HypothesisMaker_debug.log')
            try:
                with open(_log_path, 'a', encoding='utf-8') as _f:
                    _f.write(f'[Stage2B ERROR] {e}\n{traceback.format_exc()}\n')
            except Exception:
                pass
            self._progress(f'  ⚠ Stage 2B 실패 — 로그 확인: {e}', 91)

        # Stage 2C: starter tasks (undergraduate-level warmup, grounded in lab context)
        try:
            self._progress('Stage 2C: 학부생용 워밍업 과제 생성 중...', 93)
            system2c = STAGE_2C_SYSTEM_EN if language == "en" else STAGE_2C_SYSTEM
            prompt2c = build_stage2c_prompt(paper_analyses, hypo_summary, detected_field,
                                            assigned_project, language)
            response2c = self.api.call(prompt2c, system2c, max_tokens=6000)
            result2c = _parse_json_response(response2c)
            starter_tasks = result2c.get('starter_tasks', [])
            result['starter_tasks'] = starter_tasks
            self._progress(f'Stage 2C 완료: 워밍업 과제 {len(starter_tasks)}개 생성', 95)
        except Exception as e:
            import traceback, os
            _log_path = os.path.join(os.path.expanduser('~'), 'HypothesisMaker_debug.log')
            try:
                with open(_log_path, 'a', encoding='utf-8') as _f:
                    _f.write(f'[Stage2C ERROR] {e}\n{traceback.format_exc()}\n')
            except Exception:
                pass
            self._progress(f'  ⚠ Stage 2C 실패 — 가설은 정상 생성됨: {e}', 95)

        self._progress('Stage 2 완료: 리포트 데이터 생성됨', 96)
        return result

    # ──────────────────────────────────────────────
    # Full pipeline
    # ──────────────────────────────────────────────
    def run_full_analysis(self, lab_pdf_paths: list[str], ref_pdf_paths: list[str],
                          assigned_project: str = '',
                          professor_instructions: str = '',
                          language: str = 'ko',
                          student_level: str = 'beginner') -> dict:
        paper_analyses = self.run_stage1(lab_pdf_paths, ref_pdf_paths, assigned_project)
        return self.run_stage2(paper_analyses, assigned_project, professor_instructions, language, student_level)
