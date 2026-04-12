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
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores (with creation timestamps for cleanup)
sessions: dict[str, dict] = {}
jobs: dict[str, dict] = {}
import sheets  # Google Sheets persistence

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
    for jid in list(jobs):
        j = jobs[jid]
        if now - j.get("_created", now) > _SESSION_TTL_SECONDS:
            jobs.pop(jid, None)
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
    if body.session_id not in sessions:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    session = sessions[body.session_id]

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
    if body.session_id not in sessions:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    session = sessions[body.session_id]
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    jobs[job_id] = {"queue": queue, "result_path": None, "error": None, "_created": time.time(),
                     "api_provider": body.api_provider, "model": body.model,
                     "session_id": body.session_id}

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

            result = pipeline.run_full_analysis(
                session["lab_paths"],
                session.get("ref_paths", []),
                body.assigned_project,
                body.professor_instructions,
                body.language,
                body.student_level,
            )

            prof = re.sub(r'[^\w\s가-힣\-]', '', body.professor_name.strip())[:50]
            filename = f"Research_Starter_Kit_{prof}.docx" if prof else "Research_Starter_Kit.docx"
            output_path = os.path.join(session["tmpdir"], filename)
            build_report(result, output_path)

            jobs[job_id]["result_data"] = result
            jobs[job_id]["result_path"] = output_path
            jobs[job_id]["filename"] = filename
            # Count this as one successful use (cumulative counter, Sheets-backed)
            _increment_usage_count()
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"message": "리포트 생성 완료!", "percent": 100, "done": True},
            )
        except Exception as e:
            err = str(e)
            jobs[job_id]["error"] = err
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"message": err, "percent": 0, "done": True, "error": err},
            )

    threading.Thread(target=run_analysis, daemon=True).start()
    return {"job_id": job_id}


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
        "stage":        body.stage,
        "error":        error[:2000],          # cap huge tracebacks
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
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    owner = jobs[job_id].get("session_id")
    if owner and owner != session_id:
        raise HTTPException(404, "Job not found")


@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str, session: str | None = None):
    _verify_job_owner(job_id, session)

    queue = jobs[job_id]["queue"]

    async def generate():
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


# ── Download docx ─────────────────────────────────────────────

@app.get("/api/download/{job_id}")
async def download(job_id: str, session: str | None = None):
    _verify_job_owner(job_id, session)
    path = jobs[job_id].get("result_path")
    if not path or not os.path.exists(path):
        raise HTTPException(404, "리포트가 아직 준비되지 않았습니다.")
    filename = jobs[job_id].get("filename", "Research_Starter_Kit.docx")
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
    _widget_cache["button_count"] += 1
    try:
        _save_widget_all()
    except Exception as e:
        print(f"[sheets] save_widget failed: {e}")
    return {"button_count": _widget_cache["button_count"]}


@app.post("/api/widget/view")
async def record_view():
    """Increment the cumulative homepage view counter and return the full
    widget state in one call (so the frontend can render stairs + views from
    a single request). Frontend is expected to gate this per session
    (sessionStorage) to avoid refresh-spam inflation."""
    _load_widget()
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
