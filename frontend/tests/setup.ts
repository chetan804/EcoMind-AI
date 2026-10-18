import '@testing-library/jest-dom/vitest';

// jsdom does not implement the <dialog> modal API. This minimal stand-in only tracks the `open`
// attribute and fires `close`; real focus trapping and Escape handling are verified in a browser.
const dialogProto = Object.getPrototypeOf(document.createElement('dialog')) as HTMLDialogElement;
if (typeof dialogProto.showModal !== 'function') {
  dialogProto.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute('open', '');
  };
  dialogProto.close = function close(this: HTMLDialogElement) {
    this.removeAttribute('open');
    this.dispatchEvent(new Event('close'));
  };
}
