import { useState } from 'react';
import { Link } from 'react-router';
import { ArrowRight, Boxes, Brain, Cpu, Layers, Play, Recycle, Route, ScanSearch, TrendingUp, ShieldCheck, Gauge } from 'lucide-react';
import { Brand } from '@/components/layout/BrandMark';
import { Button, ButtonLink } from '@/components/ui/Button';
import { DemoDialog } from '../components/DemoDialog';
import { FeatureSection } from '../components/FeatureSection';
import { HeroArt } from '../components/HeroArt';
import { PublicHeader } from '../components/PublicHeader';
import { CAPABILITIES, PROBLEMS, PROJECT_FACTS, ROLES, SECURITY_POINTS, SHOTS, TRANSPARENCY_POINTS, WORKFLOW } from '../content';
import '../landing.css';

const FACT_ICONS = [<Boxes key="b" size={28} />, <Layers key="l" size={28} />, <Cpu key="c" size={28} />, <Brain key="r" size={28} />];
const CAPABILITY_ICONS = [
  <ScanSearch key="1" size={26} />,
  <TrendingUp key="2" size={26} />,
  <Gauge key="3" size={26} />,
  <Route key="4" size={26} />,
  <ShieldCheck key="5" size={26} />,
  <Recycle key="6" size={26} />,
];

