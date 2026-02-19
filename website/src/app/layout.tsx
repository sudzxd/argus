import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Argus - AI-Powered PR Reviews",
  description:
    "Code reviews that understand your entire codebase. Argus indexes your repository, retrieves relevant context, and delivers precise inline feedback.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="noise-overlay min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
