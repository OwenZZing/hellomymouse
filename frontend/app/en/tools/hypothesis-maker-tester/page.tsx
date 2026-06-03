import Link from "next/link";

export default function HypothesisMakerTesterPageEN() {
  return (
    <main className="min-h-dvh bg-[#09090b] text-zinc-100">
      <div className="mx-auto flex min-h-dvh max-w-3xl flex-col px-6 py-10">
        <div className="mb-12 flex items-center justify-between">
          <Link
            href="/en"
            className="text-sm text-zinc-500 transition-colors hover:text-zinc-300"
          >
            ← Back
          </Link>
          <Link
            href="/tools/hypothesis-maker-tester"
            className="border border-zinc-800 px-2 py-1 text-xs font-mono text-zinc-600 transition-colors hover:border-violet-500/40 hover:text-violet-400"
          >
            한국어
          </Link>
        </div>

        <section className="flex flex-1 flex-col justify-center">
          <p className="mb-3 text-xs font-mono uppercase tracking-widest text-amber-400">
            Under construction
          </p>
          <h1 className="mb-4 text-4xl font-bold tracking-tight text-zinc-100">
            Hypothesis Maker Tester
          </h1>
          <p className="max-w-xl text-sm leading-relaxed text-zinc-500">
            A tester page for making large-paper analysis more reliable is being prepared.
          </p>
        </section>
      </div>
    </main>
  );
}
