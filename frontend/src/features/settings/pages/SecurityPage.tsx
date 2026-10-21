import { useState, type FormEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Alert } from '@/components/feedback/Alert';
import { QueryBoundary } from '@/components/feedback/QueryBoundary';
import { PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { Input, PasswordInput } from '@/components/ui/Input';
import { getErrorMessage } from '@/services/error-handler';
import { adoptAuthResponse, changePassword, useAuth } from '@/services/session';
import { formatDateTime } from '@/utils/format';
import type { MfaEnrollment, MfaStatus } from '../api/security-api';
import { QrCode } from '../components/QrCode';
import { SettingsNav } from '../components/SettingsNav';
import { useActivateMfa, useDisableMfa, useEnrollMfa, useMfaStatus, useRegenerateCodes } from '../hooks/useSecurity';

const groupSecret = (secret: string) => secret.replace(/(.{4})/g, '$1 ').trim();

export function SecurityPage() {
  const status = useMfaStatus();
  const { user } = useAuth();
  return (
    <section aria-labelledby="security-title" className="stack stack--tight">
      <PageHeader title="Security" titleId="security-title" subtitle="Two-step verification and your password" />
      {user?.mfa_enrollment_required && (
        <Alert tone="warning" title="Set up two-step verification to continue">
          Your role requires two-step verification. Until you turn it on, this page is the only part of EcoMind AI you can use.
        </Alert>
      )}
      <SettingsNav />
      <Card aria-labelledby="mfa-title">
        <CardHeader title="Two-step verification" titleId="mfa-title" />
        <QueryBoundary query={status} label="two-step verification status">
          {(s) => <MfaPanel status={s} />}
        </QueryBoundary>
      </Card>
      <PasswordCard />
    </section>
  );
}

function MfaPanel({ status }: { status: MfaStatus }) {
  const [enrollment, setEnrollment] = useState<MfaEnrollment | null>(null);
  const [codes, setCodes] = useState<string[] | null>(null);

  // Recovery codes are shown exactly once, so they take over the panel until the user confirms.
  if (codes) return <RecoveryCodes codes={codes} onDone={() => setCodes(null)} />;
  if (enrollment) return <Enrollment enrollment={enrollment} onActivated={(c) => { setEnrollment(null); setCodes(c); }} onCancel={() => setEnrollment(null)} />;
  if (status.enabled) return <Enabled status={status} onNewCodes={setCodes} />;
  return <Disabled status={status} onEnrolling={setEnrollment} />;
}

function Disabled({ status, onEnrolling }: { status: MfaStatus; onEnrolling: (e: MfaEnrollment) => void }) {
  const enroll = useEnrollMfa();
  return (
    <div className="stack stack--tight">
      <p>
        <Badge tone="neutral">Off</Badge> Add a second step to sign-in using an authenticator app (Google Authenticator, Microsoft
        Authenticator, Aegis, 1Password and similar).
      </p>
      {status.pending_enrollment && (
        <Alert tone="info">A previous setup was started but not confirmed, so two-step verification is still off. Starting again replaces it.</Alert>
      )}
      {enroll.isError && <Alert tone="danger">{getErrorMessage(enroll.error)}</Alert>}
      <div>
        <Button loading={enroll.isPending} onClick={() => enroll.mutate(undefined, { onSuccess: onEnrolling })}>
          Set up two-step verification
        </Button>
      </div>
    </div>
  );
}

function Enrollment({ enrollment, onActivated, onCancel }: { enrollment: MfaEnrollment; onActivated: (codes: string[]) => void; onCancel: () => void }) {
  const [code, setCode] = useState('');
  const activate = useActivateMfa();
  const submit = (e: FormEvent) => {
    e.preventDefault();
    activate.mutate(code.trim(), { onSuccess: (r) => onActivated(r.recovery_codes) });
  };
  return (
    <div className="stack stack--tight">
      <p>
        <strong>1.</strong> Scan this QR code with your authenticator app, or type the key in by hand.
      </p>
      <QrCode value={enrollment.otpauth_uri} label="QR code for your authenticator app" />
      <p>
        Key (shown once): <span className="secret">{groupSecret(enrollment.secret)}</span>
      </p>
      <p>
        <strong>2.</strong> Enter the {enrollment.digits}-digit code the app shows to confirm. Two-step verification is not on until you do.
      </p>
      <form className="settings-form" onSubmit={submit} noValidate>
        <Field label="Code from your app">
          {(c) => <Input {...c} data-autofocus inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
        </Field>
        {activate.isError && <Alert tone="danger">{getErrorMessage(activate.error)}</Alert>}
        <div className="row-actions">
          <Button type="submit" loading={activate.isPending} disabled={code.trim().length < 6}>
            Confirm and turn on
          </Button>
          <Button type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [saved, setSaved] = useState(false);
  return (
    <div className="stack stack--tight">
      <Alert tone="warning" title="Save these recovery codes now">
        Each code works once if you lose your authenticator. They are shown only this time and cannot be retrieved later.
      </Alert>
      <ul className="recovery-codes" aria-label="Recovery codes">
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <label className="check">
        <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} /> I have saved these codes somewhere safe
      </label>
      <div>
        <Button disabled={!saved} onClick={onDone}>
          Done
        </Button>
      </div>
    </div>
  );
}

function Enabled({ status, onNewCodes }: { status: MfaStatus; onNewCodes: (c: string[]) => void }) {
  const [mode, setMode] = useState<'idle' | 'disable' | 'codes'>('idle');
  return (
    <div className="stack stack--tight">
      <p>
        <Badge tone="success">On</Badge> Turned on {formatDateTime(status.enabled_at)}. {status.recovery_codes_remaining} recovery code
        {status.recovery_codes_remaining === 1 ? '' : 's'} left.
      </p>
      {status.recovery_codes_remaining <= 2 && (
        <Alert tone="warning">You are running low on recovery codes. Generate new ones to stay able to sign in if you lose your device.</Alert>
      )}
      {mode === 'idle' ? (
        <div className="row-actions">
          <Button variant="secondary" onClick={() => setMode('codes')}>
            Generate new recovery codes
          </Button>
          <Button variant="danger" onClick={() => setMode('disable')}>
            Turn off two-step verification
          </Button>
        </div>
      ) : (
        <ProofForm mode={mode} onCancel={() => setMode('idle')} onNewCodes={onNewCodes} />
      )}
    </div>
  );
}

function ProofForm({ mode, onCancel, onNewCodes }: { mode: 'disable' | 'codes'; onCancel: () => void; onNewCodes: (c: string[]) => void }) {
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const disable = useDisableMfa();
  const regenerate = useRegenerateCodes();
  const mutation = mode === 'disable' ? disable : regenerate;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const proof = { password, code: code.trim() };
    if (mode === 'disable') disable.mutate(proof, { onSuccess: onCancel });
    else regenerate.mutate(proof, { onSuccess: (r) => onNewCodes(r.recovery_codes) });
  };
  return (
    <form className="settings-form" onSubmit={submit} noValidate>
      <p>{mode === 'disable' ? 'Confirm with your password and a current code to turn two-step verification off.' : 'Confirm with your password and a current code. Existing recovery codes stop working.'}</p>
      <Field label="Password">{(c) => <PasswordInput {...c} data-autofocus autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}</Field>
      <Field label="Authenticator or recovery code">
        {(c) => <Input {...c} autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} />}
      </Field>
      {mutation.isError && <Alert tone="danger">{getErrorMessage(mutation.error)}</Alert>}
      <div className="row-actions">
        <Button type="submit" variant={mode === 'disable' ? 'danger' : 'primary'} loading={mutation.isPending} disabled={!password || code.trim().length < 6}>
          {mode === 'disable' ? 'Turn off' : 'Generate new codes'}
        </Button>
        <Button type="button" variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function PasswordCard() {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [again, setAgain] = useState('');
  const [done, setDone] = useState(false);
  const mismatch = again !== '' && next !== again;
  const mutation = useMutation({ mutationFn: changePassword, onSuccess: (r) => { adoptAuthResponse(r); setDone(true); setCurrent(''); setNext(''); setAgain(''); } });
  return (
    <Card aria-labelledby="password-title">
      <CardHeader title="Change password" titleId="password-title" />
      <form
        className="settings-form"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setDone(false);
          mutation.mutate({ current_password: current, new_password: next });
        }}
      >
        <Field label="Current password">{(c) => <PasswordInput {...c} autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />}</Field>
        <Field label="New password" hint="At least 12 characters; common or personal passwords are refused.">
          {(c) => <PasswordInput {...c} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />}
        </Field>
        <Field label="Repeat new password" error={mismatch ? 'The passwords do not match.' : undefined}>
          {(c) => <PasswordInput {...c} autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />}
        </Field>
        {mutation.isError && <Alert tone="danger">{getErrorMessage(mutation.error)}</Alert>}
        {done && <Alert tone="success">Password changed. Your other devices have been signed out.</Alert>}
        <div>
          <Button type="submit" loading={mutation.isPending} disabled={!current || next.length < 12 || next !== again}>
            Change password
          </Button>
        </div>
      </form>
    </Card>
  );
}
