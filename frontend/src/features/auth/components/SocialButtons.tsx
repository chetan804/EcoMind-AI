import { Button } from '@/components/ui/Button';

const REASON = 'Single sign-on providers are not available in this build.';

/** Visible per the design, but honestly unavailable: no identity provider is integrated. */
export function SocialButtons() {
  return (
    <>
      <p className="auth-divider">
        <span>or continue with</span>
      </p>
      <div className="auth-social">
        <Button variant="secondary" size="lg" unavailableReason={REASON}>
          Google
        </Button>
        <Button variant="secondary" size="lg" unavailableReason={REASON}>
          Microsoft
        </Button>
      </div>
    </>
  );
}
