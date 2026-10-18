/** EcoMind mark: a ring (the loop) holding a leaf with a vein. Decorative; the wordmark carries the name. */
export function BrandMark({ className = 'brand__mark' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 36 36" fill="none" aria-hidden="true" focusable="false">
      <circle cx="18" cy="18" r="15" stroke="var(--color-teal)" strokeWidth="2.5" strokeDasharray="78 16" strokeLinecap="round" transform="rotate(-70 18 18)" />
      <path d="M11.5 22.5c0-6.2 4.6-10.4 12-11 .3 7.2-3.6 12.1-10.3 12.1-.6 0-1.1-.1-1.7-.2z" fill="var(--color-primary)" />
      <path d="M12.8 23.2c2.7-3.6 5.4-6.1 8.6-8" stroke="var(--color-bg)" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  );
}

export function Brand({ name = 'EcoMind AI' }: { name?: string }) {
  return (
    <>
      <BrandMark />
      <span>{name}</span>
    </>
  );
}
