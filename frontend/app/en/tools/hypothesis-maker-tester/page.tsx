"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

function safeName(name: string) {
  return name
    .replace(/\.pdf$/i, "")
    .replace(/[^\w.-]+/g, "_")
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

export default function HypothesisMakerTesterPageEN() {
  const [files, setFiles] = useState<File[]>([]);
  const [batchSize, setBatchSize] = useState(5);
  const [copied, setCopied] = useState(false);

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

${paperList || "(Add PDFs to generate per-paper Markdown templates.)"}

# Stage 1B - Batch Synthesis

${batchList || "(Add PDFs to generate batch synthesis templates.)"}

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

  return (
    <main className="min-h-dvh bg-[#09090b] text-zinc-100">
      <div className="mx-auto max-w-5xl px-6 py-10">
        <div className="mb-8 flex items-center justify-between">
          <Link href="/en" className="text-sm text-zinc-500 transition-colors hover:text-zinc-300">
            ← Back
          </Link>
          <Link
            href="/tools/hypothesis-maker-tester"
            className="border border-zinc-800 px-2 py-1 text-xs font-mono text-zinc-600 transition-colors hover:border-violet-500/40 hover:text-violet-400"
          >
            한국어
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
            Test a large-paper pipeline that splits PDFs into per-paper Markdown caches and batch
            synthesis files before the final hypothesis JSON call.
          </p>
        </section>

        <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
          <section className="space-y-4">
            <label className="block rounded-lg border border-zinc-800 bg-zinc-900/50 p-5 transition-colors hover:border-violet-500/40">
              <span className="mb-2 block text-sm font-medium text-zinc-300">Add PDFs</span>
              <span className="mb-4 block text-xs leading-relaxed text-zinc-600">
                This tester does not read file contents yet. It builds a batch plan and Markdown
                templates from filenames.
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
                <option value={3}>3 papers</option>
                <option value={5}>5 papers</option>
                <option value={7}>7 papers</option>
              </select>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                <p className="text-xs text-zinc-600">PDFs</p>
                <p className="font-mono text-xl text-zinc-100">{files.length}</p>
              </div>
              <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-3">
                <p className="text-xs text-zinc-600">Batches</p>
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
                Clear files
              </button>
            )}
          </section>

          <section className="min-w-0 space-y-4">
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <h2 className="text-sm font-semibold text-zinc-200">Generated intermediate files</h2>
                <div className="flex gap-2">
                  <button
                    onClick={copyMarkdown}
                    className="rounded-md border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:border-violet-500/50 hover:text-violet-300"
                  >
                    {copied ? "Copied" : "Copy Markdown"}
                  </button>
                  <button
                    onClick={downloadMarkdown}
                    className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-500"
                  >
                    Download
                  </button>
                </div>
              </div>

              <div className="mb-5 space-y-2">
                {plan.batches.length === 0 ? (
                  <p className="rounded-md border border-dashed border-zinc-800 p-4 text-sm text-zinc-600">
                    Add PDFs to show the batch structure here.
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
