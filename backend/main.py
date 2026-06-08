"""FastAPI backend for Hypothesis Maker web app."""
from __future__ import annotations
import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

app = FastAPI(title="Hypothesis Maker API")

# CORS: production domains + localhost for dev
_ALLOWED_ORIGINS = [
    "https://hellomymouse.com",
    "https://www.hellomymouse.com",
    "https://hellomymouse.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores (with creation timestamps for cleanup)
sessions: dict[str, dict] = {}
jobs: dict[str, dict] = {}
import sheets  # Google Sheets persistence

_STATE_ROOT = Path(tempfile.gettempdir()) / "hypothesis_maker_state"
_SESSION_STATE_DIR = _STATE_ROOT / "sessions"
_JOB_STATE_DIR = _STATE_ROOT / "jobs"


def _ensure_state_dirs():
    _SESSION_STATE_DIR.mkdir(parents=True, exist_ok=True)
    _JOB_STATE_DIR.mkdir(parents=True, exist_ok=True)


_ensure_state_dirs()


def _session_state_path(session_id: str) -> Path:
    return _SESSION_STATE_DIR / f"{session_id}.json"


def _job_state_path(job_id: str) -> Path:
    return _JOB_STATE_DIR / f"{job_id}.json"


def _write_state(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _read_state(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _delete_state(path: Path):
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _persist_session_state(session_id: str, session: dict):
    payload = {
        "session_id": session_id,
        "lab_paths": list(session.get("lab_paths", [])),
        "ref_paths": list(session.get("ref_paths", [])),
        "tmpdir": session.get("tmpdir", ""),
        "_created": session.get("_created", time.time()),
    }
    _write_state(_session_state_path(session_id), payload)


def _load_session_state(session_id: str) -> dict | None:
    payload = _read_state(_session_state_path(session_id))
    if not payload:
        return None
    created = float(payload.get("_created", 0) or 0)
    if created and time.time() - created > _SESSION_TTL_SECONDS:
        _delete_state(_session_state_path(session_id))
        return None
    tmpdir = payload.get("tmpdir", "")
    lab_paths = [p for p in payload.get("lab_paths", []) if isinstance(p, str) and os.path.exists(p)]
    ref_paths = [p for p in payload.get("ref_paths", []) if isinstance(p, str) and os.path.exists(p)]
    if not tmpdir or not os.path.isdir(tmpdir) or not lab_paths:
        return None
    session = {
        "lab_paths": lab_paths,
        "ref_paths": ref_paths,
        "tmpdir": tmpdir,
        "_created": created or time.time(),
    }
    sessions[session_id] = session
    return session


def _persist_job_state(job_id: str, job: dict):
    payload = {
        "job_id": job_id,
        "session_id": job.get("session_id", ""),
        "api_provider": job.get("api_provider", ""),
        "model": job.get("model", ""),
        "result_path": job.get("result_path", ""),
        "filename": job.get("filename", ""),
        "error": job.get("error", ""),
        "_created": job.get("_created", time.time()),
    }
    _write_state(_job_state_path(job_id), payload)


def _load_job_state(job_id: str) -> dict | None:
    payload = _read_state(_job_state_path(job_id))
    if not payload:
        return None
    created = float(payload.get("_created", 0) or 0)
    if created and time.time() - created > _SESSION_TTL_SECONDS:
        _delete_state(_job_state_path(job_id))
        return None
    result_path = payload.get("result_path", "")
    if result_path and not os.path.exists(result_path):
        result_path = ""
    job = {
        "queue": asyncio.Queue(),
        "result_path": result_path,
        "filename": payload.get("filename", ""),
        "error": payload.get("error", ""),
        "_created": created or time.time(),
        "api_provider": payload.get("api_provider", ""),
        "model": payload.get("model", ""),
        "session_id": payload.get("session_id", ""),
    }
    jobs[job_id] = job
    return job


def _get_session(session_id: str) -> dict | None:
    return sessions.get(session_id) or _load_session_state(session_id)


def _get_job(job_id: str) -> dict | None:
    return jobs.get(job_id) or _load_job_state(job_id)

# ── Session / temp file cleanup ─────────────────────────────
_SESSION_TTL_SECONDS = 3600  # 1 hour


def _cleanup_expired():
    """Remove sessions and jobs older than TTL, delete their temp files."""
    now = time.time()
    for sid in list(sessions):
        s = sessions[sid]
        if now - s.get("_created", now) > _SESSION_TTL_SECONDS:
            tmpdir = s.get("tmpdir")
            if tmpdir and os.path.isdir(tmpdir):
                shutil.rmtree(tmpdir, ignore_errors=True)
            sessions.pop(sid, None)
            _delete_state(_session_state_path(sid))
    for jid in list(jobs):
        j = jobs[jid]
        if now - j.get("_created", now) > _SESSION_TTL_SECONDS:
            jobs.pop(jid, None)
            _delete_state(_job_state_path(jid))
    # Drop rate-limit buckets that have no recent entries (prevents unbounded growth).
    cutoff = now - 120.0
    with _rate_lock:
        for k in list(_rate_buckets):
            bucket = _rate_buckets[k]
            while bucket and bucket[0] < cutoff:
                bucket.pop(0)
            if not bucket:
                _rate_buckets.pop(k, None)


# ── Rate limiting (lightweight in-memory, per-IP) ───────────
# "살살" — generous defaults, just enough to stop a runaway bot.
# Shared buckets across workers would need Redis, but single-process is fine here.
_rate_buckets: dict[str, list[float]] = {}
_rate_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_check(key: str, max_per_min: int) -> bool:
    now = time.time()
    cutoff = now - 60.0
    with _rate_lock:
        bucket = _rate_buckets.setdefault(key, [])
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= max_per_min:
            return False
        bucket.append(now)
        return True


def rate_limit(scope: str, max_per_min: int):
    """FastAPI dependency that enforces a per-IP per-minute limit on a scope."""
    def dep(request: Request):
        ip = _client_ip(request)
        if not _rate_check(f"{scope}:{ip}", max_per_min):
            raise HTTPException(429, "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.")
    return dep


def _cleanup_loop():
    while True:
        time.sleep(300)  # every 5 minutes
        try:
            _cleanup_expired()
        except Exception:
            pass


threading.Thread(target=_cleanup_loop, daemon=True).start()


@app.get("/")
async def root():
    return {"ok": True, "service": "Hypothesis Maker API"}


@app.get("/api/health")
async def health():
    return {"ok": True}


# Max file size: 50 MB per file, 500 MB total
_MAX_FILE_SIZE = 50 * 1024 * 1024
_MAX_TOTAL_SIZE = 500 * 1024 * 1024


# ── Upload PDFs ───────────────────────────────────────────────

def _safe_filename(name: str) -> str:
    """Sanitize filename: keep only safe characters, strip path components."""
    name = os.path.basename(name)
    name = re.sub(r'[^\w\s\-.\(\)\[\]가-힣]', '_', name)
    return name[:200] or "file.pdf"


@app.post("/api/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    ref_files: list[UploadFile] = File(default=[]),
    _rl=Depends(rate_limit("upload", 10)),
):
    session_id = str(uuid.uuid4())
    tmpdir = tempfile.mkdtemp()
    total_size = 0

    lab_paths: list[str] = []
    for f in files:
        if f.filename and f.filename.lower().endswith(".pdf"):
            content = await f.read()
            if len(content) > _MAX_FILE_SIZE:
                raise HTTPException(413, f"파일이 너무 큽니다: {f.filename} (최대 50MB)")
            total_size += len(content)
            if total_size > _MAX_TOTAL_SIZE:
                raise HTTPException(413, "전체 파일 크기가 500MB를 초과합니다.")
            safe_name = _safe_filename(f.filename)
            dest = os.path.join(tmpdir, "lab_" + safe_name)
            with open(dest, "wb") as out:
                out.write(content)
            lab_paths.append(dest)

    ref_paths: list[str] = []
    for f in (ref_files or []):
        if f.filename and f.filename.lower().endswith(".pdf"):
            content = await f.read()
            if len(content) > _MAX_FILE_SIZE:
                raise HTTPException(413, f"파일이 너무 큽니다: {f.filename} (최대 50MB)")
            total_size += len(content)
            if total_size > _MAX_TOTAL_SIZE:
                raise HTTPException(413, "전체 파일 크기가 500MB를 초과합니다.")
            safe_name = _safe_filename(f.filename)
            dest = os.path.join(tmpdir, "ref_" + safe_name)
            with open(dest, "wb") as out:
                out.write(content)
            ref_paths.append(dest)

    if not lab_paths:
        raise HTTPException(400, "PDF 파일을 하나 이상 업로드하세요.")

    sessions[session_id] = {
        "lab_paths": lab_paths,
        "ref_paths": ref_paths,
        "tmpdir": tmpdir,
        "_created": time.time(),
    }
    _persist_session_state(session_id, sessions[session_id])
    return {
        "session_id": session_id,
        "file_count": len(lab_paths),
        "ref_count": len(ref_paths),
    }


# ── Stage 0: Project scan ─────────────────────────────────────

class Stage0Body(BaseModel):
    session_id: str
    api_provider: str
    api_key: str
    model: str = ""


# ── API key pre-flight check ──────────────────────────────────

class PreflightBody(BaseModel):
    api_provider: str
    api_key: str
    model: str = ""


@app.post("/api/preflight")
async def preflight(body: PreflightBody, _rl=Depends(rate_limit("preflight", 30))):
    """API 키 + 모델 작동 여부 빠르게 확인. 분석 시작 전 호출 권장."""
    from analyzer.api_client import APIClient
    try:
        client = APIClient(body.api_provider, body.api_key, body.model)
        # 매우 짧은 요청으로 인증 + 모델 작동 확인
        client.call(
            user_prompt="Reply with just 'OK'",
            system_prompt="",
            max_tokens=10,
        )
        return {"ok": True, "model": client.model}
    except ValueError as e:
        # 인증 오류 — 키 문제
        raise HTTPException(401, str(e))
    except RuntimeError as e:
        # API/모델 오류 — 다른 옵션 권장
        raise HTTPException(503, str(e))
    except Exception as e:
        raise HTTPException(500, f"사전 점검 실패: {e}")


@app.post("/api/stage0")
async def run_stage0(body: Stage0Body, _rl=Depends(rate_limit("stage0", 20))):
    session = _get_session(body.session_id)
    if session is None:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    from analyzer.api_client import APIClient
    from analyzer.processor import AnalysisPipeline

    try:
        client = APIClient(body.api_provider, body.api_key, body.model)
        pipeline = AnalysisPipeline(client)
        result = pipeline.run_stage0(session["lab_paths"])
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))

    session["stage0_result"] = result
    return {
        "projects": result.get("projects", []),
        "lab_name_guess": result.get("lab_name_guess", ""),
    }


# ── Full analysis (Stage 1 + 2) ───────────────────────────────

class AnalyzeBody(BaseModel):
    session_id: str
    api_provider: str
    api_key: str
    model: str = ""
    assigned_project: str = ""
    professor_name: str = ""
    professor_instructions: str = ""
    student_level: str = "beginner"
    language: str = "ko"


@app.post("/api/analyze")
async def start_analysis(body: AnalyzeBody, _rl=Depends(rate_limit("analyze", 10))):
    session = _get_session(body.session_id)
    if session is None:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    jobs[job_id] = {"queue": queue, "result_path": None, "error": None, "_created": time.time(),
                     "api_provider": body.api_provider, "model": body.model,
                     "session_id": body.session_id}
    _persist_job_state(job_id, jobs[job_id])

    loop = asyncio.get_event_loop()

    def run_analysis():
        from analyzer.api_client import APIClient
        from analyzer.processor import AnalysisPipeline
        from report.docx_builder import build_report

        def cb(msg: str, pct: int):
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"message": msg, "percent": pct, "done": False},
            )

        try:
            client = APIClient(body.api_provider, body.api_key, body.model)
            pipeline = AnalysisPipeline(client, cb)

            paper_analyses = pipeline.run_stage1(
                session["lab_paths"],
                session.get("ref_paths", []),
                body.assigned_project,
            )

            stage2_input = paper_analyses
            if len(paper_analyses) > 5:
                cb("논문별 Markdown cache 및 batch synthesis 생성 중...", 70)
                stage2_input = _write_markdown_cache(session, paper_analyses, 5, cb)
                cb(f"{len(paper_analyses)}편을 {len(stage2_input)}개 batch로 압축 완료", 70)

            result = pipeline.run_stage2(
                stage2_input,
                body.assigned_project,
                body.professor_instructions,
                body.language,
                body.student_level,
            )
            if len(paper_analyses) > 5:
                result["paper_summaries"] = _paper_summaries_from_analyses(paper_analyses)
                _merge_equipment_capabilities(result, paper_analyses)
                result["batch_pipeline"] = {
                    "paper_count": len(paper_analyses),
                    "batch_count": len(stage2_input),
                    "batch_size": 5,
                }

            prof = re.sub(r'[^\w\s가-힣\-]', '', body.professor_name.strip())[:50]
            filename = f"Research_Starter_Kit_{prof}.docx" if prof else "Research_Starter_Kit.docx"
            output_path = os.path.join(session["tmpdir"], filename)
            build_report(result, output_path)

            jobs[job_id]["result_data"] = result
            jobs[job_id]["result_path"] = output_path
            jobs[job_id]["filename"] = filename
            _persist_job_state(job_id, jobs[job_id])
            # Count this as one successful use (cumulative counter, Sheets-backed)
            _increment_usage_count()
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"message": "리포트 생성 완료!", "percent": 100, "done": True},
            )
        except Exception as e:
            err = str(e)
            jobs[job_id]["error"] = err
            _persist_job_state(job_id, jobs[job_id])
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"message": err, "percent": 0, "done": True, "error": err},
            )

    threading.Thread(target=run_analysis, daemon=True).start()
    return {"job_id": job_id}


