"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

// ── Star background ───────────────────────────────────────────

const STARS = [
  { name: "@kseo_nkook",    x: 82, y: 12, size: 12, opacity: 0.45, color: "text-gray-600" },
  { name: "@infp_horong",   x: 6,  y: 18, size: 12, opacity: 0.45, color: "text-gray-600" },
  { name: "@eunsuniverse",  x: 55, y: 90, size: 12, opacity: 0.45, color: "text-gray-600" },
  { name: "@금붕어탐사대",  x: 88, y: 75, size: 12, opacity: 0.85, color: "text-amber-300" },
  { name: "@김진영",        x: 15, y: 82, size: 12, opacity: 0.45, color: "text-gray-400" },
  { name: "@체강삼라",      x: 42, y: 8,  size: 12, opacity: 0.45, color: "text-zinc-300" },
];

function StarBackground() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none select-none">
      {STARS.map((s, i) => (
        <span
          key={i}
          className={`absolute font-mono ${s.color}`}
          style={{ left: `${s.x}%`, top: `${s.y}%`, fontSize: `${s.size}px`, opacity: s.opacity }}
        >
          {s.name}
        </span>
      ))}
    </div>
  );
}

// ── Types ─────────────────────────────────────────────────────

type Provider = "claude" | "openai" | "gemini";
type Locale = "ko" | "en";

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

// Per-model output token cap (must mirror backend analyzer/api_client.py::_MAX_TOKENS)
const MODEL_OUTPUT_CAP: Record<string, number> = {
  "claude-sonnet-4-6": 64000,
  "claude-opus-4-6": 32000,
  "claude-haiku-4-5-20251001": 16000,
  "claude-3-5-sonnet-20241022": 8192,
  "gpt-4o": 16384,
  "gpt-4o-mini": 16384,
  "gpt-4-turbo": 4096,
  "o1-mini": 65536,
  "gemini-2.5-flash": 8192,
};

// Empirical: Stage 2A output costs ~2000 tokens per paper + ~4000 fixed
// (hypotheses, intro, capabilities, costs). Returns a safety level so we can
// warn before the user commits to a long-running analyze job.
function estimateCapacity(paperCount: number, model: string) {
  const cap = MODEL_OUTPUT_CAP[model] ?? 8192;
  const estimated = paperCount * 2000 + 4000;
  const ratio = estimated / cap;
  // Max safe paper count for this model (leaves ~15% margin)
  const maxSafe = Math.max(1, Math.floor((cap * 0.85 - 4000) / 2000));
  return { cap, estimated, ratio, maxSafe };
}

const PROVIDER_LABELS: Record<Provider, string> = {
  claude: "Claude (Anthropic)",
  openai: "GPT (OpenAI)",
  gemini: "Gemini (Google)",
};

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB per file
const MAX_TOTAL_SIZE = 500 * 1024 * 1024; // 500 MB total
const MAX_FILE_COUNT = 20;

// ── Copy (i18n) ───────────────────────────────────────────────

