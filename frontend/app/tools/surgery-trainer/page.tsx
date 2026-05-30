import Link from "next/link";

export default function SurgeryTrainerPage() {
  return (
    <main className="min-h-screen bg-[#fff7fb] text-[#35253a]">
      <section className="mx-auto flex max-w-6xl flex-col gap-5 px-4 py-5 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3 rounded-lg border-4 border-[#35253a] bg-[#fffef8] p-5 shadow-[6px_6px_0_#ff7da9]">
          <div>
            <Link
              href="/"
              className="font-mono text-sm font-bold text-[#705d75] transition-colors hover:text-[#ff4f87]"
            >
              ← 홈으로
            </Link>
            <p className="mt-4 inline-flex rounded-lg border-2 border-[#35253a] bg-[#ffd166] px-3 py-1 font-mono text-xs font-black uppercase tracking-widest text-[#35253a] shadow-[3px_3px_0_#35253a]">
              Mouse mission arcade
            </p>
            <h1 className="mt-3 text-4xl font-black tracking-tight text-[#35253a] [text-shadow:2px_2px_0_#ffd166,4px_4px_0_rgba(75,192,200,.55)] sm:text-5xl">
              마우스 미션 아케이드
            </h1>
            <p className="mt-3 max-w-3xl text-sm font-bold leading-relaxed text-[#604b64]">
              동물 없이 연습하는 귀여운 정위수술 미니게임입니다. 실제 교육, IACUC 승인 프로토콜, 수의학적 지도,
              감독하 실습을 대체하지 않습니다.
            </p>
          </div>
          <Link
            href="/en/tools/surgery-trainer"
            className="rounded-lg border-2 border-[#35253a] bg-white px-3 py-1.5 font-mono text-xs font-black text-[#35253a] shadow-[3px_3px_0_#35253a] transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5"
          >
            English
          </Link>
        </div>

        <iframe
          title="Mouse Mission Arcade"
          src="/surgery-trainer/index.html"
          className="h-[82vh] min-h-[720px] w-full rounded-lg border-4 border-[#35253a] bg-white shadow-[8px_8px_0_#35253a]"
          sandbox="allow-scripts allow-same-origin"
        />
      </section>
    </main>
  );
}