def _md_list(values) -> str:
    items = [str(v).strip() for v in (values or []) if str(v).strip()]
    return "\n".join(f"- {v}" for v in items) or "- (none)"


def _dedupe_named_records(records, limit: int = 30) -> list[dict]:
    dedup: dict[str, dict] = {}
    for item in records or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        catalog = str(item.get("catalog_number", "")).strip()
        key = f"{name.lower()}::{catalog.lower()}" if catalog else name.lower()
        current = dedup.setdefault(key, {"name": name})
        for field in ("manufacturer", "catalog_number", "description", "notes", "version"):
            value = str(item.get(field, "")).strip()
            if value and not current.get(field):
                current[field] = value
    return list(dedup.values())[:limit]


def _equipment_md_list(records) -> str:
    items = []
    for item in records or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        manufacturer = str(item.get("manufacturer", "")).strip()
        catalog = str(item.get("catalog_number", "")).strip()
        detail = []
        if manufacturer:
            detail.append(f"manufacturer: {manufacturer}")
        if catalog:
            detail.append(f"catalog_number: {catalog}")
        items.append(f"- {name}" + (f" ({'; '.join(detail)})" if detail else ""))
    return "\n".join(items) or "- (none)"


def _paper_summaries_from_analyses(paper_analyses: list[dict]) -> list[dict]:
    summaries = []
    for paper in paper_analyses:
        key_results = paper.get("key_results", []) or []
        limitations = paper.get("limitations", []) or []
        summaries.append({
            "filename": paper.get("filename", ""),
            "title": paper.get("title", paper.get("filename", "")),
            "method_tag": paper.get("method_tag", ""),
            "summary": paper.get("summary", ""),
            "key_finding": key_results[0] if key_results else "",
            "limitation": paper.get("limitation_for_hypo") or (limitations[0] if limitations else ""),
        })
    return summaries


