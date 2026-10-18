import { Brand } from '@/components/layout/BrandMark';
import { ButtonLink } from '@/components/ui/Button';
import { Link } from 'react-router';

const links = [
  { href: '#top', label: 'Home', current: true },
  { href: '#features', label: 'Features' },
  { href: '#solutions', label: 'Solutions' },
  { href: '#impact', label: 'Impact' },
  { href: '#about', label: 'About' },
];

/** Public-site header: brand, in-page section links, and the primary call to action. */
export function PublicHeader() {
  return (
    <header className="public-header">
      <Link to="/" className="brand" aria-label="EcoMind AI home">
        <Brand />
      </Link>
      <nav aria-label="Sections" className="public-header__nav">
        {links.map((link) => (
          <a key={link.href} href={link.href} className="public-header__link" aria-current={link.current ? 'true' : undefined}>
            {link.label}
          </a>
        ))}
      </nav>
      <ButtonLink to="/sign-up" className="public-header__cta">
        Get started
      </ButtonLink>
    </header>
  );
}
