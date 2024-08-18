import { ReactNode } from 'react';
import Header from './Header';
import Sidebar from './Sidebar';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="flex h-screen flex-col bg-transparent text-slate-950">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-auto p-4 md:p-6">
          <div className="view-enter h-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