def _merge_equipment_capabilities(result: dict, paper_analyses: list[dict]) -> None:
    equipment = []
    for paper in paper_analyses:
        equipment.extend(paper.get("equipment_details", []) or [])
    merged = _dedupe_named_records(equipment)
    if not merged:
        return

    capabilities = result.setdefault("lab_capabilities", {})
    existing = capabilities.get("equipment_or_models", []) or []
    capabilities["equipment_or_models"] = _dedupe_named_records(existing + merged, limit=50)


def _write_markdown_cache(session: dict, paper_analyses: list[dict],
                          batch_size: int, cb) -> list[dict]:
    cache_dir = os.path.join(session["tmpdir"], "markdown_cache")
    os.makedirs(cache_dir, exist_ok=True)
    compressed: list[dict] = []

    for i, paper in enumerate(paper_analyses, start=1):
        filename = paper.get("filename", f"paper_{i}.pdf")
        stem = re.sub(r"[^\w가-힣.-]+", "_", os.path.splitext(filename)[0])[:80]
        md_name = f"paper_{i:02d}_{stem}.md"
        md_path = os.path.join(cache_dir, md_name)
        text = f"""# {paper.get('title') or filename}

- source_pdf: {filename}
- one_line_summary: {paper.get('summary', '')}
- core_claim: {paper.get('key_results', [''])[0] if paper.get('key_results') else ''}

## Key Results
{_md_list(paper.get('key_results'))}

## Materials and Methods
{_md_list(paper.get('techniques'))}

## Equipment / Reagents / Software
{_equipment_md_list(paper.get('equipment_details'))}
{_md_list([x.get('name', '') for x in paper.get('software_and_tools', [])])}

## Limitations
{_md_list(paper.get('limitations'))}

## Further Studies
{_md_list(paper.get('future_directions'))}

## Hypothesis Gap
{paper.get('limitation_for_hypo', '')}
"""
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(text)

    batch_size = max(2, min(batch_size, 10))
    for start in range(0, len(paper_analyses), batch_size):
        batch = paper_analyses[start:start + batch_size]
        batch_no = len(compressed) + 1
        md_name = f"batch_{batch_no:02d}_synthesis.md"
        md_path = os.path.join(cache_dir, md_name)
        titles = [p.get("title") or p.get("filename", "") for p in batch]
        techniques = []
        limitations = []
        futures = []
        terms = []
        equipment = []
        software = []
        for p in batch:
            techniques.extend(p.get("techniques", []) or [])
            limitations.extend(p.get("limitations", []) or [])
            futures.extend(p.get("future_directions", []) or [])
            terms.extend(p.get("key_terms", []) or [])
            equipment.extend(p.get("equipment_details", []) or [])
            software.extend(p.get("software_and_tools", []) or [])
        equipment = _dedupe_named_records(equipment)
        software = _dedupe_named_records(software)
        summary = " / ".join((p.get("summary") or p.get("title") or "")[:220] for p in batch if p)
        limitation = " / ".join((p.get("limitation_for_hypo") or "")[:180] for p in batch if p.get("limitation_for_hypo"))
        text = f"""# Batch {batch_no} Synthesis

## Papers
{_md_list(titles)}

## Shared Theme
{summary}

## Repeated Methods
{_md_list(dict.fromkeys(techniques).keys())}

## Equipment / Reagents / Models
{_equipment_md_list(equipment)}

## Recurring Limitations
{_md_list(limitations[:12])}

## Further Studies
{_md_list(futures[:12])}

## Strongest Follow-up Gaps
{limitation or '(none detected)'}
"""
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(text)
        compressed.append({
            "filename": md_name,
            "title": f"Batch {batch_no} synthesis ({len(batch)} papers)",
            "is_reference": False,
            "field": batch[0].get("field", "research") if batch else "research",
            "method_tag": "batch synthesis",
            "techniques": list(dict.fromkeys(techniques))[:12],
            "key_results": [p.get("summary", "") for p in batch if p.get("summary")][:8],
            "limitations": limitations[:12],
            "future_directions": futures[:12],
            "key_terms": list(dict.fromkeys(terms))[:15],
            "equipment_details": equipment,
            "software_and_tools": software,
            "paper_type": "batch",
            "summary": summary,
            "limitation_for_hypo": limitation,
        })
        cb(f"Batch cache: {md_name} 생성 완료", 70)

    return compressed


