import Link from "next/link";

export default function SurgeryTrainerPage() {
  return (
    <main className="min-h-screen bg-[#09090b] text-zinc-100">
      <section className="mx-auto flex max-w-6xl flex-col gap-5 px-4 py-5 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <Link
              href="/"
              className="font-mono text-sm text-zinc-500 transition-colors hover:text-violet-400"
            >
              ← 홈으로
            </Link>
            <p className="mt-4 font-mono text-xs uppercase tracking-widest text-violet-400">
              No-animal training simulator
            </p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-zinc-100 sm:text-4xl">
              마우스 정위수술 트레이너
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-zinc-500">
              교육용 시뮬레이터입니다. 기관 교육, IACUC 승인 프로토콜, 수의학적 지도,
              감독하 실습을 대체하지 않습니다.
            </p>
          </div>
          <Link
            href="/en/tools/surgery-trainer"
            className="rounded border border-zinc-800 px-3 py-1.5 font-mono text-xs text-zinc-500 transition-colors hover:border-violet-500/40 hover:text-violet-400"
          >
            English
          </Link>
        </div>

        <iframe
          title="Mouse Stereotaxic Surgery Trainer"
          src="/surgery-trainer/index.html"
          className="h-[82vh] min-h-[720px] w-full rounded-xl border border-zinc-800 bg-zinc-950"
          sandbox="allow-scripts allow-same-origin"
        />
      </section>
    </main>
  );
}
