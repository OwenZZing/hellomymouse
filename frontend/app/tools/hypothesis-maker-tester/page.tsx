"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";
type Provider = "claude" | "openai" | "gemini" | "openrouter";
const MODELS: Record<Provider, string[]> = {
  claude: ["claude-opus-4-7", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
  openai: ["gpt-5.2", "gpt-5-mini", "gpt-5-nano", "gpt-4o"],
  gemini: ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
  openrouter: ["openrouter/free"],
};

function safeName(name: string) {
  return name
    .replace(/\.pdf$/i, "")
    .replace(/[^\w가-힣.-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80);
}

function buildPlan(files: File[], batchSize: number) {
  const papers = files.map((file, index) => ({
    index: index + 1,
    filename: file.name,
    md: `paper_${String(index + 1).padStart(2, "0")}_${safeName(file.name)}.md`,
  }));
  const batches = [];
  for (let i = 0; i < papers.length; i += batchSize) {
    batches.push({
      index: batches.length + 1,
      papers: papers.slice(i, i + batchSize),
      md: `batch_${String(batches.length + 1).padStart(2, "0")}_synthesis.md`,
    });
  }
  return { papers, batches };
}

export default function HypothesisMakerTesterPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [batchSize, setBatchSize] = useState(5);
  const [copied, setCopied] = useState(false);
  const [provider, setProvider] = useState<Provider>("claude");
  const [model, setModel] = useState(MODELS.claude[0]);
  const [apiKey, setApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressMsg, setProgressMsg] = useState("");
  const [error, setError] = useState("");
  const [downloadReady, setDownloadReady] = useState(false);

  const plan = useMemo(() => buildPlan(files, batchSize), [files, batchSize]);

  const markdown = useMemo(() => {
    const paperList = plan.papers
      .map(
        (p) => `## ${p.md}

- source_pdf: ${p.filename}
- one_line_summary:
- core_claim:
- key_results:
- materials_and_methods:
- equipment_reagents_software:
- limitations:
- further_studies:
- hypothesis_gap:
- baseline_metric_candidates:
`
      )
      .join("\n");

    const batchList = plan.batches
      .map(
        (b) => `## ${b.md}

Papers:
${b.papers.map((p) => `- ${p.md}`).join("\n")}

Synthesize:
- shared_theme:
- repeated_methods:
- recurring_limitations:
- lab_infrastructure:
- strongest_followup_gaps:
`
      )
      .join("\n");

    return `# Hypothesis Maker Large-Paper Test Plan

PDF count: ${files.length}
Batch size: ${batchSize}
Batch count: ${plan.batches.length}

# Stage 1A - Per-paper Markdown Cache

${paperList || "(PDF를 추가하면 논문별 Markdown 템플릿이 생성됩니다.)"}

# Stage 1B - Batch Synthesis

${batchList || "(PDF를 추가하면 batch synthesis 템플릿이 생성됩니다.)"}

# Stage 2 - Final Input Contract

Final Stage 2 should read only:
${plan.batches.map((b) => `- ${b.md}`).join("\n") || "- batch synthesis files"}

Do not re-send all per-paper analyses into the final hypothesis JSON call.
`;
  }, [batchSize, files.length, plan]);

  const addFiles = (selected: FileList | null) => {
    if (!selected) return;
    const pdfs = Array.from(selected).filter((file) => file.name.toLowerCase().endsWith(".pdf"));
    setFiles((current) => {
      const seen = new Set(current.map((file) => `${file.name}:${file.size}`));
      const next = [...current];
      for (const file of pdfs) {
        const key = `${file.name}:${file.size}`;
        if (!seen.has(key)) next.push(file);
      }
      return next;
    });
  };

  const copyMarkdown = async () => {
    await navigator.clipboard.writeText(markdown);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  };

  const downloadMarkdown = () => {
    const blob = new Blob([markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "hypothesis-maker-large-paper-test-plan.md";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const downloadDocx = async (jobId: string, sessionId: string) => {
    const res = await fetch(`${API_URL}/api/download/${jobId}?session=${encodeURIComponent(sessionId)}`);
    if (!res.ok) throw new Error(`${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "Research_Starter_Kit_TEST.docx";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const runTest = async () => {
    if (!files.length) {
      setError("PDF를 하나 이상 추가하세요.");
      return;
    }
    if (!apiKey.trim()) {
      setError("API key를 입력하세요.");
      return;
    }
    setError("");
    setDownloadReady(false);
    setLoading(true);
    setProgress(0);
    setProgressMsg("PDF 업로드 중...");
    try {
      const form = new FormData();
      files.forEach((file) => form.append("files", file));
      const upload = await fetch(`${API_URL}/api/upload`, { method: "POST", body: form });
      if (!upload.ok) throw new Error((await upload.json()).detail || "업로드 실패");
      const uploaded = await upload.json();

      setProgressMsg("Test mode 분석 시작...");
      const started = await fetch(`${API_URL}/api/analyze-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: uploaded.session_id,
          api_provider: provider,
          api_key: apiKey,
          model,
          batch_size: batchSize,
          language: "ko",
          student_level: "beginner",
        }),
      });
      if (!started.ok) throw new Error((await started.json()).detail || "분석 시작 실패");
      const data = await started.json();
      const es = new EventSource(
        `${API_URL}/api/progress/${data.job_id}?session=${encodeURIComponent(uploaded.session_id)}`
      );
      es.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.percent >= 0) setProgress(msg.percent);
        setProgressMsg(msg.message);
        if (msg.done) {
          es.close();
          setLoading(false);
          if (msg.error) {
            setError(msg.error);
          } else {
            setDownloadReady(true);
            downloadDocx(data.job_id, uploaded.session_id).catch((e) =>
              setError(`자동 다운로드 실패: ${e instanceof Error ? e.message : String(e)}`)
            );
          }
        }
      };
      es.onerror = () => {
        es.close();
        setLoading(false);
        setError("진행 상황 연결이 끊겼습니다. 잠시 후 다시 시도하세요.");
      };
    } catch (e) {
      setLoading(false);
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <main className="min-h-dvh bg-[#09090b] text-zinc-100">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-8 flex items-center justify-between">
          <Link href="/" className="text-sm text-zinc-500 transition-colors hover:text-zinc-300">
            ← 홈으로
          </Link>
          <Link
            href="/en/tools/hypothesis-maker-tester"
            className="border border-zinc-800 px-2 py-1 text-xs font-mono text-zinc-600 transition-colors hover:border-violet-500/40 hover:text-violet-400"
          >
            English
          </Link>
        </div>

        <section className="mb-8">
          <p className="mb-3 text-xs font-mono uppercase tracking-widest text-amber-400">
            tester
          </p>
          <h1 className="mb-3 text-4xl font-bold tracking-tight text-zinc-100">
            Hypothesis Maker Tester
          </h1>
          <p className="max-w-2xl text-sm leading-relaxed text-zinc-500">
            20편짜리 분석을 한 번에 JSON으로 만들지 않고, 논문별 Markdown 캐시와 batch synthesis로
            나누는 구조를 미리 테스트합니다.
          </p>
        </section>

        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <section className="space-y-4">
            <label className="block rounded-lg border border-zinc-800 bg-zinc-900/50 p-5 transition-colors hover:border-violet-500/40">
              <span className="mb-2 block text-sm font-medium text-zinc-300">PDF 추가</span>
              <span className="mb-4 block text-xs leading-relaxed text-zinc-600">
                실행하면 실제 PDF 내용을 읽고, 논문별 Markdown cache와 batch synthesis를 거쳐 docx까지 생성합니다.
              </span>
              <input
                type="file"
                accept="application/pdf,.pdf"
                multiple
                onChange={(e) => addFiles(e.target.files)}
                className="block w-full text-xs text-zinc-500 file:mr-3 file:rounded-md file:border-0 file:bg-violet-600 file:px-3 file:py-2 file:text-xs file:font-medium file:text-white hover:file:bg-violet-500"
              />
            </label>

            <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
              <label className="mb-2 block text-sm font-medium text-zinc-300">Batch size</label>
              <select
                value={batchSize}
                onChange={(e) => setBatchSize(Number(e.target.value))}
                className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-violet-500"
              >
                <option value={3}>3편씩</option>
                <option value={5}>5편씩</option>
                <option value={7}>7편씩</option>
              </select>
            </div>

            <div className="space-y-4 rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
              <div>
                <label className="mb-2 block text-sm font-medium text-zinc-300">AI 제공자</label>
                <select
                  value={provider}
                  onChange={(e) => {
                    const next = e.target.value as Provider;
                    setProvider(next);
                    setModel(MODELS[next][0]);
                  }}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-violet-500"
                >
                  <option value="claude">Claude</option>
                  <option value="openai">OpenAI</option>
                  <option value="gemini">Gemini</option>
                  <option value="openrouter">OpenRouter</option>
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-zinc-300">모델</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-violet-500"
                >
                  {MODELS[provider].map((item) => (
                    <option key={item} value={item}>{item}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-2 block text-sm font-medium text-zinc-300">API key</label>
                <input
                  type="password"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-violet-500"
                  placeholder={provider === "claude" ? "sk-ant-..." : "sk-..."}
                />
              </div>
              <button
                onClick={runTest}
                disabled={loading}
                className="w-full rounded-lg bg-violet-600 py-3 text-sm font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {loading ? "테스트 분석 중..." : "끝까지 테스트 실행"}
              </button>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                <p className="text-xs text-zinc-600">PDF</p>
                <p className="font-mono text-xl text-zinc-100">{files.length}</p>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                <p className="text-xs text-zinc-600">Batch</p>
                <p className="font-mono text-xl text-zinc-100">{plan.batches.length}</p>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                <p className="text-xs text-zinc-600">Mode</p>
                <p className="font-mono text-xl text-zinc-100">{files.length > 8 ? "large" : "basic"}</p>
              </div>
            </div>

            {files.length > 0 && (
              <button
                onClick={() => setFiles([])}
                className="w-full rounded-lg border border-zinc-800 py-2 text-sm text-zinc-500 transition-colors hover:border-zinc-600 hover:text-zinc-300"
              >
                파일 목록 비우기
              </button>
            )}
          </section>

          <section className="min-w-0 space-y-4">
            {(loading || progressMsg || error || downloadReady) && (
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-medium text-zinc-300">실행 상태</p>
                  <p className="font-mono text-sm text-violet-400">{progress}%</p>
                </div>
                <div className="mb-3 h-2 overflow-hidden rounded-full bg-zinc-800">
                  <div className="h-full rounded-full bg-violet-500 transition-all" style={{ width: `${progress}%` }} />
                </div>
                {progressMsg && <p className="text-sm text-zinc-500">{progressMsg}</p>}
                {downloadReady && <p className="mt-2 text-sm text-emerald-400">완료되었습니다. docx가 자동 다운로드됩니다.</p>}
                {error && <p className="mt-2 rounded-md border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
              </div>
            )}

            <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-zinc-200">생성될 중간 산출물</h2>
                <div className="flex gap-2">
                  <button
                    onClick={copyMarkdown}
                    className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:border-violet-500/50 hover:text-violet-300"
                  >
                    {copied ? "복사됨" : "Markdown 복사"}
                  </button>
                  <button
                    onClick={downloadMarkdown}
                    className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-500"
                  >
                    다운로드
                  </button>
                </div>
              </div>

              <div className="mb-5 space-y-2">
                {plan.batches.length === 0 ? (
                  <p className="rounded-md border border-dashed border-zinc-800 p-4 text-sm text-zinc-600">
                    PDF를 추가하면 batch 구조가 여기에 표시됩니다.
                  </p>
                ) : (
                  plan.batches.map((batch) => (
                    <div key={batch.md} className="rounded-md border border-zinc-800 bg-zinc-950/60 p-3">
                      <p className="mb-2 font-mono text-xs text-amber-400">{batch.md}</p>
                      <div className="space-y-1">
                        {batch.papers.map((paper) => (
                          <p key={paper.md} className="truncate font-mono text-xs text-zinc-500">
                            {paper.md}
                          </p>
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>

              <textarea
                value={markdown}
                readOnly
                className="h-[420px] w-full resize-none rounded-md border border-zinc-800 bg-zinc-950 p-4 font-mono text-xs leading-relaxed text-zinc-400 outline-none"
              />
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
