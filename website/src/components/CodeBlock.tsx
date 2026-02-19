"use client";

import { motion } from "framer-motion";
import { useState } from "react";

interface CodeBlockProps {
  code: string;
  language?: string;
  filename?: string;
}

interface TokenSpan {
  text: string;
  className: string;
}

function tokenizeYaml(line: string): TokenSpan[] {
  const spans: TokenSpan[] = [];

  // Comment lines
  if (line.trimStart().startsWith("#")) {
    return [{ text: line, className: "text-text-dim italic" }];
  }

  // Empty lines
  if (line.trim() === "") {
    return [{ text: line || " ", className: "" }];
  }

  const leadingWhitespace = line.match(/^(\s*)/)?.[1] || "";
  let rest = line.slice(leadingWhitespace.length);

  if (leadingWhitespace) {
    spans.push({ text: leadingWhitespace, className: "" });
  }

  // "- " list prefix
  if (rest.startsWith("- ")) {
    spans.push({ text: "- ", className: "text-text-dim" });
    rest = rest.slice(2);
  }

  // Key: value pairs
  const kvMatch = rest.match(/^([a-zA-Z_][a-zA-Z0-9_-]*)(:)(.*)/);
  if (kvMatch) {
    const [, key, colon, value] = kvMatch;
    spans.push({ text: key, className: "text-cyan" });
    spans.push({ text: colon, className: "text-text-dim" });

    if (value.trim()) {
      const val = value;
      // Booleans
      if (val.trim() === "true" || val.trim() === "false") {
        spans.push({ text: val, className: "text-amber" });
      }
      // Numbers
      else if (/^\s*\d+(\.\d+)?$/.test(val)) {
        spans.push({ text: val, className: "text-amber" });
      }
      // Strings with ${{ }}
      else if (val.includes("${{")) {
        const exprMatch = val.match(/^(.*?)(\$\{\{.*?\}\})(.*)/);
        if (exprMatch) {
          const [, before, expr, after] = exprMatch;
          if (before) spans.push({ text: before, className: "text-green-400" });
          spans.push({ text: expr, className: "text-violet-light" });
          if (after) spans.push({ text: after, className: "text-green-400" });
        } else {
          spans.push({ text: val, className: "text-green-400" });
        }
      }
      // Arrays [...]
      else if (val.trim().startsWith("[")) {
        spans.push({ text: val, className: "text-amber" });
      }
      // Regular string values
      else {
        spans.push({ text: val, className: "text-green-400" });
      }
    }
    return spans;
  }

  // Fallback — bare values (like "uses: ..." already handled, list items, etc.)
  spans.push({ text: rest, className: "text-text-muted" });
  return spans;
}

export default function CodeBlock({
  code,
  language = "yaml",
  filename,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const lines = code.split("\n");

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5 }}
      className="rounded-xl overflow-hidden border border-border glow-violet group"
    >
      {/* Title bar */}
      <div className="flex items-center gap-2 px-4 py-3 bg-surface/50 border-b border-border">
        <div className="flex gap-1.5">
          <div className="w-3 h-3 rounded-full bg-red-500/60" />
          <div className="w-3 h-3 rounded-full bg-amber/60" />
          <div className="w-3 h-3 rounded-full bg-green-500/60" />
        </div>
        {filename && (
          <span className="ml-2 text-xs text-text-dim">
            {filename}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {language && (
            <span className="text-[10px] text-text-dim uppercase tracking-wider px-1.5 py-0.5 rounded bg-surface border border-border">
              {language}
            </span>
          )}
          <button
            onClick={handleCopy}
            className="text-text-dim hover:text-text transition-colors opacity-0 group-hover:opacity-100 p-1"
            title="Copy to clipboard"
          >
            {copied ? (
              <svg className="w-4 h-4 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Code content */}
      <div className="bg-void overflow-x-auto">
        <pre className="text-xs leading-[1.7]">
          {lines.map((line, i) => {
            const tokens = tokenizeYaml(line);
            return (
              <div
                key={i}
                className="px-4 hover:bg-white/[0.02] transition-colors flex"
              >
                <span className="w-8 text-right mr-4 text-text-dim/30 select-none shrink-0 text-xs leading-[1.85]">
                  {i + 1}
                </span>
                <span>
                  {tokens.map((token, j) => (
                    <span key={j} className={token.className}>
                      {token.text}
                    </span>
                  ))}
                </span>
              </div>
            );
          })}
        </pre>
      </div>
    </motion.div>
  );
}
