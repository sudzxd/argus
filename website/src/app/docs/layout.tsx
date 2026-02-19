import Link from "next/link";
import { getAllDocs } from "@/lib/mdx";
import Navbar from "@/components/Navbar";

export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const docs = getAllDocs();

  return (
    <>
      <Navbar />
      <div className="mx-auto max-w-6xl px-6 pt-24 pb-16">
        <div className="flex gap-10">
          {/* Sidebar */}
          <aside className="hidden md:block w-56 shrink-0">
            <div className="sticky top-24">
              <h3
                className="text-xs uppercase tracking-widest text-cream-dim mb-4"
                style={{ fontFamily: "var(--font-mono)" }}
              >
                Documentation
              </h3>
              <nav className="flex flex-col gap-1">
                {docs.map((doc) => (
                  <Link
                    key={doc.slug}
                    href={`/docs/${doc.slug}`}
                    className="text-sm text-cream-muted hover:text-amber px-3 py-1.5 rounded-md hover:bg-surface/50 transition-all"
                  >
                    {doc.title}
                  </Link>
                ))}
              </nav>
            </div>
          </aside>

          {/* Content */}
          <main className="min-w-0 flex-1">{children}</main>
        </div>
      </div>
    </>
  );
}
