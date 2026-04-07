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
    STAGE_2_SYSTEM, build_stage2_prompt,
    STAGE_2B_SYSTEM, build_stage2b_prompt,
)

ProgressCallback = Callable[[str, int], None]


def _recover_truncated_json(text: str) -> dict:
    """Close unclosed brackets/braces in a truncated JSON string."""
    stack = []
    in_string = False
    escape = False
    last_valid_pos = 0

    for i, c in enumerate(text):
        if escape:
            escape = False
            continue
        if c == '\\' and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            if not in_string:
                last_valid_pos = i + 1
        elif not in_string:
            if c in '{[':
                stack.append(c)
            elif c in '}]':
                if stack:
                    stack.pop()
                last_valid_pos = i + 1

    truncated = text[:last_valid_pos]
    for c in reversed(stack):
        truncated += '}' if c == '{' else ']'

    return json.loads(truncated)


def _parse_json_response(text: str) -> dict:
    """Strip markdown fences and parse JSON. Falls back to truncation recovery."""
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Cut at the error position and close unclosed brackets.
        # Passing the full text to _recover_truncated_json is wrong:
        # it would update last_valid_pos past the malformed region.
        return _recover_truncated_json(text[:e.pos])


class AnalysisPipeline:
    def __init__(self, api_client: APIClient, progress_callback: ProgressCallback | None = None):
        self.api = api_client
        self._cb = progress_callback or (lambda msg, pct: None)

    def _progress(self, msg: str, pct: int):
        self._cb(msg, pct)

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
                   professor_instructions: str) -> dict:
        """Synthesize all analyses into final report data."""
        self._progress('Stage 2: 가설 및 리포트 생성 중... (1-3분 소요)', 70)

        # Keepalive: slowly advance progress bar so user knows it's still running
        _stop = threading.Event()
        def _keepalive():
            pct = 71
            msgs = [
                'AI가 논문들을 종합 분석 중...',
                'AI가 연구 가설을 설계 중...',
                'AI가 평가 지표와 Baseline 작성 중...',
                'AI가 리포트 구조를 완성 중...',
            ]
            while not _stop.is_set() and pct < 89:
                time.sleep(10)
                if not _stop.is_set():
                    msg = msgs[min((pct - 71) // 5, len(msgs) - 1)]
                    self._progress(msg, pct)
                    pct += 1
        threading.Thread(target=_keepalive, daemon=True).start()

        # Detect dominant field
        fields = [p.get('field', '') for p in paper_analyses if p.get('field')]
        detected_field = max(set(fields), key=fields.count) if fields else 'STEM research'

        prompt = build_stage2_prompt(paper_analyses, assigned_project,
                                     professor_instructions, detected_field)
        try:
            response = self.api.call(prompt, STAGE_2_SYSTEM, max_tokens=16000)
        finally:
            _stop.set()

        # Try parsing; if it fails, retry once
        result = None
        for attempt in range(2):
            try:
                result = _parse_json_response(response)
                break
            except json.JSONDecodeError:
                if attempt == 0:
                    self._progress('JSON 파싱 실패 — 자동 재시도 중...', 72)
                    try:
                        response = self.api.call(prompt, STAGE_2_SYSTEM, max_tokens=16000)
                    except Exception as retry_err:
                        raise RuntimeError(f'재시도 중 API 오류: {retry_err}')
                else:
                    raise RuntimeError(
                        'AI가 올바른 형식으로 응답하지 않았습니다. '
                        '논문 수를 줄이거나 Claude Sonnet으로 변경해보세요.'
                    )

        self._progress('Stage 2A 완료 — 체크리스트·배경지식·로드맵 생성 중...', 90)

        # Stage 2B: checklist / background / roadmap (separate smaller call)
        try:
            hypo_summary = '\n'.join(
                f"- {h.get('id','')}: {h.get('name','')} [{h.get('feasibility','')}]"
                for h in result.get('hypotheses', [])
            )
            self._progress('Stage 2B: 체크리스트·배경지식·로드맵 생성 중...', 91)
            prompt2b = build_stage2b_prompt(hypo_summary, detected_field, assigned_project)
            response2b = self.api.call(prompt2b, STAGE_2B_SYSTEM, max_tokens=8192)
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
                f'로드맵 {len(roadmap)}개월', 92
            )
        except Exception as e:
            import traceback, os
            _log_path = os.path.join(os.path.expanduser('~'), 'HypothesisMaker_debug.log')
            try:
                with open(_log_path, 'a', encoding='utf-8') as _f:
                    _f.write(f'[Stage2B ERROR] {e}\n{traceback.format_exc()}\n')
            except Exception:
                pass
            self._progress(f'  ⚠ 보조 섹션 생성 실패 — 로그 확인: {e}', 91)

        self._progress('Stage 2 완료: 리포트 데이터 생성됨', 92)
        return result

    # ──────────────────────────────────────────────
    # Full pipeline
    # ──────────────────────────────────────────────
    def run_full_analysis(self, lab_pdf_paths: list[str], ref_pdf_paths: list[str],
                          assigned_project: str = '',
                          professor_instructions: str = '') -> dict:
        paper_analyses = self.run_stage1(lab_pdf_paths, ref_pdf_paths, assigned_project)
        return self.run_stage2(paper_analyses, assigned_project, professor_instructions)