# ── Reviews ──────────────────────────────────────────────────

class ReviewBody(BaseModel):
    review_name: str = ""
    review_field: str = ""
    review_position: str = ""
    review_stars: int = 0
    review_comment: str = ""


@app.post("/api/review/{job_id}")
async def submit_review(job_id: str, body: ReviewBody, session: str | None = None):
    _verify_job_owner(job_id, session)

    review = {
        "name":     body.review_name.strip(),
        "field":    body.review_field.strip(),
        "position": body.review_position.strip(),
        "stars":    body.review_stars,
        "comment":  body.review_comment.strip(),
        "provider": jobs[job_id].get("api_provider", ""),
        "model":    jobs[job_id].get("model", ""),
        "created":  time.time(),
    }
    try:
        sheets.append_review(review)
    except Exception as e:
        print(f"[sheets] append_review failed: {e}")
    return {"ok": True}


@app.post("/api/review-direct")
async def submit_review_direct(body: ReviewBody):
    """job_id 없이 리뷰 직접 등록 (수동 추가용)."""
    review = {
        "name":     body.review_name.strip(),
        "field":    body.review_field.strip(),
        "position": body.review_position.strip(),
        "stars":    body.review_stars,
        "comment":  body.review_comment.strip(),
        "provider": "",
        "model":    "",
        "created":  time.time(),
    }
    try:
        sheets.append_review(review)
    except Exception as e:
        print(f"[sheets] append_review failed: {e}")
        raise HTTPException(500, f"Sheets error: {e}")
    return {"ok": True}


