"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

// ── Average rating ───────────────────────────────────────────

function AvgRating() {
  const [avg, setAvg] = useState<number | null>(null);
  const [count, setCount] = useState(0);

  useEffect(() => {
    fetch(`${API_URL}/api/reviews`)
      .then((r) => r.json())
      .then((d) => {
        const reviews = d.reviews ?? [];
        const withStars = reviews.filter((r: { stars: number }) => r.stars > 0);
        if (withStars.length > 0) {
          const sum = withStars.reduce((s: number, r: { stars: number }) => s + r.stars, 0);
          setAvg(Math.round((sum / withStars.length) * 10) / 10);
          setCount(withStars.length);
        }
      })
      .catch(() => {});
  }, []);

  if (avg === null) return null;

  return (
    <div className="flex items-center gap-1.5 mt-3">
      <span className="text-amber-400 text-sm">
        {"★".repeat(Math.round(avg))}{"☆".repeat(5 - Math.round(avg))}
      </span>
      <span className="text-zinc-400 text-sm font-medium">{avg}</span>
      <span className="text-zinc-600 text-xs">({count}개 리뷰)</span>
    </div>
  );
}

// ── View counter (홈페이지 조회수) ──────────────────────────

function ViewCounter() {
  const [views, setViews] = useState<number | null>(null);

  useEffect(() => {
    const key = "hmm_view_counted";
    const alreadyCounted = sessionStorage.getItem(key);

    const readOnly = () =>
      fetch(`${API_URL}/api/widget`)
        .then((r) => r.json())
        .then((d) => setViews(d.view_count ?? 0))
        .catch(() => {});

    if (alreadyCounted) {
      readOnly();
    } else {
      fetch(`${API_URL}/api/widget/view`, { method: "POST" })
        .then((r) => r.json())
        .then((d) => {
          sessionStorage.setItem(key, "1");
          setViews(d.view_count ?? 0);
        })
        .catch(readOnly);
    }
  }, []);

  if (views === null || views === 0) return null;
  return (
    <span className="text-zinc-700">
      {" · "}
      {views.toLocaleString()} views
    </span>
  );
}

// ── Usage count (누적 사용자) ─────────────────────────────────

