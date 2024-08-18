import { Header } from '../components/Header';
import { SiteFooter } from '../components/SiteFooter';
import { CodexLibrary } from './CodexLibrary';

export function CodexPage({ bookSeriesList }) {
  return (
    <main className="codex-page">
      <Header />
      <CodexLibrary bookSeriesList={bookSeriesList} />
      <SiteFooter />
    </main>
  );
}
