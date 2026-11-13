import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: {
    default: "Crashtimate: car repair estimates from a photo",
    template: "%s | Crashtimate",
  },
  description:
    "Upload a photo of a damaged car and get an itemized repair estimate in Canadian dollars, built from Ontario body shop rates.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en-CA" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-line bg-surface">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-3.5 sm:px-6">
            <Link href="/" className="flex items-center gap-2 text-lg font-semibold tracking-tight">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent text-sm text-white">
                C
              </span>
              Crashtimate
            </Link>
            <a
              href="https://github.com/zaidhawk/Crashtimate"
              className="no-print text-sm text-muted hover:text-ink"
            >
              GitHub
            </a>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
          {children}
        </main>
        <footer className="border-t border-line">
          <p className="mx-auto max-w-6xl px-4 py-5 text-xs text-muted sm:px-6">
            Crashtimate gives a planning estimate, not a quote. Shops often find more damage once
            parts come off. Prices are in Canadian dollars and use Ontario shop rates.
          </p>
        </footer>
      </body>
    </html>
  );
}
