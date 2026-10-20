import { AuthCard } from '../components/AuthCard';
import { RedirectIfSignedIn } from '../components/RedirectIfSignedIn';
import { SignUpForm } from '../components/SignUpForm';

export function SignUpPage() {
  return (
    <RedirectIfSignedIn>
      <AuthCard>
        <SignUpForm />
      </AuthCard>
    </RedirectIfSignedIn>
  );
}
