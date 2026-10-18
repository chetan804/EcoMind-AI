import type { ComponentProps, ReactNode } from 'react';
import './field.css';

type ChoiceProps = Omit<ComponentProps<'input'>, 'type' | 'children'> & { label: ReactNode };

export function Checkbox({ label, ...rest }: ChoiceProps) {
  return (
    <label className="choice choice--checkbox">
      <input {...rest} type="checkbox" />
      <span className="choice__box" aria-hidden="true" />
      <span>{label}</span>
    </label>
  );
}

/** On/off setting that takes effect immediately. Uses the native checkbox with role="switch". */
export function Switch({ label, ...rest }: ChoiceProps) {
  return (
    <label className="choice">
      <input {...rest} type="checkbox" role="switch" />
      <span className="switch__track" aria-hidden="true">
        <span className="switch__thumb" />
      </span>
      <span>{label}</span>
    </label>
  );
}

export function Radio({ label, ...rest }: ChoiceProps) {
  return (
    <label className="choice choice--radio">
      <input {...rest} type="radio" />
      <span className="choice__box" aria-hidden="true" />
      <span>{label}</span>
    </label>
  );
}

export function RadioGroup({ legend, children }: { legend: ReactNode; children: ReactNode }) {
  return (
    <fieldset className="radio-group">
      <legend>{legend}</legend>
      {children}
    </fieldset>
  );
}
