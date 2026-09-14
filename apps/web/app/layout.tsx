import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Volterra — Neural Volatility Surface Lab",
  description: "Implied-volatility surface diagnostics on a log-moneyness / total-variance grid.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
