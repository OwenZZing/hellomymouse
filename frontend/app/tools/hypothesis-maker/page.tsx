"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";

// ── Star background ───────────────────────────────────────────

const STARS = [
  { name: "@kseo_nkook",    x: 82, y: 12, size: 12, opacity: 0.45 },
  { name: "@infp_horong",   x: 6,  y: 18, size: 12, opacity: 0.45 },
  { name: "@eunsuniverse",  x: 55, y: 90, size: 12, opacity: 0.45 },
];

function StarBackground() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none select-none">
      {STARS.map((s, i) => (
        <span
          key={i}
          className="absolute font-mono text-violet-300"
          style={{
            left: `${s.x}%`,
            top: `${s.y}%`,
            fontSize: `${s.size}px`,
            opacity: s.opacity,
          }}
        >
          {s.name}
        </span>
      ))}
    </div>
  );
}

// ── Types ─────────────────────────────────────────────────────

type Provider = "claude" | "openai" | "gemini";

interface Project {
  id: number;
  name: string;
  description: string;
  related_papers: string[];
}

type Step = "setup" | "upload" | "scan" | "configure" | "analyze" | "done";

const MODELS: Record<Provider, string[]> = {
  claude: ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5-20251001", "claude-3-5-sonnet-20241022"],
  openai: ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1-mini"],
  gemini: ["gemini-2.5-flash"],
};

