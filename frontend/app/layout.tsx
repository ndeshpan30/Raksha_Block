import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'RAKSHA-BLOCK — AI Maintenance Coordination Console',
  description: 'SIH26027: AI-Powered Multi-Department Railway Maintenance Block Planning & Bundling (ENG, S&T, TRD)',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
