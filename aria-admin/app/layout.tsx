import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "ARIA Admin",
  description: "Banking Compliance Intelligence — Admin Dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#0f1117] text-[#e8eaf2] min-h-screen antialiased">
        <div className="flex h-screen overflow-hidden">
          <Nav />
          <main className="flex-1 overflow-y-auto p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
