"""FastAPI backend for Hypothesis Maker web app."""
from __future__ import annotations
import asyncio
import json
import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))

app = FastAPI(title="Hypothesis Maker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores
sessions: dict[str, dict] = {}
jobs: dict[str, dict] = {}


# ── Upload PDFs ───────────────────────────────────────────────

@app.post("/api/upload")
async def upload_files(
    files: list[UploadFile] = File(...),
    ref_files: list[UploadFile] = File(default=[]),
):
    session_id = str(uuid.uuid4())
    tmpdir = tempfile.mkdtemp()

    lab_paths: list[str] = []
    for f in files:
        if f.filename and f.filename.lower().endswith(".pdf"):
            dest = os.path.join(tmpdir, "lab_" + f.filename)
            with open(dest, "wb") as out:
                out.write(await f.read())
            lab_paths.append(dest)

    ref_paths: list[str] = []
    for f in (ref_files or []):
        if f.filename and f.filename.lower().endswith(".pdf"):
            dest = os.path.join(tmpdir, "ref_" + f.filename)
            with open(dest, "wb") as out:
                out.write(await f.read())
            ref_paths.append(dest)

    if not lab_paths:
        raise HTTPException(400, "PDF 파일을 하나 이상 업로드하세요.")

    sessions[session_id] = {
        "lab_paths": lab_paths,
        "ref_paths": ref_paths,
        "tmpdir": tmpdir,
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
    review_name: str = ""
    review_field: str = ""
    review_stars: int = 0
    review_comment: str = ""


@app.post("/api/analyze")
async def start_analysis(body: AnalyzeBody):
    if body.session_id not in sessions:
        raise HTTPException(404, "세션을 찾을 수 없습니다.")

    session = sessions[body.session_id]
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    jobs[job_id] = {"queue": queue, "result_path": None, "error": None}

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

            prof = body.professor_name.strip()
            filename = f"Research_Starter_Kit_{prof}.docx" if prof else "Research_Starter_Kit.docx"
            output_path = os.path.join(session["tmpdir"], filename)
            review = {
                "name":    body.review_name.strip(),
                "field":   body.review_field.strip(),
                "stars":   body.review_stars,
                "comment": body.review_comment.strip(),
            }
            build_report(result, output_path, review=review)

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
