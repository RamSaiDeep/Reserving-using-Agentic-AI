import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Actuarial Reserving Platform",
  description: "AI-assisted actuarial loss reserving — Chain Ladder, BF, Benktander, Cape Cod, Mack, Case Outstanding, Clark.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full overflow-hidden bg-bg text-text-main font-sans">
        {children}
      </body>
    </html>
  );
}
