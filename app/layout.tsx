import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Company Data Consolidation",
  description: "Merge master financial data with director/contact data from Drive.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen text-slate-900 antialiased">{children}</body>
    </html>
  );
}
