import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { Alert } from '@/components/feedback/Alert';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Checkbox, Radio, RadioGroup, Switch } from '@/components/ui/Choice';
import { Field } from '@/components/ui/Field';
import { IconButton } from '@/components/ui/IconButton';
import { Input, PasswordInput, Select } from '@/components/ui/Input';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Pagination, Table } from '@/components/ui/Table';
import { Tooltip } from '@/components/ui/Tooltip';

describe('Button', () => {
  it('runs its handler when clicked', async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('an unavailable button is announced as disabled, explains why, stays focusable and ignores clicks', async () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} unavailableReason="Needs the classification service.">
        Verify
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Verify' });
    expect(button).toHaveAttribute('aria-disabled', 'true');
    expect(button).not.toBeDisabled();
    expect(button).toHaveAccessibleDescription('Needs the classification service.');
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
    button.blur();
    await userEvent.tab();
    expect(button).toHaveFocus();
  });

  it('defaults to type="button" so it never submits a form by accident', () => {
    render(<Button>Go</Button>);
    expect(screen.getByRole('button')).toHaveAttribute('type', 'button');
  });
});

describe('IconButton', () => {
  it('uses its label as the accessible name', () => {
    render(<IconButton label="Close" icon={<span />} />);
    expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
  });
});

describe('Field', () => {
  it('associates label, hint and error with the control', () => {
    render(
      <Field label="Email" hint="We never share it." error="Enter a valid email." required>
        {(control) => <Input {...control} />}
      </Field>,
    );
    const input = screen.getByLabelText(/Email/);
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAttribute('aria-required', 'true');
    expect(input).toHaveAccessibleDescription('We never share it. Enter a valid email.');
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid email.');
  });

  it('does not mark a valid field as invalid', () => {
    render(<Field label="Name">{(control) => <Input {...control} />}</Field>);
    expect(screen.getByLabelText('Name')).not.toHaveAttribute('aria-invalid');
  });
});

describe('PasswordInput', () => {
  it('toggles visibility with an accessible pressed button', async () => {
    render(<PasswordInput aria-label="Password" />);
    const input = screen.getByLabelText('Password');
    expect(input).toHaveAttribute('type', 'password');
    await userEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(input).toHaveAttribute('type', 'text');
    expect(screen.getByRole('button', { name: 'Hide password' })).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('Select, Checkbox, Switch, Radio', () => {
  it('select changes value', async () => {
    render(
      <Select aria-label="Range" defaultValue="7">
        <option value="7">7 days</option>
        <option value="30">30 days</option>
      </Select>,
    );
    await userEvent.selectOptions(screen.getByLabelText('Range'), '30');
    expect(screen.getByLabelText('Range')).toHaveValue('30');
  });

  it('checkbox and switch toggle and expose their roles', async () => {
    render(
      <>
        <Checkbox label="Agree" />
        <Switch label="Notifications" />
      </>,
    );
    await userEvent.click(screen.getByRole('checkbox', { name: 'Agree' }));
    expect(screen.getByRole('checkbox', { name: 'Agree' })).toBeChecked();
    await userEvent.click(screen.getByRole('switch', { name: 'Notifications' }));
    expect(screen.getByRole('switch', { name: 'Notifications' })).toBeChecked();
  });

  it('radios in a group are mutually exclusive and named by the legend', async () => {
    render(
      <RadioGroup legend="Horizon">
        <Radio name="h" label="7 days" defaultChecked />
        <Radio name="h" label="30 days" />
      </RadioGroup>,
    );
    const group = screen.getByRole('group', { name: 'Horizon' });
    await userEvent.click(within(group).getByRole('radio', { name: '30 days' }));
    expect(within(group).getByRole('radio', { name: '7 days' })).not.toBeChecked();
  });
});

describe('feedback components', () => {
  it('danger alerts are assertive, others are polite status messages', () => {
    render(
      <>
        <Alert tone="danger">Failed</Alert>
        <Alert tone="info">FYI</Alert>
      </>,
    );
    expect(screen.getByRole('alert')).toHaveTextContent('Failed');
    expect(screen.getByRole('status')).toHaveTextContent('FYI');
  });

  it('empty state renders title, description and action', () => {
    render(<EmptyState title="Nothing here" description="Add something." action={<button type="button">Add</button>} />);
    expect(screen.getByRole('heading', { name: 'Nothing here' })).toBeInTheDocument();
    expect(screen.getByText('Add something.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument();
  });

  it('badge shows its text (colour is never the only signal)', () => {
    render(<Badge tone="danger">Unreachable</Badge>);
    expect(screen.getByText('Unreachable')).toBeInTheDocument();
  });
});

describe('ProgressBar', () => {
  it('exposes name and clamped value to assistive technology', () => {
    render(<ProgressBar label="Upload" value={140} />);
    const bar = screen.getByRole('progressbar', { name: 'Upload' });
    expect(bar).toHaveAttribute('aria-valuenow', '100');
    expect(bar).toHaveAttribute('aria-valuemax', '100');
  });
});

describe('Tooltip', () => {
  it('shows on focus, describes the control and closes with Escape', async () => {
    render(
      <Tooltip content="Explains the action">
        <button type="button">Act</button>
      </Tooltip>,
    );
    const tip = screen.getByRole('tooltip', { hidden: true });
    expect(tip).not.toBeVisible();
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Act' })).toHaveAccessibleDescription('Explains the action');
    expect(tip).toBeVisible();
    await userEvent.keyboard('{Escape}');
    expect(tip).not.toBeVisible();
  });
});

describe('Table and Pagination', () => {
  it('table has a caption as its accessible name', () => {
    render(
      <Table caption="Vehicles">
        <thead>
          <tr>
            <th scope="col">Plate</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>X1</td>
          </tr>
        </tbody>
      </Table>,
    );
    expect(screen.getByRole('table', { name: 'Vehicles' })).toBeInTheDocument();
  });

  it('pagination disables the edges and reports page changes', async () => {
    const onPageChange = vi.fn();
    render(<Pagination page={1} pageCount={3} onPageChange={onPageChange} />);
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});

it('renders router-aware components inside a router', () => {
  render(
    <MemoryRouter>
      <Button>Plain</Button>
    </MemoryRouter>,
  );
  expect(screen.getByRole('button', { name: 'Plain' })).toBeInTheDocument();
});