/** Public landing page: what the product does, with real screenshots, and what it does not yet do. */
export function LandingPage() {
  const [demoOpen, setDemoOpen] = useState(false);
  return (
    <div className="landing" id="top">
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <PublicHeader />
      <div className="landing__top">
        <HeroArt />
        <main id="main" className="landing__main">
          <div className="landing__wrap">
            {/* 1. Hero */}
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
                One workspace to classify waste, forecast collection volume, flag unusual weeks, order routes and trace recovered material, with a person
                deciding at every step.
              </p>
              <div className="hero__actions">
                <ButtonLink to="/sign-up" size="lg" icon={<ArrowRight size={20} aria-hidden="true" />}>
                  Get started
                </ButtonLink>
                <Button variant="secondary" size="lg" icon={<Play size={20} aria-hidden="true" />} onClick={() => setDemoOpen(true)}>
                  Watch demo
                </Button>
              </div>
            </section>
          </div>
          <div className="landing__wrap landing__wrap--bottom">
            <ul className="pillars" aria-label="Project status at a glance">
              {PROJECT_FACTS.map((fact, i) => (
                <li key={fact.label} className="pillar">
                  <span className="pillar__icon" aria-hidden="true">
                    {FACT_ICONS[i]}
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
        {/* 2. Problem */}
        <section className="section" id="problem" aria-labelledby="problem-title">
          <p className="eyebrow">The problem</p>
          <h2 id="problem-title" className="section__title">
            Waste systems run on guesswork
          </h2>
          <ul className="cards cards--4">
            {PROBLEMS.map((item) => (
              <li key={item.title} className="card-tile">
                <h3 className="card-tile__title">{item.title}</h3>
                <p>{item.body}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* 3. Solution */}
        <section className="section" id="product" aria-labelledby="solution-title">
          <p className="eyebrow">The solution</p>
          <h2 id="solution-title" className="section__title">
            One workspace from report to recovery
          </h2>
          <p className="section__text">
            EcoMind AI connects what residents report, what collectors collect, what facilities recover and what the data says should happen next. Each step
            is recorded, and every machine suggestion is labelled and left for a person to accept.
          </p>
          <ul className="cards cards--3">
            <li className="card-tile">
              <h3 className="card-tile__title">See</h3>
              <p>A command center built from live database queries, with honest empty states when there is no data yet.</p>
            </li>
            <li className="card-tile">
              <h3 className="card-tile__title">Decide</h3>
              <p>Forecasts, suspected anomalies and route plans arrive with their method and their limits.</p>
            </li>
            <li className="card-tile">
              <h3 className="card-tile__title">Prove</h3>
              <p>Recovery records, passports and the points ledger are append-only or verified by a second person.</p>
            </li>
          </ul>
        </section>

        {/* 4. Capabilities */}
        <section className="section section--tight" id="capabilities" aria-labelledby="features-title">
          <p className="eyebrow">Platform</p>
          <h2 id="features-title" className="section__title">
            What the platform covers
          </h2>
          <ul className="features">
            {CAPABILITIES.map((item, i) => (
              <li key={item.title} className="feature">
                <span className="feature__icon" aria-hidden="true">
                  {CAPABILITY_ICONS[i]}
                </span>
                <h3 className="feature__title">{item.title}</h3>
                <p className="feature__body">{item.body}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* 5. Classification */}
        <FeatureSection
          id="classification"
          eyebrow="AI classification"
          title="Identify waste from a photo, or say plainly that it cannot"
          lead="Residents and collectors upload a photo and get a material category with a confidence. Uncertain results and material outside the known categories go to a review queue instead of being guessed."
          points={['Upload checks on type and size before anything is analysed', 'Low-confidence and out-of-scope results are routed to human review', 'Reviewers can correct a result, and corrections are kept']}
          status={{ tone: 'warning', label: 'Status', text: 'No classifier is approved for use. The screen shows "No classification model is active" until one passes its approval checks.' }}
          shot={SHOTS.classify}
        />

        {/* 6. Forecasting */}
        <FeatureSection
          id="forecasting"
          eyebrow="Forecasting"
          title="Forecasts that show their history, interval and baseline"
          lead="Weekly collection volume is forecast up to a few weeks ahead. Observed history and the forecast are drawn apart, with an interval, and the chosen model is compared with a naive baseline."
          points={['Needs 26 complete weeks of history, and says so when there is less', 'Public reference series are labelled as public reference data', 'Forecasts can be saved and read back later']}
          status={{ tone: 'info', label: 'Evidence', text: 'On the series tested, the selected model beat the naive baseline on two of four. Treat a forecast as a planning aid, not a promise.' }}
          shot={SHOTS.forecasts}
          reverse
        />

        {/* 7. Anomaly */}
        <FeatureSection
          id="anomaly"
          eyebrow="Anomaly detection"
          title="Statistical outliers, explained and triaged by people"
          lead="A robust check compares each week with the same weeks in earlier years, or with recent weeks when there is not enough history, and flags unusual values with a plain-language reason."
          points={['Severity and the observed versus expected values are shown', 'Managers acknowledge, resolve or mark a flag as a false positive', 'Every change is audited']}
          status={{ tone: 'warning', label: 'Read this', text: 'A flag is a suspected anomaly, not a confirmed incident. The system cannot know the cause.' }}
          shot={SHOTS.anomalies}
        />

        {/* 8. Routing */}
        <FeatureSection
          id="routing"
          eyebrow="Route planning"
          title="Route plans that state how they were made"
          lead="A manager picks the tasks and a vehicle, and the platform orders the stops. The plan lists its method and distance and draws the stops on a map."
          points={['Straight-line distances, labelled as straight-line estimates', 'Checked against an exact search on small test sets', 'Optional road geometry only when a routing provider is configured']}
          status={{ tone: 'warning', label: 'Limits', text: 'No live traffic, no travel-time estimate and no claim about arrival times.' }}
          shot={SHOTS.routes}
          reverse
        />

        {/* 9. Command center */}
        <FeatureSection
          id="command-center"
          eyebrow="Command center"
          title="Operations at a glance, built from real queries"
          lead="The dashboard reads the database when you open it: collected weight, open and overdue tasks, recovery rate, suspected anomalies, and a list of what needs attention."
          points={['Weekly trend, task status and fleet summary', 'A needs-attention list that links straight to the work', 'A fleet and facilities map that labels simulated or stale positions']}
          shot={SHOTS.dashboard}
        />

        {/* 10. Citizen participation */}
        <FeatureSection
          id="citizens"
          eyebrow="Citizen participation"
          title="Residents report, staff triage"
          lead="Residents report waste and community incidents such as illegal dumping, overflowing bins or open burning. Staff review, assign and close them, and the reporter is told what happened."
          points={['Reports with location and photo, and a status the reporter can follow', 'A sorting guide and a help assistant for everyday questions', 'Private addresses and reporter identity are not shown on maps']}
          shot={SHOTS.incidents}
          reverse
        />

        {/* 11. Marketplace */}
        <FeatureSection
          id="marketplace"
          eyebrow="Circular marketplace"
          title="Surplus material, matched for reuse"
          lead="Facility operators and managers list surplus material, and others ask for what they can use. It is a matching board only."
          points={['Listings by category, quantity, condition and city', 'Requests are accepted, declined or withdrawn, with notifications', 'No payment, delivery tracking or chat']}
          shot={SHOTS.marketplace}
        />

        {/* 12. Traceability */}
        <FeatureSection
          id="traceability"
          eyebrow="Traceability"
          title="Material passports with a chain of custody"
          lead="Each batch has a passport. Custody events are added in order and never edited, so the record shows who held the material and where it went."
          points={['Created, received, processed and verified events', 'Linked to the recovery record', 'An integrity check that tests the record for consistency']}
          status={{ tone: 'info', label: 'Note', text: 'The integrity check tests consistency of the record. It is not a cryptographic proof.' }}
          shot={SHOTS.passport}
          reverse
        />

        {/* 13. Impact and rewards */}
        <FeatureSection
          id="impact"
          eyebrow="Impact and rewards"
          title="Recovery and points from verified weight only"
          lead="Recovery is a mass ratio from records that a second person verified. Residents earn points from verified collected weight, in an append-only ledger that staff correct with reversals."
          points={['Recovery rate equals recovered weight divided by input weight', 'Points per kilogram are configured, not estimated', 'Staff set the reward items that points can be spent on']}
          status={{ tone: 'warning', label: 'No impact claims', text: 'No carbon, cost or landfill-diversion figure is shown because none is sourced.' }}
          shot={SHOTS.rewards}
        />

        {/* 14. Workflow */}
        <section className="section" id="workflow" aria-labelledby="workflow-title">
          <p className="eyebrow">Workflow</p>
          <h2 id="workflow-title" className="section__title">
            From a report to a verified result
          </h2>
          <ol className="steps">
            {WORKFLOW.map((step) => (
              <li key={step.title} className="step">
                <h3 className="step__title">{step.title}</h3>
                <p>{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        {/* 15. Roles */}
        <section className="section" id="roles" aria-labelledby="roles-title">
          <p className="eyebrow">Roles</p>
          <h2 id="roles-title" className="section__title">
            Five roles, each with its own view
          </h2>
          <p className="section__text">Anyone can sign up as a citizen. An operational role is requested after sign-up and approved by an administrator.</p>
          <ul className="cards cards--5">
            {ROLES.map((role) => (
              <li key={role.name} className="card-tile">
                <h3 className="card-tile__title">{role.name}</h3>
                <p>{role.summary}</p>
                <p className="card-tile__how">{role.how}</p>
              </li>
            ))}
          </ul>
        </section>

        {/* 16. Security and transparency */}
        <section className="section" id="security" aria-labelledby="security-title">
          <p className="eyebrow">Security and transparency</p>
          <h2 id="security-title" className="section__title">
            Built to be checked, and honest about what is not done
          </h2>
          <div className="two-col">
            <ul className="cards cards--2">
              {SECURITY_POINTS.map((item) => (
                <li key={item.title} className="card-tile">
                  <h3 className="card-tile__title">{item.title}</h3>
                  <p>{item.body}</p>
                </li>
              ))}
            </ul>
            <div className="card-tile card-tile--note">
              <h3 className="card-tile__title">Where the project stands</h3>
              <ul className="ticks">
                {TRANSPARENCY_POINTS.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p>
                <Link to="/settings/system-status">System status</Link>
              </p>
            </div>
          </div>
        </section>

        {/* 17. Final call to action */}
        <section className="cta" aria-labelledby="cta-title">
          <h2 id="cta-title" className="cta__title">
            See it on demonstration data
          </h2>
          <p className="cta__text">Create a citizen account in a minute, or walk through the five core flows first.</p>
          <div className="hero__actions cta__actions">
            <ButtonLink to="/sign-up" size="lg" icon={<ArrowRight size={20} aria-hidden="true" />}>
              Get started
            </ButtonLink>
            <Button variant="secondary" size="lg" icon={<Play size={20} aria-hidden="true" />} onClick={() => setDemoOpen(true)}>
              Watch demo
            </Button>
          </div>
        </section>
      </div>

      {/* 18. Footer */}
      <footer className="landing__footer">
        <div className="landing__wrap footer">
          <div>
            <Link to="/" className="brand" aria-label="EcoMind AI home">
              <Brand />
            </Link>
            <p className="footer__note">Early-stage software. Data shown on this page is demonstration data, not real operations.</p>
          </div>
          <nav aria-label="Footer" className="footer__nav">
            <a href="#product">Product</a>
            <a href="#capabilities">Platform</a>
            <a href="#roles">Roles</a>
            <a href="#security">Security</a>
            <Link to="/sign-in">Sign in</Link>
            <Link to="/sign-up">Get started</Link>
          </nav>
        </div>
      </footer>

      <DemoDialog open={demoOpen} onClose={() => setDemoOpen(false)} />
    </div>
  );
}

