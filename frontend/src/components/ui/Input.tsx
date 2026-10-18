import { useState, type ComponentProps, type ReactNode } from 'react';
import { ChevronDown, Eye, EyeOff, Search } from 'lucide-react';
import { cx } from '@/utils/cx';
import { IconButton } from './IconButton';
import './field.css';

type Size = 'md' | 'lg';

export function Input({
  size = 'md',
  className,
  ...rest
}: Omit<ComponentProps<'input'>, 'size'> & { size?: Size }) {
  return <input {...rest} className={cx('control', size === 'lg' && 'control--lg', className)} />;
}

/** Password field with a show/hide toggle (a real button with `aria-pressed`). */
export function PasswordInput({
  size = 'md',
  className,
  ...rest
}: Omit<ComponentProps<'input'>, 'size' | 'type'> & { size?: Size }) {
  const [visible, setVisible] = useState(false);
  return (
    <span className="control-wrap">
      <input
        {...rest}
        type={visible ? 'text' : 'password'}
        className={cx('control', size === 'lg' && 'control--lg', className)}
      />
      <span className="control-wrap__action">
        <IconButton
          label={visible ? 'Hide password' : 'Show password'}
          aria-pressed={visible}
          icon={visible ? <EyeOff size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
          onClick={() => setVisible((v) => !v)}
        />
      </span>
    </span>
  );
}

export function SearchInput({
  size = 'md',
  className,
  ...rest
}: Omit<ComponentProps<'input'>, 'size' | 'type'> & { size?: Size }) {
  return (
    <span className="control-wrap control-wrap--icon">
      <Search className="control-wrap__icon" size={20} aria-hidden="true" />
      <input
        {...rest}
        type="search"
        className={cx('control', size === 'lg' && 'control--lg', className)}
      />
    </span>
  );
}

export function Select({
  size = 'md',
  className,
  children,
  ...rest
}: Omit<ComponentProps<'select'>, 'size'> & { size?: Size; children: ReactNode }) {
  return (
    <span className="control-wrap control-wrap--select">
      <select {...rest} className={cx('control', size === 'lg' && 'control--lg', className)}>
        {children}
      </select>
      <ChevronDown className="control-wrap__icon" size={20} aria-hidden="true" />
    </span>
  );
}

export function Textarea({ className, ...rest }: ComponentProps<'textarea'>) {
  return <textarea {...rest} className={cx('control', className)} />;
}
