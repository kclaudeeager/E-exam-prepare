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
    { href: ROUTES.DASHBOARD, label: 'Dashboard' },
    { href: ROUTES.STUDENT_BROWSE, label: 'Exam Papers' },
    { href: ROUTES.STUDENT_ASK_AI, label: '🤖 Ask AI' },
    { href: ROUTES.STUDENT_PRACTICE, label: 'Practice' },
    { href: ROUTES.STUDENT_PROGRESS, label: 'Progress' },
  ];

  const adminLinks = [
    { href: ROUTES.DASHBOARD, label: 'Dashboard' },
    { href: ROUTES.ADMIN_DOCUMENTS, label: 'Documents' },
    { href: ROUTES.ADMIN_STUDENTS, label: 'Students' },
    { href: ROUTES.ADMIN_ANALYTICS, label: 'Analytics' },
  ];

  const links = isAdmin ? adminLinks : studentLinks;

  return (
    <header className="border-b bg-white shadow-sm sticky top-0 z-10">
      <div className="container flex items-center justify-between py-3">
        {/* Brand */}
        <Link href={ROUTES.DASHBOARD} className="flex items-center gap-2">
          <span className="text-xl font-bold text-blue-600">E-exam-prepare</span>
        </Link>

        {/* Nav links */}
        <nav className="hidden md:flex items-center gap-1">
          {links.map(({ href, label }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  active
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        {/* User info + logout */}
        <div className="flex items-center gap-3">
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

      {/* Mobile nav */}
      <div className="md:hidden border-t px-4 py-2 flex gap-2 overflow-x-auto">
        {links.map(({ href, label }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={`shrink-0 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                active
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </header>
  );
}
