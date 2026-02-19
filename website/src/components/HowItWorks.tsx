"use client";

import { motion } from "framer-motion";

const steps = [
  {
    number: "01",
    title: "Index",
    description:
      "Argus parses your codebase with tree-sitter, building a semantic map of every function, class, and module boundary. Runs once on bootstrap, then incrementally on each push.",
  },
  {
    number: "02",
    title: "Review",
    description:
      "When a PR opens, Argus retrieves the most relevant context for each changed file — call sites, type definitions, related modules — and sends it with the diff to your chosen LLM.",
  },
  {
    number: "03",
    title: "Learn",
    description:
      "After each review cycle, Argus analyzes codebase patterns and conventions. Future reviews reference this memory, getting more accurate over time.",
  },
];

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="relative py-32">
      <div className="relative z-10 mx-auto max-w-6xl px-6">
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
            Three steps to{" "}
            <span className="gradient-text">smarter reviews</span>
          </h2>
          <p className="text-cream-muted max-w-xl mx-auto">
            Set up once, improve continuously. Argus fits into your existing
            GitHub workflow with zero friction.
          </p>
        </motion.div>

        <div className="relative grid md:grid-cols-3 gap-8">
          {/* Connecting amber line (desktop) */}
          <div className="hidden md:block absolute top-16 left-[16.67%] right-[16.67%] h-px">
            <motion.div
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 1, delay: 0.3, ease: "easeOut" }}
              className="h-full bg-gradient-to-r from-amber/40 via-amber/60 to-amber/40 origin-left"
            />
          </div>

          {steps.map((step, i) => (
            <motion.div
              key={step.number}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.15 }}
              className="relative"
            >
              <div className="card rounded-xl p-8 h-full border-t-2 border-t-amber/30 hover:border-t-amber/60 transition-colors">
                <span
                  className="text-5xl text-amber/20 block mb-4"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {step.number}
                </span>
                <h3
                  className="text-2xl font-bold mb-3 text-amber"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {step.title}
                </h3>
                <p className="text-sm text-cream-muted leading-relaxed">
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
