import { ArrowRight } from 'lucide-react';
import { Dialog } from '@/components/ui/Dialog';
import { ButtonLink } from '@/components/ui/Button';
import { Tabs, type TabItem } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';
import { DEMO_STEPS } from '../content';
import { ProductShot } from './ProductShot';

const items: TabItem[] = DEMO_STEPS.map((step) => ({
  id: step.id,
  label: step.label,
  panel: (
    <div className="demo">
      <div className="demo__text">
        <h3 className="demo__title">{step.title}</h3>
        <p>{step.body}</p>
        <p className="demo__note">
          <Badge tone="success">Built</Badge> {step.real}
        </p>
        <p className="demo__note">
          <Badge tone="warning">Limit</Badge> {step.limit}
        </p>
      </div>
      <ProductShot shot={step.shot} />
    </div>
  ),
}));

/**
 * "Watch demo": an interactive walkthrough of the five core flows using screenshots of the real
 * screens. It is a native modal dialog, so the page behind is inert, Escape closes it and focus
 * returns to the button that opened it. It is deliberately not a video player.
 */
export function DemoDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      wide
      className="demo-dialog"
      title="Product walkthrough"
      description="Five steps through the platform, using screenshots of the running application on demonstration data."
      footer={
        <ButtonLink to="/sign-up" icon={<ArrowRight size={18} aria-hidden="true" />}>
          Get started
        </ButtonLink>
      }
    >
      <Tabs items={items} label="Walkthrough steps" />
    </Dialog>
  );
}