@app.delete("/api/review/{row_index}")
async def delete_review(row_index: int):
    """Sheets 행 번호로 리뷰 삭제 (header=1, 첫 데이터=2)."""
    try:
        sheets.delete_review(row_index)
    except Exception as e:
        raise HTTPException(500, f"Sheets error: {e}")
    return {"ok": True}


@app.get("/api/reviews")
async def get_reviews():
    try:
        return {"reviews": sheets.get_reviews()}
    except Exception as e:
        print(f"[sheets] get_reviews failed: {e}")
        return {"reviews": []}


# ── Failure feedback ─────────────────────────────────────────

class FailureFeedbackBody(BaseModel):
    job_id: str = ""
    provider: str = ""
    model: str = ""
    paper_count: int = 0
    stage: str = ""
    error: str = ""
    user_comment: str = ""
    contact: str = ""


_FAILURE_STAGE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("preflight", ("preflight", "api key", "api 키", "사전 점검")),
    ("upload", ("upload", "업로드", "50mb", "500mb")),
    ("stage0", ("stage 0", "stage0", "quick scan", "프로젝트", "title", "abstract", "제목", "초록")),
    ("stage1", ("stage 1", "stage1", "논문 심층 분석")),
    ("stage2b", ("stage 2b", "stage2b", "checklist", "background", "roadmap", "체크리스트", "배경지식", "로드맵")),
    ("stage2c", ("stage 2c", "stage2c", "starter task", "워밍업")),
    ("auto_download", ("auto download", "auto-download", "자동 다운로드")),
    ("download", ("download", "다운로드", "session expired", "세션이 만료")),
    ("progress_stream", ("progress_stream", "eventsource", "server connection lost", "연결이 끊겼")),
    ("analyze_start", ("analyze_start", "starting analysis", "분석 시작")),
    ("analyze", ("stage 2", "stage2", "hypothesis", "json", "parse", "가설", "리포트 생성", "synthesis")),
]

