import fs from "fs";
import path from "path";
import matter from "gray-matter";

const contentDir = path.join(process.cwd(), "src", "content");

export interface DocMeta {
  slug: string;
  title: string;
  description: string;
  order: number;
}

export function getDocSlugs(): string[] {
  return fs
    .readdirSync(contentDir)
    .filter((f) => f.endsWith(".mdx"))
    .map((f) => f.replace(/\.mdx$/, ""));
}

export function getDocBySlug(slug: string): {
  content: string;
  meta: DocMeta;
} {
  const filePath = path.join(contentDir, `${slug}.mdx`);
  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = matter(raw);

  return {
    content,
    meta: {
      slug,
      title: (data.title as string) || slug,
      description: (data.description as string) || "",
      order: (data.order as number) || 99,
    },
  };
}

export function getAllDocs(): DocMeta[] {
  return getDocSlugs()
    .map((slug) => getDocBySlug(slug).meta)
    .sort((a, b) => a.order - b.order);
}
