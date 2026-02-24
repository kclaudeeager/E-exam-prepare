'use client';

import Navbar from '@/components/Navbar';
import AuthGuard from '@/components/AuthGuard';

export default function StudentLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <div className="min-h-screen bg-gray-50">
        <Navbar />
        {children}
      </div>
    </AuthGuard>
  );
}
