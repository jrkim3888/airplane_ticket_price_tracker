import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "항공권 가격 트래커",
  description: "항공권 최저가를 추적합니다",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
