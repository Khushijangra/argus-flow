import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ARGUS Stream A",
  description: "Vercel frontend for ARGUS Stream A with a Modal FastAPI backend.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