_FAILURE_SIGNATURE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("invalid_api_key", ("api key not valid", "invalid api key", "authentication", "api 키가 올바르지", "api 키가 유효하지")),
    ("rate_limit", ("rate limit", "too many requests", "429", "요청이 너무 많습니다")),
    ("quota_exhausted", ("quota exceeded", "resource_exhausted", "free-models-per-day", "daily limit", "add 10 credits")),
    ("service_overloaded", ("503", "unavailable", "overloaded", "high demand", "과부하")),
    ("gemini_safety_block", ("safety", "recitation", "차단", "안전 필터")),
    ("json_parse_failure", ("json", "parse", "valid json", "truncated", "올바른 json")),
    ("download_session_expired", ("session expired", "세션이 만료", "404")),
    ("file_too_large", ("50mb", "파일이 너무 큽니다")),
    ("total_upload_too_large", ("500mb", "전체 파일 크기")),
    ("sheets_rate_limit", ("sheets api", "read requests", "spreadsheets", "sheets error")),
]


def _canonicalize_failure_stage(stage: str, error: str = "", user_comment: str = "") -> str:
    direct = (stage or "").strip().lower().replace("-", "_").replace(" ", "_")
    allowed = {name for name, _ in _FAILURE_STAGE_RULES}
    if direct in allowed:
        return direct

    haystack = " ".join([stage or "", error or "", user_comment or ""]).strip().lower()
    for canonical, needles in _FAILURE_STAGE_RULES:
        if any(needle in haystack for needle in needles):
            return canonical

    sanitized = re.sub(r"[^a-z0-9_]+", "_", direct).strip("_")
    return sanitized[:50] or "unknown"


