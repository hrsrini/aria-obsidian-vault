"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  { href: "/documents",   label: "Documents",   icon: "📄" },
  { href: "/health",      label: "Graph Health", icon: "🔬" },
  { href: "/tests",       label: "Test Console", icon: "🧪" },
  { href: "/corrections", label: "Corrections",  icon: "✏️" },
  { href: "/sync",        label: "Sync",         icon: "🔄" },
];

export default function Nav() {
  const pathname = usePathname();
  return (
    <aside className="w-52 shrink-0 bg-[#1a1d27] border-r border-[#2e3348] flex flex-col">
      <div className="px-4 py-5 border-b border-[#2e3348]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-indigo-600 rounded-md flex items-center justify-center text-xs font-bold">AR</div>
          <div>
            <div className="text-sm font-semibold">ARIA Admin</div>
            <div className="text-[10px] text-[#7b82a0]">Compliance Ops</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 py-3 px-2 flex flex-col gap-1">
        {links.map(l => (
          <Link
            key={l.href}
            href={l.href}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors
              ${pathname.startsWith(l.href)
                ? "bg-indigo-600/20 text-indigo-300 font-medium"
                : "text-[#7b82a0] hover:text-[#e8eaf2] hover:bg-[#22263a]"
              }`}
          >
            <span>{l.icon}</span>{l.label}
          </Link>
        ))}
      </nav>
      <div className="px-4 py-3 border-t border-[#2e3348] text-[10px] text-[#7b82a0]">
        ARIA v1.0 · Admin
      </div>
    </aside>
  );
}
