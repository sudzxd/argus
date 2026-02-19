"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import Link from "next/link";

const diffLines = [
  { type: "header", text: "src/api/handlers.ts" },
  { type: "hunk", text: "@@ -41,8 +41,12 @@ export async function handlePayment(" },
  { type: "context", num: "41", text: "  const session = await getSession(req);" },
  { type: "context", num: "42", text: "  const amount = parseFloat(req.body.amount);" },
  { type: "removed", num: "43", text: "  await db.charge(session.userId, amount);" },
  { type: "added", num: "43", text: "  const result = await db.charge(session.userId, amount);" },
  { type: "added", num: "44", text: "  if (!result.ok) throw new PaymentError(result);" },
  { type: "context", num: "45", text: "  await db.commit();" },
  { type: "context", num: "46", text: "  return res.json({ success: true });" },
];

const inlineComment = {
  severity: "warning",
  category: "bug",
  body: "db.commit() runs even if charge fails with a non-exception error. Consider moving the commit inside the success branch, or wrapping lines 43-45 in a transaction block.",
  suggestion: `  const result = await db.charge(session.userId, amount);
  if (!result.ok) throw new PaymentError(result);
  await db.commit();`,
};

function PRReviewDemo() {
  const [phase, setPhase] = useState(0); // 0: diff only, 1: show comment

  useEffect(() => {
    const timers = [
      setTimeout(() => setPhase(1), 2500),
      setTimeout(() => {
        setPhase(0);
        // restart cycle
        setTimeout(() => setPhase(1), 2500);
      }, 10000),
    ];
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="rounded-xl overflow-hidden border border-border glow-violet">
      {/* PR header bar */}
      <div className="flex items-center gap-3 px-4 py-3 bg-surface/50 border-b border-border">
        <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
        </svg>
        <span className="text-xs text-text-muted" style={{ fontFamily: "var(--font-mono)" }}>
          PR #142
        </span>
        <span className="text-xs text-text-dim">feat: add payment error handling</span>
        <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-green-500/10 text-green-400 border border-green-500/20">
          +2 -1
        </span>
      </div>

      {/* Diff view */}
      <div className="bg-void text-xs overflow-x-auto" style={{ fontFamily: "var(--font-mono)" }}>
        {diffLines.map((line, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.15, delay: i * 0.08 }}
            className={`px-4 py-0.5 flex ${
              line.type === "header"
                ? "bg-surface/80 text-cyan py-1.5 font-semibold border-b border-border"
                : line.type === "hunk"
                  ? "bg-violet/5 text-violet-light py-1"
                  : line.type === "removed"
                    ? "bg-red-500/8 text-red-300"
                    : line.type === "added"
                      ? "bg-green-500/8 text-green-300"
                      : "text-text-dim"
            }`}
          >
            {line.num && (
              <span className="w-8 text-right mr-3 text-text-dim/50 select-none shrink-0">
                {line.num}
              </span>
            )}
            <span>
              {line.type === "removed" && "- "}
              {line.type === "added" && "+ "}
              {line.text}
            </span>
          </motion.div>
        ))}

        {/* Inline review comment */}
        {phase >= 1 && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className="mx-3 my-2 rounded-lg border border-amber/20 bg-amber/5 overflow-hidden"
          >
            <div className="flex items-center gap-2 px-3 py-2 border-b border-amber/10">
              {/* Argus avatar */}
              <div className="relative w-5 h-5 shrink-0">
                <div className="absolute inset-0 rounded-full bg-gradient-to-br from-violet to-cyan" />
                <div className="absolute inset-[1.5px] rounded-full bg-void" />
                <div className="absolute inset-[3px] rounded-full bg-gradient-to-br from-violet to-cyan opacity-50" />
                <div className="absolute inset-[4.5px] rounded-full bg-void" />
                <div className="absolute inset-[5.5px] rounded-full bg-cyan/70" />
              </div>
              <span className="text-[11px] font-semibold text-text">argus</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber/15 text-amber border border-amber/20">
                {inlineComment.severity}
              </span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-surface text-text-dim border border-border">
                {inlineComment.category}
              </span>
              <span className="ml-auto text-[10px] text-text-dim">line 45</span>
            </div>
            <div className="px-3 py-2">
              <p className="text-[11px] text-text-muted leading-relaxed">
                {inlineComment.body}
              </p>
              <div className="mt-2 rounded bg-green-500/5 border border-green-500/15 px-2 py-1.5">
                <span className="text-[10px] text-green-400/70 block mb-1">Suggested change:</span>
                <pre className="text-[10px] text-green-300 whitespace-pre leading-relaxed">
                  {inlineComment.suggestion}
                </pre>
              </div>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}

export default function Hero() {
  return (
    <section className="relative min-h-screen flex items-center pt-20 overflow-hidden">
      {/* Background effects */}
      <div className="absolute inset-0 grid-bg" />
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[600px] rounded-full bg-violet/5 blur-[120px]" />
      <div className="absolute top-1/3 left-1/4 w-[400px] h-[400px] rounded-full bg-cyan/5 blur-[100px]" />

      <div className="relative z-10 mx-auto max-w-6xl px-6 py-20 grid lg:grid-cols-2 gap-12 items-center">
        {/* Left: Copy */}
        <div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border text-xs text-text-muted mb-6"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            <span className="w-2 h-2 rounded-full bg-cyan animate-pulse" />
            v0.1.0 &mdash; now in beta
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="text-5xl md:text-6xl lg:text-7xl font-extrabold leading-[1.05] tracking-tight mb-6"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Code reviews
            <br />
            that{" "}
            <span className="gradient-text">see everything</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.4 }}
            className="text-lg text-text-muted max-w-md mb-8 leading-relaxed"
          >
            Argus indexes your entire codebase, retrieves relevant context for
            every diff, and delivers precise inline review comments on your pull
            requests.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.5 }}
            className="flex flex-wrap gap-4"
          >
            <Link
              href="/docs/getting-started"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-gradient-to-r from-violet to-cyan text-white font-semibold text-sm hover:opacity-90 transition-opacity"
            >
              Get Started
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 7l5 5m0 0l-5 5m5-5H6"
                />
              </svg>
            </Link>
            <a
              href="https://github.com/sudzxd/argus"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg border border-border text-text-muted hover:text-text hover:border-border-light transition-all text-sm"
            >
              <svg
                className="w-4 h-4"
                fill="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  fillRule="evenodd"
                  d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                  clipRule="evenodd"
                />
              </svg>
              View on GitHub
            </a>
          </motion.div>
        </div>

        {/* Right: Terminal demo */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.4 }}
        >
          <PRReviewDemo />
        </motion.div>
      </div>

      {/* Bottom fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-void to-transparent" />
    </section>
  );
}
