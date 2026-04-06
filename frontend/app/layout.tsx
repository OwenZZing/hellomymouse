import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hellomymouse",
  description: "Ph.D. in Neuroscience — tools and projects",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#09090b] text-zinc-100">{children}</body>
    </html>
  );
}
