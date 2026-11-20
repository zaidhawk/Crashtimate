import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import Image from "next/image";
import Link from "next/link";

import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

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
    <html lang="en-CA" className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <header className="border-b border-line bg-surface">
          <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4 sm:px-6">
            <Link href="/" className="flex items-center gap-2.5" aria-label="Crashtimate home">
              <Image src="/logo.png" alt="" width={41} height={28} priority />
              <span className="text-[17px] font-semibold tracking-tight">Crashtimate</span>
            </Link>
            <a
              href="https://github.com/zaidhawk/Crashtimate"
              className="no-print text-sm text-muted hover:text-ink"
            >
              GitHub
            </a>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
          {children}
        </main>
        <footer className="border-t border-line bg-surface">
          <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <p className="max-w-xl">
              A planning estimate, not a quote. Shops often find more damage once parts come off.
            </p>
            <p className="font-mono">CAD · Ontario shop rates · 13% HST</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
