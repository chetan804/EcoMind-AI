import { useId, type ComponentProps, type MouseEvent, type ReactNode } from 'react';
import { Link, type LinkProps } from 'react-router';
import { cx } from '@/utils/cx';
import './button.css';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'md' | 'lg';

interface ButtonStyleProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
  fullWidth?: boolean;
  /** Leading icon (decorative). */
  icon?: ReactNode;
}

const classes = ({ variant = 'primary', size = 'md', fullWidth }: ButtonStyleProps, extra?: string) =>
  cx('btn', `btn--${variant}`, size === 'lg' && 'btn--lg', fullWidth && 'btn--full', extra);

export type ButtonProps = ButtonStyleProps &
  ComponentProps<'button'> & {
    /**
     * Marks the action as unavailable and explains why. The button stays focusable (unlike
     * `disabled`) so keyboard and screen-reader users can read the reason; clicks are ignored.
     */
    unavailableReason?: string;
    /**
     * An action is in progress: shows a spinner, sets aria-busy and ignores clicks (so a form
     * cannot be submitted twice) while staying focusable.
     */
    loading?: boolean;
  };

export function Button({
  variant,
  size,
  fullWidth,
  icon,
  className,
  children,
  type = 'button',
  unavailableReason,
  loading = false,
  onClick,
  ...rest
}: ButtonProps) {
  const reasonId = useId();
  const unavailable = unavailableReason !== undefined;
  const handleClick = (event: MouseEvent<HTMLButtonElement>) => {
    if (unavailable || loading) {
      event.preventDefault();
      return;
    }
    onClick?.(event);
  };
  return (
    <>
      <button
        {...rest}
        type={type}
        className={classes({ variant, size, fullWidth }, cx(loading && 'btn--loading', className))}
        aria-disabled={unavailable || loading || undefined}
        aria-busy={loading || undefined}
        aria-describedby={unavailable ? reasonId : rest['aria-describedby']}
        title={unavailable ? unavailableReason : rest.title}
        onClick={handleClick}
      >
        {loading ? <span className="btn__spinner" aria-hidden="true" /> : icon}
        {children}
      </button>
      {unavailable && (
        <span id={reasonId} className="visually-hidden">
          {unavailableReason}
        </span>
      )}
    </>
  );
}

export function ButtonLink({
  variant,
  size,
  fullWidth,
  icon,
  className,
  children,
  ...rest
}: ButtonStyleProps & LinkProps) {
  return (
    <Link {...rest} className={classes({ variant, size, fullWidth }, className)}>
      {icon}
      {children}
    </Link>
  );
}