const COPY = {
  ko: {
    backHome: "← 홈으로",
    subtitle: "연구실 논문 PDF → AI 분석 → Research Starter Kit (.docx)",
    steps: ["API 설정", "PDF 업로드", "프로젝트 파악", "분석 설정", "분석 중", "완료"],
    geminiWarning: "⚠ Gemini는 학술 논문 분석 시 안전 필터 차단 및 응답 지연(10분+)이 발생할 수 있습니다. Claude 또는 GPT 사용을 권장합니다.",
    apiKeyLabel: "API Key",
    apiKeyNote: "API 키는 서버에 저장되지 않습니다.",
    modelLabel: "모델",
    providerLabel: "AI 제공자",
    nextBtn: "다음 →",
    labFilesLabel: "연구실 논문 PDF (필수) — 최근 5년 논문을 모두 올려주세요 (최대 20편)",
    refFilesLabel: "교수님 추천 참고 논문 PDF (선택) — 교수님이 별도로 읽어보라고 한 논문",
    dropHint: "PDF 파일을 드래그하거나 클릭해서 선택",
    dropMulti: "여러 파일 동시 선택 가능",
    dropAdd: "+ 파일 추가하려면 클릭하거나 드래그",
    prevBtn: "← 이전",
    uploadBtn: (n: number) => `${n}개 파일 업로드 →`,
    uploadingBtn: "업로드 중...",
    uploadRequired: "연구실 논문 PDF를 하나 이상 선택하세요.",
    uploadDoneLabel: "업로드 완료",
    uploadSummary: (lab: number, ref: number) =>
      `연구실 논문 ${lab}편` + (ref > 0 ? ` · 참고 논문 ${ref}편` : ""),
    scanStageLabel: "Stage 0 — 빠른 스캔",
    scanStageDesc: "논문 제목과 초록만 읽어 연구실 프로젝트 목록을 파악합니다. API 비용이 소량 발생합니다.",
    scanBtn: "프로젝트 파악 시작 →",
    scanningBtn: "스캔 중...",
    projectsLabel: "파악된 프로젝트 — 배정받은 프로젝트를 선택하세요 (선택사항)",
    noProjectOption: "없음 / 직접 입력",
    noProjectDesc: "모든 프로젝트를 균등하게 분석",
    labNameLabel: "추정 연구실 이름",
    profNameLabel: "교수님 이름 (선택사항) — 저장될 파일명에 추가됩니다",
    profNamePlaceholder: "예: 김철수",
    bgLevelLabel: "본인의 배경지식 수준",
    bgLevelOptions: ["학부 졸업 (이 분야 처음)", "학부 + 관련 수업 수강", "석사 이상 / 연구 경험 있음"],
    instrLabel: "추가 지시사항 (선택사항)",
    instrPlaceholder: "예: '교수님이 소프트 로봇 그리퍼 쪽을 맡아보라고 하셨어요' 또는 '특히 에너지 효율 관련 가설을 중점적으로 뽑아주세요'",
    costTitle: "비용 안내",
    costDesc: "논문 5편 기준 약 Claude Sonnet $0.5~1 / GPT-4o $1~2 / Gemini Flash $0.1~0.5",
    capacityWarnTitle: (n: number, model: string) => `⚠ 논문 ${n}편 × ${model}`,
    capacityWarnBody: (maxSafe: number) =>
      `선택한 모델의 출력 한도에 가까워 결과가 잘릴 수 있습니다. 논문을 ${maxSafe}편 이하로 줄이거나 Claude Sonnet 4.6(64K 출력) 사용을 권장합니다.`,
    capacityDangerTitle: (n: number, model: string) => `🚫 논문 ${n}편 × ${model} — 실패 가능성 높음`,
    capacityDangerBody: (maxSafe: number) =>
      `이 조합은 거의 확실하게 출력이 잘립니다. 이전 단계로 돌아가 Claude Sonnet 4.6으로 변경하거나 논문을 ${maxSafe}편 이하로 줄여주세요.`,
    analyzeBtn: "분석 시작 →",
    analyzingTitle: "분석 진행 중...",
    analyzeWait: "Stage 2 (가설 생성) 단계에서 1~3분 소요됩니다. 창을 닫지 마세요.",
    retryBtn: "← 다시 시도",
    doneTitle: "리포트 완성!",
    doneDesc: "Research Starter Kit이 생성되었습니다.",
    downloadBtn: "Research_Starter_Kit.docx 다운로드",
    restartBtn: "처음부터 다시",
    disclaimer: "⚠ AI 생성 초안입니다. 반드시 교수님 및 선배 연구원의 검토를 받으세요.",
    connError: "서버 연결이 끊겼습니다. 다시 시도해주세요.",
    langSwitch: "English",
    langSwitchHref: "/en/tools/hypothesis-maker",
    reviewLabel: "리뷰 남기기 — 선택사항",
    reviewDesc: "남겨주신 리뷰가 이 페이지에 표시되어 다른 분들에게 도움이 됩니다.",
    reviewNameLabel: "이름",
    reviewNamePlaceholder: "예: 김철수",
    reviewFieldLabel: "연구 분야",
    reviewFieldPlaceholder: "예: 신경과학, 로봇공학",
    reviewPositionLabel: "소속",
    reviewPositionOptions: ["학부생", "석사과정", "박사과정", "박사"],
    reviewStarsLabel: "별점",
    reviewCommentLabel: "한줄평",
    reviewCommentPlaceholder: "예: 처음 연구실 배정받았는데 너무 막막했는데 큰 도움이 됐어요!",
    reviewSubmitBtn: "리뷰 남기기",
    reviewSubmitted: "리뷰가 등록되었습니다!",
    reviewsTitle: "사용자 리뷰",
    reviewNoReviews: "아직 리뷰가 없습니다.",
    reviewModelLabel: "분석 모델",
  },
  en: {
    backHome: "← Back to Home",
    subtitle: "Lab papers PDF → AI analysis → Research Starter Kit (.docx)",
    steps: ["API Setup", "Upload PDFs", "Scan Projects", "Configure", "Analyzing", "Done"],
    geminiWarning: "⚠ Gemini may trigger safety filter blocks and slow responses (10+ min) on academic papers. Claude or GPT is recommended.",
    apiKeyLabel: "API Key",
    apiKeyNote: "Your API key is never stored on the server.",
    modelLabel: "Model",
    providerLabel: "AI Provider",
    nextBtn: "Next →",
    labFilesLabel: "Lab papers PDF (required) — upload all papers from the last 5 years (max 20)",
    refFilesLabel: "Professor-recommended reference PDFs (optional) — papers your PI asked you to read",
    dropHint: "Drag & drop PDF files here or click to select",
    dropMulti: "Multiple files supported",
    dropAdd: "+ Click or drag to add more files",
    prevBtn: "← Back",
    uploadBtn: (n: number) => `Upload ${n} file${n > 1 ? "s" : ""} →`,
    uploadingBtn: "Uploading...",
    uploadRequired: "Please select at least one lab paper PDF.",
    uploadDoneLabel: "Upload complete",
    uploadSummary: (lab: number, ref: number) =>
      `${lab} lab paper${lab > 1 ? "s" : ""}` + (ref > 0 ? ` · ${ref} reference paper${ref > 1 ? "s" : ""}` : ""),
    scanStageLabel: "Stage 0 — Quick Scan",
    scanStageDesc: "Reads only titles and abstracts to identify lab research projects. Minimal API cost.",
    scanBtn: "Identify Projects →",
    scanningBtn: "Scanning...",
    projectsLabel: "Detected projects — select your assigned project (optional)",
    noProjectOption: "None / Enter manually",
    noProjectDesc: "Analyze all projects equally",
    labNameLabel: "Estimated lab name",
    profNameLabel: "Professor name (optional) — added to the output filename",
    profNamePlaceholder: "e.g. John Smith",
    bgLevelLabel: "Your background level",
    bgLevelOptions: ["Undergrad (new to this field)", "Undergrad + relevant coursework", "Master's+ / research experience"],
    instrLabel: "Additional instructions (optional)",
    instrPlaceholder: "e.g. 'My PI told me to focus on soft robotic grippers' or 'Emphasize energy-efficiency hypotheses'",
    costTitle: "Estimated cost",
    costDesc: "~5 papers: Claude Sonnet $0.5–1 / GPT-4o $1–2 / Gemini Flash $0.1–0.5",
    capacityWarnTitle: (n: number, model: string) => `⚠ ${n} papers × ${model}`,
    capacityWarnBody: (maxSafe: number) =>
      `You're approaching this model's output limit — the JSON response may get truncated. Consider reducing to ${maxSafe} papers or switching to Claude Sonnet 4.6 (64K output).`,
    capacityDangerTitle: (n: number, model: string) => `🚫 ${n} papers × ${model} — very likely to fail`,
    capacityDangerBody: (maxSafe: number) =>
      `This combination will almost certainly truncate. Go back and switch to Claude Sonnet 4.6, or reduce to ${maxSafe} papers or fewer.`,
    analyzeBtn: "Start Analysis →",
    analyzingTitle: "Analysis in progress...",
    analyzeWait: "Stage 2 (hypothesis generation) takes 1–3 minutes. Do not close this window.",
    retryBtn: "← Retry",
    doneTitle: "Report ready!",
    doneDesc: "Your Research Starter Kit has been generated.",
    downloadBtn: "Download Research_Starter_Kit.docx",
    restartBtn: "Start over",
    disclaimer: "⚠ This is an AI-generated draft. Always review with your PI and senior lab members.",
    connError: "Server connection lost. Please try again.",
    langSwitch: "한국어",
    langSwitchHref: "/tools/hypothesis-maker",
    reviewLabel: "Leave a review — optional",
    reviewDesc: "Your review will be displayed on this page to help others.",
    reviewNameLabel: "Name",
    reviewNamePlaceholder: "e.g. Jane Smith",
    reviewFieldLabel: "Research field",
    reviewFieldPlaceholder: "e.g. Neuroscience, Robotics",
    reviewPositionLabel: "Position",
    reviewPositionOptions: ["Undergrad", "Master's", "Ph.D. student", "Ph.D."],
    reviewStarsLabel: "Rating",
    reviewCommentLabel: "One-line review",
    reviewCommentPlaceholder: "e.g. Saved me so much time getting oriented in the lab!",
    reviewSubmitBtn: "Submit review",
    reviewSubmitted: "Review submitted!",
    reviewsTitle: "User reviews",
    reviewNoReviews: "No reviews yet.",
    reviewModelLabel: "Model used",
  },
};

