import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";

const SITE_URL = "https://www.hellomymouse.com";
// GA4 Measurement ID를 발급받은 후 아래 값을 교체하세요 (예: "G-XXXXXXXXXX")
const GA_MEASUREMENT_ID = "G-H4623GZRNV";

export const metadata: Metadata = {
  title: {
    default: "Hellomymouse — 대학원생을 위한 연구 도구",
    template: "%s | Hellomymouse",
  },
  description:
    "신경과학 박사가 만든 대학원생을 위한 AI 연구 도구 모음. Hypothesis Maker로 논문 PDF를 업로드하면 AI가 가설과 연구 스타터 킷을 생성합니다.",
  metadataBase: new URL(SITE_URL),
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "Hellomymouse",
    title: "Hellomymouse — 대학원생을 위한 연구 도구",
    description:
      "신경과학 박사가 만든 AI 연구 도구 모음. 논문 PDF → 가설 생성 → Research Starter Kit",
    locale: "ko_KR",
  },
  twitter: {
    card: "summary",
    title: "Hellomymouse — 대학원생을 위한 연구 도구",
    description: "논문 PDF를 업로드하면 AI가 연구 가설을 자동 생성합니다.",
  },
  icons: { icon: "/favicon.ico" },
};

const schemaMarkup = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: "Hellomymouse",
      description: "대학원생을 위한 AI 연구 도구 모음",
      inLanguage: ["ko", "en"],
    },
    {
      "@type": "Person",
      "@id": `${SITE_URL}/#author`,
      name: "Kyungri Kim",
      alternateName: "김경리",
      jobTitle: "Postdoctoral Researcher",
      knowsAbout: "Neuroscience",
      email: "kby930@gmail.com",
      url: SITE_URL,
    },
    {
      "@type": "WebApplication",
      "@id": `${SITE_URL}/tools/hypothesis-maker#app`,
      name: "Hypothesis Maker",
      url: `${SITE_URL}/tools/hypothesis-maker`,
      description:
        "연구실 논문 PDF를 업로드하면 AI가 분석해 Research Starter Kit(Word 문서)를 생성하는 도구. 신입 대학원생을 위한 첫 번째 연구 가이드.",
      applicationCategory: "ResearchApplication",
      operatingSystem: "Web",
      isAccessibleForFree: true,
      inLanguage: ["ko", "en"],
      author: { "@id": `${SITE_URL}/#author` },
      isPartOf: { "@id": `${SITE_URL}/#website` },
    },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <head>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schemaMarkup) }}
        />
      </head>
      <body className="min-h-screen bg-[#09090b] text-zinc-100">
        {children}
        {/* Google Analytics GA4 — GA_MEASUREMENT_ID를 실제 값으로 교체하세요 */}
        {GA_MEASUREMENT_ID !== "G-XXXXXXXXXX" && (
          <>
            <Script
              src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`}
              strategy="afterInteractive"
            />
            <Script id="ga4-init" strategy="afterInteractive">
              {`
                window.dataLayer = window.dataLayer || [];
                function gtag(){dataLayer.push(arguments);}
                gtag('js', new Date());
                gtag('config', '${GA_MEASUREMENT_ID}');
              `}
            </Script>
          </>
        )}
      </body>
    </html>
  );
}