const PROVIDER_LABELS: Record<Provider, string> = {
  claude: "Claude (Anthropic)",
  openai: "GPT (OpenAI)",
  gemini: "Gemini (Google)",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// ── Step indicator ─────────────────────────────────────────────

const STEPS: { key: Step; label: string }[] = [
  { key: "setup", label: "API 설정" },
  { key: "upload", label: "PDF 업로드" },
  { key: "scan", label: "프로젝트 파악" },
  { key: "configure", label: "분석 설정" },
  { key: "analyze", label: "분석 중" },
  { key: "done", label: "완료" },
];

function StepBar({ current }: { current: Step }) {
  const idx = STEPS.findIndex((s) => s.key === current);
  return (
    <div className="flex items-center gap-1 mb-10 overflow-x-auto pb-1">
      {STEPS.map((s, i) => (
        <div key={s.key} className="flex items-center">
          <div
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-mono transition-all ${
              i < idx
                ? "bg-violet-500/20 text-violet-300"
                : i === idx
                ? "bg-violet-500 text-white"
                : "bg-zinc-800 text-zinc-500"
            }`}
          >
            <span
              className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${
                i < idx ? "bg-violet-400 text-white" : i === idx ? "bg-white/20" : "bg-zinc-700"
              }`}
            >
              {i < idx ? "✓" : i + 1}
            </span>
            {s.label}
          </div>
          {i < STEPS.length - 1 && (
            <div className={`w-4 h-px mx-1 ${i < idx ? "bg-violet-500/40" : "bg-zinc-700"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

// ── Drop zone ─────────────────────────────────────────────────

function DropZone({
  label,
  files,
  onChange,
}: {
  label: string;
  files: File[];
  onChange: (f: File[]) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const dropped = Array.from(e.dataTransfer.files).filter((f) =>
        f.name.endsWith(".pdf")
      );
      onChange([...files, ...dropped]);
    },
    [files, onChange]
  );

  return (
    <div>
      <p className="text-sm text-zinc-400 mb-2">{label}</p>
      <div
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          dragging
            ? "border-violet-400 bg-violet-500/5"
            : "border-zinc-700 hover:border-zinc-500"
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          multiple
          className="hidden"
          onChange={(e) => {
            const selected = Array.from(e.target.files || []);
            onChange([...files, ...selected]);
            e.target.value = "";
          }}
        />
        {files.length === 0 ? (
          <div>
            <p className="text-zinc-500 text-sm">PDF 파일을 드래그하거나 클릭해서 선택</p>
            <p className="text-zinc-600 text-xs mt-1">여러 파일 동시 선택 가능</p>
          </div>
        ) : (
          <div className="text-left space-y-1">
            {files.map((f, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span className="text-zinc-300 truncate max-w-xs">{f.name}</span>
                <button
                  className="text-zinc-600 hover:text-red-400 ml-2 transition-colors"
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange(files.filter((_, j) => j !== i));
                  }}
                >
                  ✕
                </button>
              </div>
            ))}
            <p className="text-violet-400 text-xs mt-2 pt-2 border-t border-zinc-700">
              + 파일 추가하려면 클릭하거나 드래그
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export default function HypothesisMaker() {
  // State
  const [step, setStep] = useState<Step>("setup");
  const [provider, setProvider] = useState<Provider>("claude");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState(MODELS.claude[0]);
  const [labFiles, setLabFiles] = useState<File[]>([]);
  const [refFiles, setRefFiles] = useState<File[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [labName, setLabName] = useState("");
  const [assignedProject, setAssignedProject] = useState("");
  const [profName, setProfName] = useState("");
  const [profInstructions, setProfInstructions] = useState("");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [progressMsg, setProgressMsg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // ── Helpers ────────────────────────────────────────────────

  const post = async (path: string, body: unknown) => {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  };

  // ── Step handlers ──────────────────────────────────────────

  const handleUpload = async () => {
    if (labFiles.length === 0) { setError("연구실 논문 PDF를 하나 이상 선택하세요."); return; }
    setError("");
    setLoading(true);
    try {
      const form = new FormData();
      labFiles.forEach((f) => form.append("files", f));
      refFiles.forEach((f) => form.append("ref_files", f));
      const res = await fetch(`${API_URL}/api/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error((await res.json()).detail);
      const data = await res.json();
      setSessionId(data.session_id);
      setStep("scan");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleScan = async () => {
    setError("");
    setLoading(true);
    try {
      const data = await post("/api/stage0", {
        session_id: sessionId,
        api_provider: provider,
        api_key: apiKey,
        model,
      });
      setProjects(data.projects || []);
      setLabName(data.lab_name_guess || "");
      setStep("configure");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    setError("");
    setLoading(true);
    setProgress(0);
    setProgressMsg("분석 시작 중...");
    try {
      const data = await post("/api/analyze", {
        session_id: sessionId,
        api_provider: provider,
        api_key: apiKey,
        model,
        assigned_project: assignedProject,
        professor_name: profName,
        professor_instructions: profInstructions,
      });
      setJobId(data.job_id);
      setStep("analyze");

      // SSE progress
      const es = new EventSource(`${API_URL}/api/progress/${data.job_id}`);
      es.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if (d.percent >= 0) setProgress(d.percent);
        setProgressMsg(d.message);
        if (d.done) {
          es.close();
          setLoading(false);
          if (d.error) {
            setError(d.error);
          } else {
            setStep("done");
          }
        }
      };
      es.onerror = () => {
        es.close();
        setLoading(false);
        setError("서버 연결이 끊겼습니다. 다시 시도해주세요.");
      };
    } catch (e) {
      setError(String(e));
      setLoading(false);
    }
  };

  const handleDownload = () => {
    window.open(`${API_URL}/api/download/${jobId}`, "_blank");
  };

  // ── Render ─────────────────────────────────────────────────

  return (
    <>
    <StarBackground />
    <main className="max-w-2xl mx-auto px-6 py-16 relative">
      {/* Back */}
      <Link
        href="/"
        className="inline-flex items-center gap-2 text-zinc-500 hover:text-zinc-300 text-sm mb-10 transition-colors"
      >
        ← 홈으로
      </Link>

      <h1 className="text-3xl font-bold text-zinc-100 mb-2">Hypothesis Maker</h1>
      <p className="text-zinc-500 text-sm mb-10">
        연구실 논문 PDF → AI 분석 → Research Starter Kit (.docx)
      </p>

      <StepBar current={step} />

      {error && (
        <div className="mb-6 p-4 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* ── Step: setup ── */}
      {step === "setup" && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm text-zinc-400 mb-3">AI 제공자</label>
            <div className="grid grid-cols-3 gap-2">
              {(["claude", "openai", "gemini"] as Provider[]).map((p) => (
                <button
                  key={p}
                  onClick={() => { setProvider(p); setModel(MODELS[p][0]); }}
                  className={`py-2.5 px-3 rounded-lg border text-sm font-medium transition-all ${
                    provider === p
                      ? "border-violet-500 bg-violet-500/10 text-violet-300"
                      : "border-zinc-700 text-zinc-500 hover:border-zinc-500"
                  }`}
                >
                  {PROVIDER_LABELS[p]}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-2">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={`${provider === "claude" ? "sk-ant-..." : provider === "openai" ? "sk-..." : "AI..."}`}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors font-mono"
            />
            <p className="text-xs text-zinc-600 mt-1">API 키는 서버에 저장되지 않습니다.</p>
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-2">모델</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 focus:outline-none focus:border-violet-500 transition-colors"
            >
              {MODELS[provider].map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>

          <button
            disabled={!apiKey.trim()}
            onClick={() => { setError(""); setStep("upload"); }}
            className="w-full py-3 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed text-white font-medium transition-colors"
          >
            다음 →
          </button>
        </div>
      )}

      {/* ── Step: upload ── */}
      {step === "upload" && (
        <div className="space-y-6">
          <DropZone
            label="연구실 논문 PDF (필수) — 최근 5년 논문을 모두 올려주세요"
            files={labFiles}
            onChange={setLabFiles}
          />
          <DropZone
            label="교수님 추천 참고 논문 PDF (선택) — 교수님이 별도로 읽어보라고 한 논문"
            files={refFiles}
            onChange={setRefFiles}
          />

          <div className="flex gap-3">
            <button
              onClick={() => setStep("setup")}
              className="py-3 px-5 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300 text-sm transition-all"
            >
              ← 이전
            </button>
            <button
              disabled={labFiles.length === 0 || loading}
              onClick={handleUpload}
              className="flex-1 py-3 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed text-white font-medium transition-colors"
            >
              {loading ? "업로드 중..." : `${labFiles.length}개 파일 업로드 →`}
            </button>
          </div>
        </div>
      )}

      {/* ── Step: scan ── */}
      {step === "scan" && (
        <div className="space-y-6">
          <div className="p-5 rounded-xl bg-zinc-900 border border-zinc-800">
            <p className="text-sm text-zinc-400 mb-1">업로드 완료</p>
            <p className="text-zinc-100 font-medium">
              연구실 논문 {labFiles.length}편
              {refFiles.length > 0 && ` · 참고 논문 ${refFiles.length}편`}
            </p>
          </div>

          <div className="p-5 rounded-xl bg-violet-500/5 border border-violet-500/20">
            <p className="text-sm text-violet-300 font-medium mb-1">Stage 0 — 빠른 스캔</p>
            <p className="text-zinc-500 text-sm">
              논문 제목과 초록만 읽어 연구실 프로젝트 목록을 파악합니다.
              API 비용이 소량 발생합니다.
            </p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => setStep("upload")}
              className="py-3 px-5 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300 text-sm transition-all"
            >
              ← 이전
            </button>
            <button
              disabled={loading}
              onClick={handleScan}
              className="flex-1 py-3 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-30 text-white font-medium transition-colors"
            >
              {loading ? "스캔 중..." : "프로젝트 파악 시작 →"}
            </button>
          </div>
        </div>
      )}

      {/* ── Step: configure ── */}
      {step === "configure" && (
        <div className="space-y-6">
          {labName && (
            <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800">
              <p className="text-xs text-zinc-500 mb-1">추정 연구실 이름</p>
              <p className="text-zinc-200 font-medium">{labName}</p>
            </div>
          )}

          {projects.length > 0 && (
            <div>
              <label className="block text-sm text-zinc-400 mb-3">
                파악된 프로젝트 — 배정받은 프로젝트를 선택하세요 (선택사항)
              </label>
              <div className="space-y-2">
                <label className="flex items-start gap-3 p-3 rounded-lg border border-zinc-700 cursor-pointer hover:border-zinc-500 transition-colors">
                  <input
                    type="radio"
                    name="project"
                    value=""
                    checked={assignedProject === ""}
                    onChange={() => setAssignedProject("")}
                    className="mt-1 accent-violet-500"
                  />
                  <div>
                    <p className="text-sm text-zinc-300 font-medium">없음 / 직접 입력</p>
                    <p className="text-xs text-zinc-600">모든 프로젝트를 균등하게 분석</p>
                  </div>
                </label>
                {projects.map((p) => (
                  <label
                    key={p.id}
                    className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                      assignedProject === p.name
                        ? "border-violet-500/50 bg-violet-500/5"
                        : "border-zinc-700 hover:border-zinc-500"
                    }`}
                  >
                    <input
                      type="radio"
                      name="project"
                      value={p.name}
                      checked={assignedProject === p.name}
                      onChange={() => setAssignedProject(p.name)}
                      className="mt-1 accent-violet-500"
                    />
                    <div>
                      <p className="text-sm text-zinc-200 font-medium">{p.name}</p>
                      <p className="text-xs text-zinc-500 mt-0.5">{p.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm text-zinc-400 mb-2">
              교수님 이름 (선택사항) — 저장될 파일명에 추가됩니다
            </label>
            <input
              type="text"
              value={profName}
              onChange={(e) => setProfName(e.target.value)}
              placeholder="예: 김철수"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm text-zinc-400 mb-2">
              추가 지시사항 (선택사항)
            </label>
            <textarea
              value={profInstructions}
              onChange={(e) => setProfInstructions(e.target.value)}
              placeholder="예: '교수님이 소프트 로봇 그리퍼 쪽을 맡아보라고 하셨어요' 또는 '특히 에너지 효율 관련 가설을 중점적으로 뽑아주세요'"
              rows={3}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors resize-none"
            />
          </div>

          <div className="p-4 rounded-lg bg-amber-500/5 border border-amber-500/20">
            <p className="text-xs text-amber-400 font-medium mb-1">비용 안내</p>
            <p className="text-xs text-zinc-500">
              논문 5편 기준 약 Claude Sonnet $0.5~1 / GPT-4o $1~2 / Gemini Flash $0.1~0.5
            </p>
          </div>

          <div className="flex gap-3">
            <button
              onClick={() => setStep("scan")}
              className="py-3 px-5 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300 text-sm transition-all"
            >
              ← 이전
            </button>
            <button
              onClick={handleAnalyze}
              className="flex-1 py-3 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium transition-colors"
            >
              분석 시작 →
            </button>
          </div>
        </div>
      )}

      {/* ── Step: analyze ── */}
      {step === "analyze" && (
        <div className="space-y-6">
          <div className="p-6 rounded-xl bg-zinc-900 border border-zinc-800">
            <div className="flex items-center justify-between mb-4">
              <p className="text-sm font-medium text-zinc-300">분석 진행 중...</p>
              <p className="text-sm font-mono text-violet-400">{progress}%</p>
            </div>
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden mb-4">
              <div
                className="h-full bg-violet-500 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <p className="text-sm text-zinc-500 min-h-[1.25rem]">{progressMsg}</p>
          </div>

          <div className="p-4 rounded-lg bg-zinc-900/50 border border-zinc-800">
            <p className="text-xs text-zinc-600">
              Stage 2 (가설 생성) 단계에서 1~3분 소요됩니다. 창을 닫지 마세요.
            </p>
          </div>

          {error && (
            <button
              onClick={() => setStep("configure")}
              className="w-full py-3 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 text-sm transition-all"
            >
              ← 다시 시도
            </button>
          )}
        </div>
      )}

      {/* ── Step: done ── */}
      {step === "done" && (
        <div className="space-y-6 text-center">
          <div className="py-12">
            <div className="w-16 h-16 rounded-full bg-violet-500/10 border border-violet-500/30 flex items-center justify-center mx-auto mb-6">
              <span className="text-3xl">✓</span>
            </div>
            <h2 className="text-2xl font-bold text-zinc-100 mb-2">리포트 완성!</h2>
            <p className="text-zinc-500 text-sm">Research Starter Kit이 생성되었습니다.</p>
          </div>

          <button
            onClick={handleDownload}
            className="w-full py-4 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-lg transition-colors"
          >
            Research_Starter_Kit.docx 다운로드
          </button>

          <button
            onClick={() => {
              setStep("setup");
              setLabFiles([]);
              setRefFiles([]);
              setSessionId("");
              setProjects([]);
              setAssignedProject("");
              setProfInstructions("");
              setJobId("");
              setProgress(0);
              setProgressMsg("");
              setError("");
            }}
            className="w-full py-3 rounded-xl border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300 text-sm transition-all"
          >
            처음부터 다시
          </button>

          <p className="text-xs text-zinc-600">
            ⚠ AI 생성 초안입니다. 반드시 교수님 및 선배 연구원의 검토를 받으세요.
          </p>
        </div>
      )}
    </main>
    </>
  );
}