def _annotate_failure_error(error: str) -> str:
    raw = " ".join((error or "").split())
    if not raw:
        return ""
    if raw.startswith("[sig:"):
        return raw[:2000]

    lower = raw.lower()
    for signature, needles in _FAILURE_SIGNATURE_RULES:
        if any(needle in lower for needle in needles):
            return f"[sig:{signature}] {raw}"[:2000]
    return raw[:2000]


@app.post("/api/failure-feedback")
async def submit_failure_feedback(body: FailureFeedbackBody):
    """Record a failed-run feedback so we can learn what's actually breaking.
    Accepts either a live job_id (auto-fills provider/model/error) or a raw
    payload (frontend already collected context)."""
    provider = body.provider
    model = body.model
    error = body.error
    if body.job_id and body.job_id in jobs:
        j = jobs[body.job_id]
        provider = provider or j.get("api_provider", "")
        model = model or j.get("model", "")
        error = error or (j.get("error") or "")

    entry = {
        "created":      time.time(),
        "provider":     provider,
        "model":        model,
        "paper_count":  body.paper_count,
        "stage":        _canonicalize_failure_stage(body.stage, error, body.user_comment),
        "error":        _annotate_failure_error(error),
        "user_comment": body.user_comment.strip()[:2000],
        "contact":      body.contact.strip()[:200],
    }
    try:
        sheets.append_failure(entry)
    except Exception as e:
        print(f"[sheets] append_failure failed: {e}")
        raise HTTPException(500, f"Sheets error: {e}")
    return {"ok": True}


# ── SSE progress stream ───────────────────────────────────────

def _verify_job_owner(job_id: str, session_id: str | None):
    """Ensure the caller knows the session_id that created this job.
    Raises 404 (not 403) so we don't leak the existence of the job id."""
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    owner = job.get("session_id")
    if owner and owner != session_id:
        raise HTTPException(404, "Job not found")


@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str, session: str | None = None):
    _verify_job_owner(job_id, session)

    job = _get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    queue = job["queue"]

    async def generate():
        current = _get_job(job_id) or job
        if current.get("error"):
            err = current["error"]
            yield f"data: {json.dumps({'message': err, 'percent': 0, 'done': True, 'error': err}, ensure_ascii=False)}\n\n"
            return
        if current.get("result_path"):
            yield f"data: {json.dumps({'message': '리포트 생성 완료!', 'percent': 100, 'done': True}, ensure_ascii=False)}\n\n"
            return
        while True:
            try:
                data = await asyncio.wait_for(queue.get(), timeout=60.0)
                yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                if data.get("done"):
                    break
            except asyncio.TimeoutError:
                yield 'data: {"message":"...","percent":-1,"done":false}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/job/{job_id}/status")
