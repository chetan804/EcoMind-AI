import type { Shot } from '../content';

/** A real screenshot in a window frame with its caption. Lazy-loaded, with its size fixed to avoid layout shift. */
export function ProductShot({ shot, priority = false }: { shot: Shot; priority?: boolean }) {
  return (
    <figure className="shot">
      <div className="shot__frame">
        <div className="shot__bar" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <img src={shot.src} alt={shot.alt} width={1200} height={750} loading={priority ? 'eager' : 'lazy'} decoding="async" className="shot__img" />
      </div>
      <figcaption className="shot__caption">{shot.caption}</figcaption>
    </figure>
  );
}
