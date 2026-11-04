import { Check } from 'lucide-react';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { AVAILABILITY_LABEL, ROLE_INFO, type RoleInfo } from '../roles';

const TONE: Record<RoleInfo['availability'], BadgeTone> = { instant: 'success', approval: 'warning', protected: 'neutral' };

/** The five account types: what each does, what it can open and how it is obtained. Read-only explanation. */
export function RoleGuide() {
  return (
    <ul className="role-guide">
      {ROLE_INFO.map((role) => (
        <li key={role.key} className="role-guide__item">
          <div className="role-guide__head">
            <h3 className="role-guide__name">{role.label}</h3>
            <Badge tone={TONE[role.availability]}>{AVAILABILITY_LABEL[role.availability]}</Badge>
          </div>
          <p className="muted">{role.summary}</p>
          <ul className="role-guide__access">
            {role.access.map((line) => (
              <li key={line}><Check size={14} aria-hidden="true" /> {line}</li>
            ))}
          </ul>
        </li>
      ))}
    </ul>
  );
}
