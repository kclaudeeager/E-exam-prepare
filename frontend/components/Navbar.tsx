'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAuth } from '@/lib/hooks';
import { ROUTES } from '@/config/constants';

export default function Navbar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();

  if (!user) return null;

  const isAdmin = user.role === 'admin';

  const studentLinks = [
    { href: ROUTES.DASHBOARD, label: 'Dashboard', icon: '🏠' },
    { href: ROUTES.STUDENT_BROWSE, label: 'Exam Papers', icon: '📄' },
    { href: ROUTES.STUDENT_DOCUMENTS, label: 'My Docs', icon: '📂' },
    { href: ROUTES.STUDENT_ASK_AI, label: 'Ask AI', icon: '🤖' },
    { href: ROUTES.STUDENT_PRACTICE, label: 'Practice', icon: '✏️' },
    { href: ROUTES.STUDENT_ATTEMPTS, label: 'Attempts', icon: '📝' },
    { href: ROUTES.STUDENT_PROGRESS, label: 'Progress', icon: '📊' },
    { href: ROUTES.STUDENT_PROFILE, label: 'Profile', icon: '👤' },
  ];

  const adminLinks = [
    { href: ROUTES.DASHBOARD, label: 'Dashboard', icon: '🏠' },
    { href: ROUTES.ADMIN_DOCUMENTS, label: 'Documents', icon: '📁' },
    { href: ROUTES.ADMIN_STUDENTS, label: 'Students', icon: '👥' },
    { href: ROUTES.ADMIN_ANALYTICS, label: 'Analytics', icon: '📈' },
  ];

  const links = isAdmin ? adminLinks : studentLinks;

  // Match sub-routes too (e.g. /student/attempts/123 → Attempts active)
  const isActive = (href: string) =>
    pathname === href ||
    (href !== ROUTES.DASHBOARD && pathname.startsWith(href));

  return (
    <header className="border-b bg-white shadow-sm sticky top-0 z-50">
      <div className="mx-auto max-w-7xl flex items-center justify-between px-4 py-2.5">
        {/* Brand */}
        <Link href={ROUTES.DASHBOARD} className="flex items-center gap-2 shrink-0">
          <span className="text-lg font-bold text-blue-600">📚 E-exam</span>
        </Link>

        {/* Nav links — desktop */}
        <nav className="hidden md:flex items-center gap-0.5">
          {links.map(({ href, label, icon }) => {
            const active = isActive(href);
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`}
              >
                <span className="text-base">{icon}</span>
                {label}
              </Link>
            );
          })}
        </nav>

        {/* User info + logout */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="hidden sm:block text-right">
            <p className="text-sm font-medium text-gray-800 leading-tight">{user.full_name}</p>
            <span
              className={`text-xs font-semibold uppercase px-1.5 py-0.5 rounded ${
                isAdmin
                  ? 'bg-purple-100 text-purple-700'
                  : 'bg-blue-100 text-blue-700'
              }`}
            >
              {user.role}
            </span>
          </div>
          <button
            onClick={logout}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-gray-400 transition-colors"
          >
            Log out
          </button>
        </div>
      </div>

      {/* Mobile nav — scrollable */}
      <div className="md:hidden border-t px-3 py-1.5 flex gap-1 overflow-x-auto scrollbar-hide">
        {links.map(({ href, label, icon }) => {
          const active = isActive(href);
          return (
            <Link
              key={href}
              href={href}
              className={`shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                active
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              <span>{icon}</span>
              {label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
