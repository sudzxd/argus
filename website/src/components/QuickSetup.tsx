"use client";

import { motion } from "framer-motion";
import CodeBlock from "./CodeBlock";

const workflowYaml = `name: Argus PR Review
on:
  pull_request:
    types: [opened, synchronize]

permissions:
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: sudzxd/argus@develop
        with:
          model: >-
            anthropic:claude-sonnet-4-5-20250929
          anthropic_api_key: >-
            \${{ secrets.ANTHROPIC_API_KEY }}`;

export default function QuickSetup() {
  return (
    <section id="setup" className="relative py-32">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5 }}
          >
            <h2
              className="text-3xl md:text-4xl font-bold mb-4"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Up and running in{" "}
              <span className="gradient-text">two minutes</span>
            </h2>
            <p className="text-text-muted mb-6 leading-relaxed">
              Add a single workflow file to your repository and Argus starts
              reviewing every pull request. No servers, no databases, no
              configuration files.
            </p>

            <div className="space-y-4">
              {[
                "Add the workflow YAML to .github/workflows/",
                "Set your LLM API key in repository secrets",
                "Open a pull request and watch Argus review it",
              ].map((step, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: 0.2 + i * 0.1 }}
                  className="flex items-start gap-3"
                >
                  <span
                    className="flex-shrink-0 w-6 h-6 rounded-full bg-gradient-to-br from-violet to-cyan flex items-center justify-center text-xs font-bold text-white"
                  >
                    {i + 1}
                  </span>
                  <span className="text-text-muted text-sm pt-0.5">
                    {step}
                  </span>
                </motion.div>
              ))}
            </div>
          </motion.div>

          <CodeBlock
            code={workflowYaml}
            language="yaml"
            filename=".github/workflows/argus.yml"
          />
        </div>
      </div>
    </section>
  );
}
