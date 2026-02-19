"use client";

import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-border py-12">
      <div className="mx-auto max-w-6xl px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <div className="relative w-6 h-6">
              <div className="absolute inset-0 rounded-full bg-gradient-to-br from-violet to-cyan opacity-60" />
              <div className="absolute inset-[2px] rounded-full bg-void" />
              <div className="absolute inset-[5px] rounded-full bg-gradient-to-br from-violet to-cyan opacity-40" />
              <div className="absolute inset-[7px] rounded-full bg-void" />
              <div className="absolute inset-[8px] rounded-full bg-cyan/60" />
            </div>
            <span
              className="text-sm font-semibold text-text-muted"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Argus
            </span>
          </div>

          <div className="flex items-center gap-6 text-sm text-text-dim">
            <Link
              href="/docs/getting-started"
              className="hover:text-text-muted transition-colors"
            >
              Docs
            </Link>
            <a
              href="https://github.com/sudzxd/argus"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-text-muted transition-colors"
            >
              GitHub
            </a>

          </div>

          <p className="text-xs text-text-dim">
            Built with purpose. Open source.
          </p>
        </div>
      </div>
    </footer>
  );
}
