"use client";

import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-border py-12">
      <div className="mx-auto max-w-6xl px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            {/* Eye logo */}
            <svg width="22" height="22" viewBox="0 0 32 32" fill="none">
              <path
                d="M2 16C2 16 8 6 16 6C24 6 30 16 30 16C30 16 24 26 16 26C8 26 2 16 2 16Z"
                stroke="#e8a838"
                strokeWidth="1.5"
                fill="rgba(232,168,56,0.06)"
              />
              <circle cx="16" cy="16" r="5" stroke="#e8a838" strokeWidth="1.5" fill="rgba(232,168,56,0.1)" />
              <circle cx="16" cy="16" r="2" fill="#e8a838" />
            </svg>
            <span
              className="text-sm text-cream-muted"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Argus
            </span>
          </div>

          <div className="flex items-center gap-6 text-sm text-cream-dim">
            <Link
              href="/docs/getting-started"
              className="hover:text-amber transition-colors"
            >
              Docs
            </Link>
            <a
              href="https://github.com/sudzxd/argus"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-amber transition-colors"
            >
              GitHub
            </a>
          </div>

          <p
            className="text-xs text-cream-dim italic"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Named after Argus Panoptes &mdash; the many-eyed giant.
          </p>
        </div>
      </div>
    </footer>
  );
}
