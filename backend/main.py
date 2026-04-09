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
from fastapi import FastAPI, File, HTTPException, UploadFile
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
reviews: list[dict] = []  # persistent review list (survives job cleanup)

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


def _cleanup_loop():
    while True:
        time.sleep(300)  # every 5 minutes
        try:
            _cleanup_expired()
        except Exception:
            pass


threading.Thread(target=_cleanup_loop, daemon=True).start()

# Max file size: 50 MB per file, 200 MB total
_MAX_FILE_SIZE = 50 * 1024 * 1024
_MAX_TOTAL_SIZE = 200 * 1024 * 1024


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
                raise HTTPException(413, "전체 파일 크기가 200MB를 초과합니다.")
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
                raise HTTPException(413, "전체 파일 크기가 200MB를 초과합니다.")
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


@app.post("/api/stage0")
async def run_stage0(body: Stage0Body):
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
    language: str = "ko"


@app.post("/api/analyze")
async def start_analysis(body: AnalyzeBody):
    if body.session_id not in sessions:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    session = sessions[body.session_id]
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    jobs[job_id] = {"queue": queue, "result_path": None, "error": None, "_created": time.time(),
                     "api_provider": body.api_provider, "model": body.model}

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
            )

            prof = re.sub(r'[^\w\s가-힣\-]', '', body.professor_name.strip())[:50]
            filename = f"Research_Starter_Kit_{prof}.docx" if prof else "Research_Starter_Kit.docx"
            output_path = os.path.join(session["tmpdir"], filename)
            build_report(result, output_path)

            jobs[job_id]["result_data"] = result
            jobs[job_id]["result_path"] = output_path
            jobs[job_id]["filename"] = filename
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
    review_stars: int = 0
    review_comment: str = ""


@app.post("/api/review/{job_id}")
async def submit_review(job_id: str, body: ReviewBody):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

    review = {
        "name":     body.review_name.strip(),
        "field":    body.review_field.strip(),
        "stars":    body.review_stars,
        "comment":  body.review_comment.strip(),
        "provider": jobs[job_id].get("api_provider", ""),
        "model":    jobs[job_id].get("model", ""),
        "created":  time.time(),
    }
    reviews.append(review)
    return {"ok": True}


@app.get("/api/reviews")
async def get_reviews():
    return {"reviews": reviews}


# ── SSE progress stream ───────────────────────────────────────

@app.get("/api/progress/{job_id}")
async def progress_stream(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")

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
async def download(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
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

widget_state = {
    "stairs": 0,
    "button_count": 0,
    "last_updated": "",
}


@app.get("/api/widget")
async def get_widget():
    return widget_state


class StairsBody(BaseModel):
    count: int
    secret: str = ""


@app.post("/api/widget/stairs")
async def update_stairs(body: StairsBody):
    if body.secret != os.environ.get("WIDGET_SECRET", "hellomymouse"):
        raise HTTPException(403, "비밀번호가 틀렸습니다.")
    widget_state["stairs"] = body.count
    widget_state["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return widget_state


@app.post("/api/widget/button")
async def press_button():
    widget_state["button_count"] += 1
    return {"button_count": widget_state["button_count"]}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
