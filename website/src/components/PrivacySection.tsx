"use client";

import { motion } from "framer-motion";
import GlassCard from "./GlassCard";

const privacyCards = [
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
      </svg>
    ),
    title: "Stored in your repo",
    description:
      "Codebase map, pattern memory, and embedding indices all live on an argus-data orphan branch in your repository — pushed via the Git Data API. No external databases, no third-party storage.",
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
    title: "What leaves (and where)",
    description:
      "Only the diff and selected context snippets are sent to your chosen LLM provider for review generation. No full source files are ever transmitted. You pick the provider — Anthropic, OpenAI, or Google.",
  },
  {
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
      </svg>
    ),
    title: "What doesn't exist",
    description:
      "No Argus servers. No external databases. No telemetry. No user accounts. No data retention. Argus is a GitHub Action that runs in your CI environment and stores artifacts in your repository.",
  },
];

export default function PrivacySection() {
  return (
    <section id="privacy" className="relative py-32">
      <div className="mx-auto max-w-6xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-20"
        >
          <h2
            className="text-3xl md:text-4xl font-bold mb-4"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Your code{" "}
            <span className="gradient-text">stays yours</span>
          </h2>
          <p className="text-cream-muted max-w-xl mx-auto">
            Argus has no backend, no accounts, and no data collection.
            Everything lives in your repository.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          {privacyCards.map((card, i) => (
            <GlassCard key={card.title} delay={i * 0.1}>
              <div className="text-amber mb-4">
                {card.icon}
              </div>
              <h3
                className="text-lg font-semibold mb-2 text-cream"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {card.title}
              </h3>
              <p className="text-sm text-cream-muted leading-relaxed">
                {card.description}
              </p>
            </GlassCard>
          ))}
        </div>
      </div>
    </section>
  );
}
