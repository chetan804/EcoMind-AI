/**
 * Compatibility check for the locked form stack (React Hook Form + Zod + @hookform/resolvers)
 * against the installed React and Zod majors. Feature forms will build on this combination.
 */
import { zodResolver } from '@hookform/resolvers/zod';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

const schema = z.object({ email: z.email('Enter a valid email') });
type Values = z.infer<typeof schema>;

function TestForm({ onValid }: { onValid: (values: Values) => void }) {
  const { register, handleSubmit, formState } = useForm<Values>({ resolver: zodResolver(schema) });
  return (
    <form onSubmit={(event) => void handleSubmit(onValid)(event)}>
      <label>
        Email
        <input {...register('email')} />
      </label>
      {formState.errors.email && <p role="alert">{formState.errors.email.message}</p>}
      <button type="submit">Save</button>
    </form>
  );
}

describe('react-hook-form + zod', () => {
  it('blocks invalid input and submits valid input', async () => {
    const onValid = vi.fn();
    const user = userEvent.setup();
    render(<TestForm onValid={onValid} />);

    await user.type(screen.getByLabelText('Email'), 'nope');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a valid email');
    expect(onValid).not.toHaveBeenCalled();

    await user.clear(screen.getByLabelText('Email'));
    await user.type(screen.getByLabelText('Email'), 'a@example.org');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(onValid).toHaveBeenCalledTimes(1));
    expect(onValid.mock.calls[0]?.[0]).toEqual({ email: 'a@example.org' });
  });
});
