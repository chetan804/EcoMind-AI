import { ROLE_INFO, RoleGuide, type RoleKey } from '@/features/access-requests';
import type { AccountType } from '../schemas/auth-forms';

const CHOICES = ROLE_INFO.filter((r) => r.key !== 'administrator');

/**
 * Account-type chooser for sign-up. Everyone starts as a citizen; the other types are requests an
 * administrator approves, and the administrator role is not offered at all. Explanatory only: the
 * server decides what a person can do.
 */
export function AccountTypePicker({ value, onChange }: { value: AccountType; onChange: (value: AccountType) => void }) {
  const chosen = ROLE_INFO.find((r) => r.key === (value as RoleKey));
  return (
    <fieldset className="account-types">
      <legend>I am signing up as</legend>
      <div className="account-types__grid">
        {CHOICES.map((role) => (
          <label key={role.key} className="account-type">
            <input type="radio" name="accountType" value={role.key} checked={value === role.key} onChange={() => onChange(role.key as AccountType)} />
            <span className="account-type__name">{role.label}</span>
            <span className="account-type__hint">{role.availability === 'instant' ? 'Instant access' : 'Needs approval'}</span>
          </label>
        ))}
      </div>
      {chosen && (
        <p className="account-types__help" aria-live="polite">
          {chosen.availability === 'instant'
            ? `${chosen.summary}`
            : `${chosen.summary} You start as a Citizen; an administrator reviews your request and you are notified.`}
        </p>
      )}
      <details className="auth-roles-detail">
        <summary>What can each role do?</summary>
        <RoleGuide />
        <p className="account-types__help">Administrator accounts are created by an existing administrator and cannot be requested here.</p>
      </details>
    </fieldset>
  );
}
