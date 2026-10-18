import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { ConfirmDialog, Dialog } from '@/components/ui/Dialog';
import { Menu } from '@/components/ui/Menu';
import { Tabs } from '@/components/ui/Tabs';

describe('Tabs', () => {
  const items = [
    { id: 'a', label: 'Alpha', panel: <p>Alpha content</p> },
    { id: 'b', label: 'Beta', panel: <p>Beta content</p> },
    { id: 'c', label: 'Gamma', panel: <p>Gamma content</p> },
  ];

  it('shows the selected panel and switches on click', async () => {
    render(<Tabs label="Sections" items={items} />);
    expect(screen.getByText('Alpha content')).toBeVisible();
    await userEvent.click(screen.getByRole('tab', { name: 'Beta' }));
    expect(screen.getByText('Beta content')).toBeVisible();
    expect(screen.queryByText('Alpha content')).not.toBeInTheDocument();
  });

  it('supports arrow, Home and End keys with a roving tabindex', async () => {
    render(<Tabs label="Sections" items={items} />);
    await userEvent.tab();
    expect(screen.getByRole('tab', { name: 'Alpha' })).toHaveFocus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Beta' })).toHaveFocus();
    expect(screen.getByRole('tab', { name: 'Beta' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Alpha' })).toHaveAttribute('tabindex', '-1');
    await userEvent.keyboard('{End}');
    expect(screen.getByRole('tab', { name: 'Gamma' })).toHaveFocus();
    await userEvent.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: 'Alpha' })).toHaveFocus();
    await userEvent.keyboard('{ArrowLeft}');
    expect(screen.getByRole('tab', { name: 'Gamma' })).toHaveFocus();
  });

  it('links panels to tabs for assistive technology', () => {
    render(<Tabs label="Sections" items={items} />);
    expect(screen.getByRole('tabpanel')).toHaveAccessibleName('Alpha');
  });
});

describe('Dialog', () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          Open
        </button>
        <Dialog open={open} onClose={() => setOpen(false)} title="Example" description="Described.">
          <p>Body</p>
        </Dialog>
      </>
    );
  }

  it('opens with an accessible name and description, and closes from its close button', async () => {
    render(<Harness />);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Open' }));
    const dialog = screen.getByRole('dialog', { name: 'Example' });
    expect(dialog).toHaveAccessibleDescription('Described.');
    await userEvent.click(screen.getByRole('button', { name: 'Close dialog' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('moves focus to the element marked data-autofocus instead of the close button', async () => {
    render(
      <Dialog open onClose={() => {}} title="Find">
        <input aria-label="Query" data-autofocus />
      </Dialog>,
    );
    expect(screen.getByLabelText('Query')).toHaveFocus();
  });

  it('confirm dialog reports the chosen action', async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog open onCancel={onCancel} onConfirm={onConfirm} title="Delete?" description="This cannot be undone." confirmLabel="Delete" destructive />);
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

describe('Menu', () => {
  function renderMenu(onSelect = vi.fn()) {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route
            path="/"
            element={
              <Menu
                label="Account menu"
                trigger={<span>Guest</span>}
                items={[
                  { id: 'one', label: 'Run action', onSelect },
                  { id: 'two', label: 'Go there', to: '/there' },
                ]}
              />
            }
          />
          <Route path="/there" element={<p>There</p>} />
        </Routes>
      </MemoryRouter>,
    );
    return onSelect;
  }

  it('opens from the keyboard, moves with arrows, runs an action, and returns focus to the trigger', async () => {
    const onSelect = renderMenu();
    const trigger = screen.getByRole('button', { name: 'Account menu' });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    trigger.focus();
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(await screen.findByRole('menuitem', { name: 'Run action' })).toHaveFocus();
    await userEvent.keyboard('{ArrowDown}');
    expect(screen.getByRole('menuitem', { name: 'Go there' })).toHaveFocus();
    await userEvent.keyboard('{ArrowUp}{Enter}');
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('closes with Escape and restores focus', async () => {
    renderMenu();
    const trigger = screen.getByRole('button', { name: 'Account menu' });
    await userEvent.click(trigger);
    expect(screen.getByRole('menu')).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('closes when clicking outside', async () => {
    renderMenu();
    await userEvent.click(screen.getByRole('button', { name: 'Account menu' }));
    await userEvent.click(document.body);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });

  it('navigates when a link item is chosen', async () => {
    renderMenu();
    await userEvent.click(screen.getByRole('button', { name: 'Account menu' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'Go there' }));
    expect(screen.getByText('There')).toBeInTheDocument();
  });
});
