import Link from "next/link";

export default function HypothesisMakerTesterPage() {
  return (
    <main className="min-h-dvh bg-[#09090b] text-zinc-100">
      <div className="mx-auto flex min-h-dvh max-w-3xl flex-col px-6 py-10">
        <div className="mb-12 flex items-center justify-between">
          <Link
            href="/"
            className="text-sm text-zinc-500 transition-colors hover:text-zinc-300"
          >
            ← 홈으로
          </Link>
          <Link
            href="/en/tools/hypothesis-maker-tester"
            className="border border-zinc-800 px-2 py-1 text-xs font-mono text-zinc-600 transition-colors hover:border-violet-500/40 hover:text-violet-400"
          >
            English
          </Link>
        </div>

        <section className="flex flex-1 flex-col justify-center">
          <p className="mb-3 text-xs font-mono uppercase tracking-widest text-amber-400">
            공사중
          </p>
          <h1 className="mb-4 text-4xl font-bold tracking-tight text-zinc-100">
            Hypothesis Maker Tester
          </h1>
          <p className="max-w-xl text-sm leading-relaxed text-zinc-500">
            대용량 논문 분석을 더 안정적으로 만들기 위한 테스트 페이지를 준비 중입니다.
          </p>
        </section>
      </div>
    </main>
  );
}
