"use client";

import { motion } from "framer-motion";

const steps = [
  {
    number: "01",
    title: "Index",
    description:
      "Argus parses your codebase with tree-sitter, building a semantic map of every function, class, and module boundary. Runs once on bootstrap, then incrementally on each push.",
    color: "text-violet-light",
    borderColor: "border-violet/30",
    glowColor: "shadow-violet/10",
  },
  {
    number: "02",
    title: "Review",
    description:
      "When a PR opens, Argus retrieves the most relevant context for each changed file — call sites, type definitions, related modules — and sends it with the diff to your chosen LLM.",
    color: "text-cyan",
    borderColor: "border-cyan/30",
    glowColor: "shadow-cyan/10",
  },
  {
    number: "03",
    title: "Learn",
    description:
      "After each review cycle, Argus analyzes codebase patterns and conventions. Future reviews reference this memory, getting more accurate over time.",
    color: "text-amber",
    borderColor: "border-amber/30",
    glowColor: "shadow-amber/10",
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="relative py-32">
      {/* Subtle background glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] rounded-full bg-violet/3 blur-[120px]" />

      <div className="relative z-10 mx-auto max-w-6xl px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2
            className="text-3xl md:text-4xl font-bold mb-4"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Three steps to{" "}
            <span className="gradient-text">smarter reviews</span>
          </h2>
          <p className="text-text-muted max-w-xl mx-auto">
            Set up once, improve continuously. Argus fits into your existing
            GitHub workflow with zero friction.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-8">
          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.15 }}
              className="relative"
            >
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="hidden md:block absolute top-12 left-[calc(100%+1rem)] w-[calc(100%-2rem)] h-px bg-gradient-to-r from-border-light to-transparent" />
              )}

              <div
                className={`relative glass rounded-xl p-8 border ${step.borderColor} h-full`}
              >
                <span
                  className={`text-5xl font-extrabold ${step.color} opacity-20 absolute top-4 right-6`}
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {step.number}
                </span>
                <h3
                  className={`text-2xl font-bold mb-3 ${step.color}`}
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {step.title}
                </h3>
                <p className="text-sm text-text-muted leading-relaxed">
                  {step.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
