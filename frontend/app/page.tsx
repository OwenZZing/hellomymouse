import Link from "next/link";

const tools = [
  {
    slug: "hypothesis-maker",
    name: "Hypothesis Maker",
    description:
      "연구실 논문 PDF를 업로드하면 AI가 분석해 Research Starter Kit (Word 문서)를 생성합니다. 신입 대학원생을 위한 첫 번째 연구 가이드.",
    tags: ["Claude / GPT / Gemini", "PDF 분석", "가설 생성"],
    status: "live",
  },
  {
    slug: null,
    name: "Coming Soon",
    description: "다음 프로젝트를 준비 중입니다.",
    tags: [],
    status: "soon",
  },
  {
    slug: null,
    name: "Coming Soon",
    description: "다음 프로젝트를 준비 중입니다.",
    tags: [],
    status: "soon",
  },
];

export default function Home() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-24">
      {/* Hero */}
      <section className="mb-24">
        <p className="text-violet-400 font-mono text-sm mb-4 tracking-widest uppercase">
          hellomymouse.com
        </p>
        <h1 className="text-5xl font-bold text-zinc-100 mb-4 tracking-tight">
          Hellomymouse
        </h1>
        <p className="text-xl text-zinc-400 mb-6">Ph.D. in Neuroscience</p>
        <p className="text-zinc-500 max-w-xl leading-relaxed">
          연구하면서 만든 것들을 올려두는 곳입니다.
          주로 대학원생에게 필요한 도구들을 만들고 있어요.
        </p>
      </section>

      {/* Divider */}
      <div className="h-px bg-zinc-800 mb-16" />

      {/* Tools */}
      <section>
        <h2 className="text-xs font-mono text-zinc-500 uppercase tracking-widest mb-8">
          Tools
        </h2>
        <div className="grid gap-4">
          {tools.map((tool, i) =>
            tool.status === "live" && tool.slug ? (
              <Link
                key={i}
                href={`/tools/${tool.slug}`}
                className="group block p-6 rounded-xl border border-zinc-800 bg-zinc-900/50 hover:border-violet-500/50 hover:bg-zinc-900 transition-all duration-200"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-lg font-semibold text-zinc-100 group-hover:text-violet-300 transition-colors">
                    {tool.name}
                  </h3>
                  <span className="text-xs font-mono px-2 py-1 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                    live
                  </span>
                </div>
                <p className="text-zinc-400 text-sm leading-relaxed mb-4">
                  {tool.description}
                </p>
                <div className="flex gap-2 flex-wrap">
                  {tool.tags.map((tag) => (
                    <span
                      key={tag}
                      className="text-xs px-2 py-1 rounded-md bg-zinc-800 text-zinc-500"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </Link>
            ) : (
              <div
                key={i}
                className="p-6 rounded-xl border border-zinc-800/50 bg-zinc-900/20 opacity-40"
              >
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-lg font-semibold text-zinc-500">{tool.name}</h3>
                  <span className="text-xs font-mono px-2 py-1 rounded-full bg-zinc-800 text-zinc-600 border border-zinc-700">
                    soon
                  </span>
                </div>
                <p className="text-zinc-600 text-sm">{tool.description}</p>
              </div>
            )
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-24 pt-8 border-t border-zinc-800">
        <p className="text-zinc-600 text-sm font-mono">
          © {new Date().getFullYear()} Hellomymouse
        </p>
      </footer>
    </main>
  );
}
