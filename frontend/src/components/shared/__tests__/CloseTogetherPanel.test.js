import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CloseTogetherPanel from '../CloseTogetherPanel';

const PERIODS = ['2026-06', '2026-07', '2026-08', '2026-09'];

function preview(overrides = {}) {
  return {
    start: '2026-06',
    end: '2026-08',
    label: 'June–August 2026',
    months: [
      { period: '2026-06', label: 'June 2026', net: 949.12, debtor: 'Valeria', creditor: 'Christy', sheet_net: -949.12, app_net: -909.23, mismatch: true },
      { period: '2026-07', label: 'July 2026', net: 2553.76, debtor: 'Christy', creditor: 'Valeria', sheet_net: 2553.76, app_net: 2553.76, mismatch: false },
      { period: '2026-08', label: 'August 2026', net: 500, debtor: 'Christy', creditor: 'Valeria', sheet_net: 500, app_net: 500, mismatch: false },
    ],
    total: { net: 2104.64, debtor: 'Christy', creditor: 'Valeria', net_for_me: 2104.64 },
    blockers: [],
    ...overrides,
  };
}

const renderPanel = (handlers = {}) =>
  render(
    <CloseTogetherPanel
      periods={PERIODS}
      currentPeriod="2026-09"
      onPreview={jest.fn().mockResolvedValue(preview())}
      onConfirm={jest.fn().mockResolvedValue(undefined)}
      onCancel={jest.fn()}
      {...handlers}
    />,
  );

test('defaults to every finished month', () => {
  renderPanel();

  expect(screen.getByLabelText('From')).toHaveValue('2026-06');
  expect(screen.getByLabelText('To')).toHaveValue('2026-08');
});

test('the preview lists each month and the one payment', async () => {
  const onPreview = jest.fn().mockResolvedValue(preview());
  renderPanel({ onPreview });

  await userEvent.click(screen.getByRole('button', { name: /preview/i }));

  expect(onPreview).toHaveBeenCalledWith('2026-06', '2026-08');
  expect(within(screen.getByRole('list')).getByText('July 2026')).toBeInTheDocument();
  expect(screen.getByText('Valeria owes Christy $949.12')).toBeInTheDocument();
  expect(screen.getByTestId('ct-total')).toHaveTextContent('Christy pays Valeria $2,104.64 in total');
});

test('a month the app sees differently is flagged', async () => {
  renderPanel();
  await userEvent.click(screen.getByRole('button', { name: /preview/i }));

  expect(screen.getByText(/the app has \$909\.23 for this month/i)).toBeInTheDocument();
});

test('a blocked run explains why and offers no way to close', async () => {
  renderPanel({
    onPreview: jest.fn().mockResolvedValue(
      preview({ blockers: ['July 2026 is already marked paid in full by Christy.'] }),
    ),
  });
  await userEvent.click(screen.getByRole('button', { name: /preview/i }));

  expect(screen.getByRole('alert')).toHaveTextContent('already marked paid in full');
  expect(screen.queryByRole('button', { name: /close 3 months/i })).not.toBeInTheDocument();
});

test('closing passes the range and the note on', async () => {
  const onConfirm = jest.fn().mockResolvedValue(undefined);
  renderPanel({ onConfirm });

  await userEvent.click(screen.getByRole('button', { name: /preview/i }));
  await userEvent.type(screen.getByLabelText(/how was it settled/i), 'via Zelle');
  await userEvent.click(screen.getByRole('button', { name: /close 3 months/i }));

  expect(onConfirm).toHaveBeenCalledWith('2026-06', '2026-08', 'via Zelle');
});

test('a refused close is shown in the panel', async () => {
  const onConfirm = jest.fn().mockRejectedValue({
    response: { status: 409, data: { detail: 'July 2026 is already marked paid in full.' } },
  });
  renderPanel({ onConfirm });

  await userEvent.click(screen.getByRole('button', { name: /preview/i }));
  await userEvent.click(screen.getByRole('button', { name: /close 3 months/i }));

  expect(await screen.findByRole('alert')).toBeInTheDocument();
});

test('a range of one month cannot be previewed', async () => {
  renderPanel();
  await userEvent.selectOptions(screen.getByLabelText('To'), '2026-06');

  expect(screen.getByRole('button', { name: /preview/i })).toBeDisabled();
  expect(screen.getByText(/pick at least two months/i)).toBeInTheDocument();
});

test('changing the range drops a stale preview', async () => {
  renderPanel();
  await userEvent.click(screen.getByRole('button', { name: /preview/i }));
  await userEvent.selectOptions(screen.getByLabelText('To'), '2026-07');

  expect(screen.queryByTestId('ct-total')).not.toBeInTheDocument();
});
