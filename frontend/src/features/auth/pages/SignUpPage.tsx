import { useState } from 'react';
import { AuthCard } from '../components/AuthCard';
import { RedirectIfSignedIn } from '../components/RedirectIfSignedIn';
import { SignUpForm } from '../components/SignUpForm';
import type { AccountType } from '../schemas/auth-forms';

export function SignUpPage() {
  const [accountType, setAccountType] = useState<AccountType>('citizen');
  return (
    // A person who asked for an operational role lands on the page that shows the request.
    <RedirectIfSignedIn fallback={accountType === 'citizen' ? '/dashboard' : '/settings/access'}>
      <AuthCard wide>
        <SignUpForm accountType={accountType} onAccountType={setAccountType} />
      </AuthCard>
    </RedirectIfSignedIn>
  );
}