// ── Step indicator ─────────────────────────────────────────────

function StepBar({ current, locale }: { current: Step; locale: Locale }) {
  const STEP_KEYS: Step[] = ["setup", "upload", "scan", "configure", "analyze", "done"];
  const labels = COPY[locale].steps;
  const idx = STEP_KEYS.indexOf(current);
  return (
    <div className="flex items-center gap-1 mb-10 overflow-x-auto pb-1">
      {STEP_KEYS.map((key, i) => (
        <div key={key} className="flex items-center">
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
            {labels[i]}
          </div>
          {i < STEP_KEYS.length - 1 && (
            <div className={`w-4 h-px mx-1 ${i < idx ? "bg-violet-500/40" : "bg-zinc-700"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

// ── Drop zone ─────────────────────────────────────────────────

function DropZone({
  label, files, onChange, locale,
}: {
  label: string; files: File[]; onChange: (f: File[]) => void; locale: Locale;
}) {
  const c = COPY[locale];
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const validateAndAdd = useCallback(
    (newFiles: File[]) => {
      const pdfs = newFiles.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
      const tooLarge = pdfs.find((f) => f.size > MAX_FILE_SIZE);
      if (tooLarge) {
        alert(`파일이 너무 큽니다: ${tooLarge.name} (최대 50MB)`);
        return;
      }
      const combined = [...files, ...pdfs];
      if (combined.length > MAX_FILE_COUNT) {
        alert(`논문은 최대 ${MAX_FILE_COUNT}편까지 업로드할 수 있습니다.`);
        return;
      }
      const totalSize = combined.reduce((s, f) => s + f.size, 0);
      if (totalSize > MAX_TOTAL_SIZE) {
        alert("전체 파일 크기가 500MB를 초과합니다.");
        return;
      }
      onChange(combined);
    },
    [files, onChange]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      validateAndAdd(Array.from(e.dataTransfer.files));
    },
    [validateAndAdd]
  );

  return (
    <div>
      <p className="text-sm text-zinc-400 mb-2">{label}</p>
      <div
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
          dragging ? "border-violet-400 bg-violet-500/5" : "border-zinc-700 hover:border-zinc-500"
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
            validateAndAdd(selected);
            e.target.value = "";
          }}
        />
        {files.length === 0 ? (
          <div>
            <p className="text-zinc-500 text-sm">{c.dropHint}</p>
            <p className="text-zinc-600 text-xs mt-1">{c.dropMulti}</p>
          </div>
        ) : (
          <div className="text-left space-y-1">
            {files.map((f, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span className="text-zinc-300 truncate max-w-xs">{f.name}</span>
                <button
                  className="text-zinc-600 hover:text-red-400 ml-2 transition-colors"
                  onClick={(e) => { e.stopPropagation(); onChange(files.filter((_, j) => j !== i)); }}
                >
                  ✕
                </button>
              </div>
            ))}
            <p className="text-violet-400 text-xs mt-2 pt-2 border-t border-zinc-700">{c.dropAdd}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────

export default function HypothesisMaker({ locale = "ko" }: { locale?: Locale }) {
  const c = COPY[locale];

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
  const [bgLevel, setBgLevel] = useState("beginner");
  const [profInstructions, setProfInstructions] = useState("");
  const [jobId, setJobId] = useState("");
  const [progress, setProgress] = useState(0);
  const [progressMsg, setProgressMsg] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [reviewName, setReviewName] = useState("");
  const [reviewField, setReviewField] = useState("");
  const [reviewStars, setReviewStars] = useState(0);
  const [reviewPosition, setReviewPosition] = useState("");
  const [reviewComment, setReviewComment] = useState("");
  const [existingReviews, setExistingReviews] = useState<
    { name: string; field: string; position: string; stars: number; comment: string; provider: string; model: string }[]
  >([]);
  const [reviewSubmitted, setReviewSubmitted] = useState(false);

  const fetchReviews = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/reviews`);
      if (res.ok) {
        const data = await res.json();
        setExistingReviews(data.reviews ?? []);
      }
    } catch {}
  }, []);

  useEffect(() => { fetchReviews(); }, [fetchReviews]);

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

  const handleUpload = async () => {
    if (labFiles.length === 0) { setError(c.uploadRequired); return; }
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

  const downloadFile = async (id: string) => {
    const res = await fetch(`${API_URL}/api/download/${id}`);
    if (!res.ok) {
      throw new Error(`${res.status}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "Research_Starter_Kit.docx";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleAnalyze = async () => {
    setError("");
    setLoading(true);
    setProgress(0);
    setProgressMsg(locale === "en" ? "Starting analysis..." : "분석 시작 중...");
    try {
      const data = await post("/api/analyze", {
        session_id: sessionId,
        api_provider: provider,
        api_key: apiKey,
        model,
        assigned_project: assignedProject,
        professor_name: profName,
        professor_instructions: profInstructions,
        student_level: bgLevel,
        language: locale,
      });
      setJobId(data.job_id);
      setStep("analyze");

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
            // 자동 다운로드 트리거 (사용자가 자리 비우는 동안 세션 만료 방지)
            downloadFile(data.job_id).catch(() => {
              // 자동 다운로드 실패는 조용히 무시 — 사용자가 수동 버튼으로 재시도 가능
            });
          }
        }
      };
      es.onerror = () => {
        es.close();
        setLoading(false);
        setError(c.connError);
      };
    } catch (e) {
      setError(String(e));
      setLoading(false);
    }
  };

  const handleSubmitReview = async () => {
    const hasReview = reviewName || reviewField || reviewStars || reviewComment;
    if (hasReview && jobId) {
      await fetch(`${API_URL}/api/review/${jobId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          review_name: reviewName,
          review_field: reviewField,
          review_position: reviewPosition,
          review_stars: reviewStars,
          review_comment: reviewComment,
        }),
      });
      setReviewSubmitted(true);
      fetchReviews();
    }
  };

  const handleDownload = async () => {
    try {
      await downloadFile(jobId);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg === "404") {
        setError("다운로드 실패: 분석 세션이 만료되었습니다. 다시 분석해 주세요.");
      } else {
        setError(`다운로드 오류: ${msg}`);
      }
    }
  };

  const handleReset = () => {
    setStep("setup");
    setLabFiles([]); setRefFiles([]); setSessionId(""); setProjects([]);
    setAssignedProject(""); setBgLevel("beginner"); setProfInstructions(""); setJobId("");
    setProgress(0); setProgressMsg(""); setError("");
    setReviewName(""); setReviewField(""); setReviewPosition(""); setReviewStars(0); setReviewComment(""); setReviewSubmitted(false);
  };

  return (
    <>
      <StarBackground />
      <main className="max-w-2xl mx-auto px-6 py-16 relative">
        {/* Top nav */}
        <div className="flex items-center justify-between mb-10">
          <Link
            href={locale === "ko" ? "/" : "/en"}
            className="inline-flex items-center gap-2 text-zinc-500 hover:text-zinc-300 text-sm transition-colors"
          >
            {c.backHome}
          </Link>
          <Link
            href={c.langSwitchHref}
            className="text-xs font-mono text-zinc-600 hover:text-violet-400 transition-colors border border-zinc-800 hover:border-violet-500/40 px-2 py-1 rounded"
          >
            {c.langSwitch}
          </Link>
        </div>

        <h1 className="text-3xl font-bold text-zinc-100 mb-2">Hypothesis Maker</h1>
        <p className="text-zinc-500 text-sm mb-10">{c.subtitle}</p>

        <StepBar current={step} locale={locale} />

        {error && (
          <div className="mb-6 p-4 rounded-lg border border-red-500/30 bg-red-500/10 text-red-400 text-sm">
            {error}
          </div>
        )}

        {/* ── Step: setup ── */}
        {step === "setup" && (
          <div className="space-y-6">
            <div>
              <label className="block text-sm text-zinc-400 mb-3">{c.providerLabel}</label>
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

            {provider === "gemini" && (
              <div className="p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
                <p className="text-xs text-amber-400">{c.geminiWarning}</p>
              </div>
            )}

            <div>
              <label className="block text-sm text-zinc-400 mb-2">{c.apiKeyLabel}</label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={provider === "claude" ? "sk-ant-..." : provider === "openai" ? "sk-..." : "AIza..."}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors font-mono"
              />
              <p className="text-xs text-zinc-600 mt-1">{c.apiKeyNote}</p>
            </div>

            <div>
              <label className="block text-sm text-zinc-400 mb-2">{c.modelLabel}</label>
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 focus:outline-none focus:border-violet-500 transition-colors"
              >
                {MODELS[provider].map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>

            <button
              disabled={!apiKey.trim()}
              onClick={() => { setError(""); setStep("upload"); }}
              className="w-full py-3 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed text-white font-medium transition-colors"
            >
              {c.nextBtn}
            </button>

            {/* ── User reviews ── */}
            {existingReviews.length > 0 && (
              <div className="space-y-3 pt-4 border-t border-zinc-800">
                <h3 className="text-sm font-medium text-zinc-400">{c.reviewsTitle}</h3>
                {existingReviews.slice().reverse().map((r, i) => (
                  <div key={i} className="p-3 rounded-lg border border-zinc-800 bg-zinc-900/50">
                    <div className="flex items-center gap-2 mb-1">
                      {r.stars > 0 && (
                        <span className={`text-sm ${r.stars >= 4 ? "text-amber-400" : "text-zinc-500"}`}>
                          {"★".repeat(r.stars)}{"☆".repeat(5 - r.stars)}
                        </span>
                      )}
                      {r.name && (
                        <span className={`text-xs font-medium ${
                          r.position === "박사" || r.position === "Ph.D." ? "text-amber-400"
                          : r.position === "박사과정" || r.position === "Ph.D. student" ? "text-zinc-300"
                          : r.position === "석사과정" || r.position === "Master's" ? "text-gray-400"
                          : "text-gray-600"
                        }`}>
                          @{r.name}
                        </span>
                      )}
                      {(r.position || r.field) && (
                        <span className="text-xs text-zinc-500">
                          {[r.position, r.field].filter(Boolean).join("  ·  ")}
                        </span>
                      )}
                    </div>
                    {r.comment && <p className="text-sm text-zinc-300">{r.comment}</p>}
                    {(r.provider || r.model) && (
                      <p className="text-xs text-zinc-600 mt-1">
                        {c.reviewModelLabel}: {[r.provider, r.model].filter(Boolean).join(" · ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Step: upload ── */}
        {step === "upload" && (
          <div className="space-y-6">
            <DropZone label={c.labFilesLabel} files={labFiles} onChange={setLabFiles} locale={locale} />
            <DropZone label={c.refFilesLabel} files={refFiles} onChange={setRefFiles} locale={locale} />
            <div className="flex gap-3">
              <button
                onClick={() => setStep("setup")}
                className="py-3 px-5 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300 text-sm transition-all"
              >
                {c.prevBtn}
              </button>
              <button
                disabled={labFiles.length === 0 || loading}
                onClick={handleUpload}
                className="flex-1 py-3 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-30 disabled:cursor-not-allowed text-white font-medium transition-colors"
              >
                {loading ? c.uploadingBtn : c.uploadBtn(labFiles.length)}
              </button>
            </div>
          </div>
        )}

        {/* ── Step: scan ── */}
        {step === "scan" && (
          <div className="space-y-6">
            <div className="p-5 rounded-xl bg-zinc-900 border border-zinc-800">
              <p className="text-sm text-zinc-400 mb-1">{c.uploadDoneLabel}</p>
              <p className="text-zinc-100 font-medium">{c.uploadSummary(labFiles.length, refFiles.length)}</p>
            </div>
            <div className="p-5 rounded-xl bg-violet-500/5 border border-violet-500/20">
              <p className="text-sm text-violet-300 font-medium mb-1">{c.scanStageLabel}</p>
              <p className="text-zinc-500 text-sm">{c.scanStageDesc}</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setStep("upload")}
                className="py-3 px-5 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300 text-sm transition-all"
              >
                {c.prevBtn}
              </button>
              <button
                disabled={loading}
                onClick={handleScan}
                className="flex-1 py-3 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-30 text-white font-medium transition-colors"
              >
                {loading ? c.scanningBtn : c.scanBtn}
              </button>
            </div>
          </div>
        )}

        {/* ── Step: configure ── */}
        {step === "configure" && (
          <div className="space-y-6">
            {labName && (
              <div className="p-4 rounded-lg bg-zinc-900 border border-zinc-800">
                <p className="text-xs text-zinc-500 mb-1">{c.labNameLabel}</p>
                <p className="text-zinc-200 font-medium">{labName}</p>
              </div>
            )}
            {projects.length > 0 && (
              <div>
                <label className="block text-sm text-zinc-400 mb-3">{c.projectsLabel}</label>
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
                      <p className="text-sm text-zinc-300 font-medium">{c.noProjectOption}</p>
                      <p className="text-xs text-zinc-600">{c.noProjectDesc}</p>
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
              <label className="block text-sm text-zinc-400 mb-2">{c.profNameLabel}</label>
              <input
                type="text"
                value={profName}
                onChange={(e) => setProfName(e.target.value)}
                placeholder={c.profNamePlaceholder}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors"
              />
            </div>
            <div>
              <label className="block text-sm text-zinc-400 mb-2">{c.bgLevelLabel}</label>
              <div className="grid grid-cols-3 gap-2">
                {(["beginner", "intermediate", "advanced"] as const).map((lvl, i) => (
                  <button
                    key={lvl}
                    onClick={() => setBgLevel(lvl)}
                    className={`py-2.5 px-2 rounded-lg border text-xs font-medium transition-all ${
                      bgLevel === lvl
                        ? "border-violet-500 bg-violet-500/10 text-violet-300"
                        : "border-zinc-700 text-zinc-500 hover:border-zinc-500"
                    }`}
                  >
                    {c.bgLevelOptions[i]}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-zinc-400 mb-2">{c.instrLabel}</label>
              <textarea
                value={profInstructions}
                onChange={(e) => setProfInstructions(e.target.value)}
                placeholder={c.instrPlaceholder}
                rows={3}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors resize-none"
              />
            </div>
            {/* Capacity warning: raise this before the user commits to a
                multi-minute analyze job with a too-small model. */}
            {(() => {
              const cap = estimateCapacity(labFiles.length, model);
              if (cap.ratio >= 1.0) {
                return (
                  <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/40">
                    <p className="text-sm text-red-400 font-semibold mb-1">
                      {c.capacityDangerTitle(labFiles.length, model)}
                    </p>
                    <p className="text-xs text-red-300/80 leading-relaxed">
                      {c.capacityDangerBody(cap.maxSafe)}
                    </p>
                  </div>
                );
              }
              if (cap.ratio >= 0.75) {
                return (
                  <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/40">
                    <p className="text-sm text-amber-400 font-semibold mb-1">
                      {c.capacityWarnTitle(labFiles.length, model)}
                    </p>
                    <p className="text-xs text-amber-300/80 leading-relaxed">
                      {c.capacityWarnBody(cap.maxSafe)}
                    </p>
                  </div>
                );
              }
              return null;
            })()}
            <div className="p-4 rounded-lg bg-amber-500/5 border border-amber-500/20">
              <p className="text-xs text-amber-400 font-medium mb-1">{c.costTitle}</p>
              <p className="text-xs text-zinc-500">{c.costDesc}</p>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setStep("scan")}
                className="py-3 px-5 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300 text-sm transition-all"
              >
                {c.prevBtn}
              </button>
              <button
                onClick={handleAnalyze}
                className="flex-1 py-3 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium transition-colors"
              >
                {c.analyzeBtn}
              </button>
            </div>
          </div>
        )}

        {/* ── Step: analyze ── */}
        {step === "analyze" && (
          <div className="space-y-6">
            <div className="p-6 rounded-xl bg-zinc-900 border border-zinc-800">
              <div className="flex items-center justify-between mb-4">
                <p className="text-sm font-medium text-zinc-300">{c.analyzingTitle}</p>
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
              <p className="text-xs text-zinc-600">{c.analyzeWait}</p>
            </div>
            {error && (
              <button
                onClick={() => setStep("configure")}
                className="w-full py-3 rounded-lg border border-zinc-700 text-zinc-400 hover:border-zinc-500 text-sm transition-all"
              >
                {c.retryBtn}
              </button>
            )}
          </div>
        )}

        {/* ── Step: done ── */}
        {step === "done" && (
          <div className="space-y-6">
            <div className="py-8 text-center">
              <div className="w-16 h-16 rounded-full bg-violet-500/10 border border-violet-500/30 flex items-center justify-center mx-auto mb-6">
                <span className="text-3xl">✓</span>
              </div>
              <h2 className="text-2xl font-bold text-zinc-100 mb-2">{c.doneTitle}</h2>
              <p className="text-zinc-500 text-sm">{c.doneDesc}</p>
            </div>

            {/* ── Review ── */}
            <div className="p-4 rounded-xl border border-zinc-800 bg-zinc-900/50 space-y-4">
              <div>
                <p className="text-sm text-zinc-300 font-medium mb-1">{c.reviewLabel}</p>
                <p className="text-xs text-zinc-600">{c.reviewDesc}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">{c.reviewNameLabel}</label>
                  <input
                    type="text"
                    value={reviewName}
                    onChange={(e) => setReviewName(e.target.value)}
                    placeholder={c.reviewNamePlaceholder}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>
                <div>
                  <label className="block text-xs text-zinc-500 mb-1">{c.reviewFieldLabel}</label>
                  <input
                    type="text"
                    value={reviewField}
                    onChange={(e) => setReviewField(e.target.value)}
                    placeholder={c.reviewFieldPlaceholder}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-2">{c.reviewPositionLabel}</label>
                <div className="flex gap-2">
                  {c.reviewPositionOptions.map((opt) => (
                    <button
                      key={opt}
                      onClick={() => setReviewPosition(reviewPosition === opt ? "" : opt)}
                      className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                        reviewPosition === opt
                          ? "border-violet-500 bg-violet-500/10 text-violet-300"
                          : "border-zinc-700 text-zinc-500 hover:border-zinc-500"
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-2">{c.reviewStarsLabel}</label>
                <div className="flex gap-2">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button
                      key={n}
                      onClick={() => setReviewStars(reviewStars === n ? 0 : n)}
                      className={`text-2xl transition-colors ${n <= reviewStars ? "text-amber-400" : "text-zinc-700 hover:text-zinc-500"}`}
                    >
                      ★
                    </button>
                  ))}
                  {reviewStars > 0 && (
                    <span className="text-xs text-zinc-600 self-center ml-1">{reviewStars}/5</span>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-xs text-zinc-500 mb-1">{c.reviewCommentLabel}</label>
                <textarea
                  value={reviewComment}
                  onChange={(e) => setReviewComment(e.target.value)}
                  placeholder={c.reviewCommentPlaceholder}
                  rows={2}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-violet-500 transition-colors resize-none"
                />
              </div>
              {reviewSubmitted ? (
                <p className="text-sm text-emerald-400 text-center">{c.reviewSubmitted}</p>
              ) : (
                <button
                  onClick={handleSubmitReview}
                  disabled={!reviewName && !reviewField && !reviewStars && !reviewComment}
                  className="w-full py-2 rounded-lg bg-zinc-700 hover:bg-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed text-zinc-200 text-sm transition-colors"
                >
                  {c.reviewSubmitBtn}
                </button>
              )}
            </div>

            <button
              onClick={handleDownload}
              className="w-full py-4 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-lg transition-colors"
            >
              {c.downloadBtn}
            </button>

            <button
              onClick={handleReset}
              className="w-full py-3 rounded-xl border border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300 text-sm transition-all"
            >
              {c.restartBtn}
            </button>
            <p className="text-xs text-zinc-600 text-center">{c.disclaimer}</p>
          </div>
        )}
      </main>
    </>
  );
}
