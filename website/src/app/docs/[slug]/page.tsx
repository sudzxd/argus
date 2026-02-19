import { MDXRemote } from "next-mdx-remote/rsc";
import remarkGfm from "remark-gfm";
import { getDocBySlug, getDocSlugs } from "@/lib/mdx";
import type { Metadata } from "next";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return getDocSlugs().map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const { meta } = getDocBySlug(slug);
  return {
    title: `${meta.title} - Argus Docs`,
    description: meta.description,
  };
}

export default async function DocPage({ params }: PageProps) {
  const { slug } = await params;
  const { content, meta } = getDocBySlug(slug);

  return (
    <article className="docs-prose max-w-3xl">
      <h1>{meta.title}</h1>
      {meta.description && (
        <p className="text-lg text-cream-muted mt-2 mb-8">{meta.description}</p>
      )}
      <MDXRemote source={content} options={{ mdxOptions: { remarkPlugins: [remarkGfm] } }} />
    </article>
  );
}
