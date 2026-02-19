import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <h1
          className="text-6xl gradient-text mb-4"
          style={{ fontFamily: "var(--font-display)" }}
        >
          404
        </h1>
        <p className="text-cream-muted mb-6">Page not found.</p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg border border-border text-sm text-cream-muted hover:text-cream hover:border-border-light transition-all"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}
