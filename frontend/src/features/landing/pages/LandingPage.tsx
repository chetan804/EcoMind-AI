import { Boxes, Brain, Cpu, Layers, Play, Recycle, Route, ScanSearch, TrendingUp } from 'lucide-react';
import { Link } from 'react-router';
import { Button, ButtonLink } from '@/components/ui/Button';
import { HeroArt } from '../components/HeroArt';
import { PublicHeader } from '../components/PublicHeader';
import '../landing.css';

/**
 * These four are facts about the product today, not performance claims. The design reference
 * shows accuracy/cost/response/user-count statistics; none can be substantiated (no service is
 * deployed and the only trained classifier is an unapproved candidate), so they are intentionally
 * not reproduced. Keep every value true when features change (the project audit found the earlier
 * "planned, none available" copy outdated).
 */
const projectFacts = [
  { icon: <Boxes size={28} />, value: '5', label: 'User roles with separate permissions' },
  { icon: <Layers size={28} />, value: '6', label: 'Waste classes the classifier knows' },
  { icon: <Cpu size={28} />, value: '3', label: 'ML capabilities built: classifier, forecasts, anomaly flags' },
  { icon: <Brain size={28} />, value: '0', label: 'Classifiers approved for use' },
];

const capabilities = [
  { icon: <ScanSearch size={28} />, title: 'Identify waste using computer vision' },
  { icon: <TrendingUp size={28} />, title: 'Forecast waste generation trends' },
  { icon: <Route size={28} />, title: 'Optimize collection routes with AI' },
  { icon: <Recycle size={28} />, title: 'Enable reuse, recycling and resource recovery' },
];

/** Public landing page. Describes what the product does and states plainly what is not yet approved. */
export function LandingPage() {
  return (
    <div className="landing" id="top">
      <div className="landing__top">
        <HeroArt />
        <PublicHeader />
        <main id="main" className="landing__main">
          <div className="landing__wrap">
            <section className="hero" aria-labelledby="hero-title">
              <h1 id="hero-title" className="hero__title">
                Smarter
                <br />
                Waste Management
                <br />
                for <em>a Cleaner Tomorrow</em>
              </h1>
              <p className="hero__tagline">AI-Powered. Data-Driven. Sustainable.</p>
              <p className="hero__lead">
                Transforming waste into opportunities through artificial intelligence, smart analytics and community participation.
              </p>
              <div className="hero__actions">
                <ButtonLink to="/dashboard" size="lg">
                  Explore platform
                </ButtonLink>
                <Button variant="secondary" size="lg" icon={<Play size={20} aria-hidden="true" />} unavailableReason="No product demo is available yet.">
                  Watch demo
                </Button>
              </div>
            </section>
          </div>
          <div className="landing__wrap landing__wrap--bottom" id="solutions">
            <ul className="pillars" aria-label="Project status at a glance">
              {projectFacts.map((fact) => (
                <li key={fact.label} className="pillar">
                  <span className="pillar__icon" aria-hidden="true">
                    {fact.icon}
                  </span>
                  <span>
                    <span className="pillar__value">{fact.value}</span>
                    <span className="pillar__label">{fact.label}</span>
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </main>
      </div>

      <div className="landing__wrap">
        <section className="section section--tight" id="features" aria-labelledby="features-title">
          <h2 id="features-title" className="visually-hidden">
            Planned capabilities
          </h2>
          <ul className="features">
            {capabilities.map((item) => (
              <li key={item.title} className="feature">
                <span className="feature__icon" aria-hidden="true">
                  {item.icon}
                </span>
                <h3 className="feature__title">{item.title}</h3>
              </li>
            ))}
          </ul>
          <p className="landing__status">EcoMind AI is under active development and is not deployed anywhere yet. The screens work end to end on demonstration data; the waste-image classifier is an unapproved research candidate, so no performance or impact figures are published.</p>
        </section>

        <section className="section" id="impact" aria-labelledby="impact-title">
          <h2 id="impact-title" className="section__title">
            Impact
          </h2>
          <p className="section__text">
            The aim is to cut avoidable landfill by routing recoverable material to reuse and recycling, and to make collection
            planning evidence-based. No impact figures are published until there is measured data behind them.
          </p>
        </section>

        <section className="section" id="about" aria-labelledby="about-title">
          <h2 id="about-title" className="section__title">
            About
          </h2>
          <p className="section__text">
            EcoMind AI is a waste-intelligence and circular-economy platform under construction. Follow progress in the{' '}
            <Link to="/settings/system-status">system status</Link> page.
          </p>
        </section>
      </div>
      <footer className="landing__footer">
        <div className="landing__wrap">EcoMind AI. Early-stage software: features and figures shown elsewhere in the app marked as demonstration data are not real.</div>
      </footer>
    </div>
  );
}
