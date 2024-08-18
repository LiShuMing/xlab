import { Navigate, Outlet } from 'react-router-dom';
import { Header } from '../../components/Header';
import { EgoTabBar } from '../../components/ego/EgoTabBar';
import { isLoggedIn } from '../../lib/ego/authState';

export function EgoShellPage() {
  if (!isLoggedIn()) {
    return <Navigate to="/ego/login" replace />;
  }

  return (
    <main className="ego2-page">
      <Header />
      <EgoTabBar />
      <div className="ego2-shell">
        <Outlet />
      </div>
    </main>
  );
}