function UsageCount() {
  const [count, setCount] = useState<number | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/api/widget`)
      .then((r) => r.json())
      .then((d) => setCount(d.usage_count ?? 0))
      .catch(() => {});
  }, []);

  if (count === null || count === 0) return null;

  return (
    <p className="text-xs text-zinc-500 mt-3 font-mono">
      지금까지{" "}
      <span className="text-violet-400 font-semibold">{count.toLocaleString()}</span>
      명이 사용했습니다!
    </p>
  );
}

// ── Tools ─────────────────────────────────────────────────────

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

// ── Recent Commits ────────────────────────────────────────────

interface Commit {
  sha: string;
  commit: { message: string; author: { date: string } };
}

function timeAgo(dateStr: string) {
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function RecentCommits() {
  const [commits, setCommits] = useState<Commit[]>([]);

  useEffect(() => {
    fetch("https://api.github.com/repos/OwenZZing/hellomymouse/commits?per_page=5")
      .then((r) => r.json())
      .then(setCommits)
      .catch(() => {});
  }, []);

  if (!commits.length) return null;

  return (
    <div className="mb-4">
      <p className="text-xs font-mono text-zinc-500 uppercase tracking-widest mb-2">
        Recent commits
      </p>
      <div className="space-y-2">
        {commits.map((c) => (
          <div key={c.sha} className="flex items-baseline gap-3 font-mono text-xs">
            <span className="text-zinc-600 w-16 shrink-0">
              {timeAgo(c.commit.author.date)}
            </span>
            <span className="text-violet-500">hypothesis-maker</span>
            <span className="text-zinc-500 truncate">
              {c.commit.message.split("\n")[0]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Stair Widget ──────────────────────────────────────────────

function StairWidget() {
  const [stairs, setStairs] = useState<number | null>(null);
  const [buttonCount, setButtonCount] = useState(0);
  const [pressed, setPressed] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/api/widget`)
      .then((r) => r.json())
      .then((d) => {
        setStairs(d.stairs);
        setButtonCount(d.button_count);
      })
      .catch(() => {});
  }, []);

  const handlePress = async () => {
    if (pressed) return;
    setPressed(true);
    setButtonCount((n) => n + 1);
    await fetch(`${API_URL}/api/widget/button`, { method: "POST" }).catch(() => {});
  };

  return (
    <div className="mb-10 px-4 py-2.5 rounded-xl border border-zinc-800 bg-zinc-900/40 flex items-center justify-between gap-3 flex-wrap">
      <p className="text-sm text-zinc-400 font-mono">
        🐭 오늘 오른 계단 <span className="text-zinc-100 font-bold">{stairs === null ? "-" : stairs === 0 ? "아직 0층 🥲" : `${stairs}층`}</span>
      </p>
      <div className="flex items-center gap-2">
        <button
          onClick={handlePress}
          disabled={pressed}
          className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
            pressed
              ? "text-violet-400 cursor-default"
              : "text-zinc-500 hover:text-violet-400 border border-zinc-700 hover:border-violet-500/40"
          }`}
        >
          {pressed ? "✓ 눌렀어요" : "박사님 운동하세요! 🔔"}
        </button>
        <span className="text-xs text-zinc-600 font-mono">{buttonCount}명</span>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────

export default function Home() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-6">
      {/* Hero */}
      <section className="mb-4">
        <div className="flex items-center justify-between">
          <p className="text-violet-400 font-mono text-sm mb-1 tracking-widest uppercase">
            hellomymouse.com
          </p>
          <Link
            href="/en"
            className="text-xs font-mono text-zinc-600 hover:text-violet-400 transition-colors border border-zinc-800 hover:border-violet-500/40 px-2 py-1 rounded"
          >
            English
          </Link>
        </div>
        <h1 className="text-5xl font-bold text-zinc-100 mb-1 tracking-tight">
          Hellomymouse
        </h1>
        <p className="text-xl text-zinc-400 mb-2">Kyungri Kim · Ph.D. in Neuroscience</p>
        <p className="text-zinc-500 max-w-xl leading-relaxed">
          연구하면서 만든 것들을 올려두는 곳입니다.
          주로 대학원생에게 필요한 도구들을 만들고 있어요.
        </p>
        <p className="text-amber-400 font-mono text-sm mt-1 italic">
          Ruptis Claustris, Scientia Omnibus
          <span className="text-amber-500 not-italic ml-2">— 닫힌 벽을 부수고, 지식을 모두에게</span>
        </p>
        <div className="flex gap-4 mt-2">
          <a
            href="mailto:kby930@gmail.com"
            className="text-sm text-zinc-500 hover:text-violet-400 transition-colors font-mono"
          >
            kby930@gmail.com
          </a>
          <span className="text-zinc-700">·</span>
          <a
            href="https://www.threads.net/@hellmomymouse"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-zinc-500 hover:text-violet-400 transition-colors font-mono"
          >
            @hellmomymouse
          </a>
        </div>
      </section>

      {/* Divider */}
      <div className="h-px bg-zinc-800 mb-4" />

      {/* Stair Widget */}
      <StairWidget />

      {/* Recent Commits */}
      <RecentCommits />

      {/* Divider */}
      <div className="h-px bg-zinc-800 mb-4" />

      {/* Tools */}
      <section>
        <h2 className="text-xs font-mono text-zinc-500 uppercase tracking-widest mb-3">
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
                <div className="flex items-center gap-3 flex-wrap">
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
                  {tool.slug === "hypothesis-maker" && <AvgRating />}
                </div>
                {tool.slug === "hypothesis-maker" && <UsageCount />}
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
      <footer className="mt-6 pt-4 border-t border-zinc-800">
        <p className="text-zinc-600 text-sm font-mono">
          © {new Date().getFullYear()} Hellomymouse
          <ViewCounter />
        </p>
      </footer>
    </main>
  );
}
