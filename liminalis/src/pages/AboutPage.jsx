import { AboutContent } from '../components/AboutContent';
import { Header } from '../components/Header';
import { SiteFooter } from '../components/SiteFooter';

export function AboutPage() {
  return (
    <main className="about-page">
      <Header />
      <AboutContent />
      <SiteFooter />
    </main>
  );
}