async def job_status(job_id: str, session: str | None = None):
    _verify_job_owner(job_id, session)
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.get("error"):
        return {"status": "error", "error": job["error"]}
    if job.get("result_path"):
        return {
            "status": "done",
            "filename": job.get("filename", "Research_Starter_Kit.docx"),
        }
    return {"status": "running"}


# ── Download docx ─────────────────────────────────────────────

@app.get("/api/download/{job_id}")
async def download(job_id: str, session: str | None = None):
    _verify_job_owner(job_id, session)
    job = _get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    path = job.get("result_path")
    if not path or not os.path.exists(path):
        raise HTTPException(404, "리포트가 아직 준비되지 않았습니다.")
    filename = job.get("filename", "Research_Starter_Kit.docx")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


# ── Widget (계단 + 버튼) ──────────────────────────────────────

from datetime import datetime, timezone

# In-memory cache for widget (reduces Sheets API calls)
_widget_cache: dict = {
    "stairs": 0,
    "button_count": 0,
    "last_updated": "",
    "usage_count": 0,
    "view_count": 0,
}
_widget_loaded = False


def _load_widget():
    global _widget_cache, _widget_loaded
    if not _widget_loaded:
        try:
            _widget_cache = sheets.get_widget()
        except Exception as e:
            print(f"[sheets] get_widget failed: {e}")
        _widget_loaded = True


@app.get("/api/widget")
async def get_widget():
    _load_widget()
    _rollover_if_new_day()
    return _widget_cache


class StairsBody(BaseModel):
    count: int
    secret: str = ""


def _save_widget_all():
    """Persist current widget cache to Sheets using today's date."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sheets.save_widget(
        today,
        _widget_cache.get("stairs", 0),
        _widget_cache.get("button_count", 0),
        _widget_cache.get("usage_count", 0),
        _widget_cache.get("view_count", 0),
    )


def _rollover_if_new_day():
    """button_count와 view_count는 하루 단위로 리셋. last_updated가 오늘이 아니면 0으로."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _widget_cache.get("last_updated") != today:
        _widget_cache["button_count"] = 0
        _widget_cache["view_count"] = 0
        _widget_cache["last_updated"] = today


@app.post("/api/widget/stairs")
async def update_stairs(body: StairsBody):
    expected = os.environ.get("WIDGET_SECRET")
    if not expected:
        # Never allow a default — if the server hasn't set WIDGET_SECRET,
        # reject the write instead of falling back to a guessable string.
        raise HTTPException(503, "위젯 설정이 초기화되지 않았습니다.")
    if body.secret != expected:
        raise HTTPException(403, "비밀번호가 틀렸습니다.")
    _load_widget()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _widget_cache["stairs"] = body.count
    _widget_cache["last_updated"] = today
    try:
        _save_widget_all()
    except Exception as e:
        print(f"[sheets] save_widget failed: {e}")
    return _widget_cache


@app.post("/api/widget/button")
async def press_button():
    _load_widget()
    _rollover_if_new_day()
    _widget_cache["button_count"] += 1
    try:
        _save_widget_all()
    except Exception as e:
        print(f"[sheets] save_widget failed: {e}")
    return {"button_count": _widget_cache["button_count"]}


@app.post("/api/widget/view")
async def record_view():
    """Increment today's homepage view counter (하루 단위 리셋) and return the full
    widget state in one call. Frontend gates this per session (sessionStorage)
    to avoid refresh-spam inflation."""
    _load_widget()
    _rollover_if_new_day()
    _widget_cache["view_count"] = _widget_cache.get("view_count", 0) + 1
    try:
        _save_widget_all()
    except Exception as e:
        print(f"[sheets] view increment failed: {e}")
    return _widget_cache


def _increment_usage_count():
    """Bump the cumulative hypothesis-maker usage counter. Safe to fail silently."""
    try:
        _load_widget()
        _widget_cache["usage_count"] = _widget_cache.get("usage_count", 0) + 1
        _save_widget_all()
    except Exception as e:
        print(f"[sheets] usage increment failed: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
