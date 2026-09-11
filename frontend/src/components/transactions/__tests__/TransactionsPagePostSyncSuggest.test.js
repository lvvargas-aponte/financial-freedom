import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import axios from 'axios';
import TransactionsPage from '../TransactionsPage';
import { SyncContext } from '../../../contexts/SyncContext';

jest.mock('axios');

const txn = (id, over = {}) => ({
  id, transaction_id: id,
  date: '2026-09-05', description: `MERCHANT ${id}`, amount: -10,
  source: 'simplefin', institution: 'Bank',
  is_shared: false, reviewed: false, category: '',
  person_1_owes: 0, person_2_owes: 0, notes: '', transaction_type: 'debit',
  ...over,
});

const TRANSACTIONS = [txn('new-1'), txn('new-2', { category: 'Groceries' }), txn('old-1')];

function fakeSync(over = {}) {
  return {
    registerSyncPage: jest.fn(),
    setShowAccountsModal: jest.fn(),
    setShowSyncModal: jest.fn(),
    syncing: false,
    uploading: false,
    sendingSheet: false,
    accountsRefreshKey: 0,
    handleCsvPicked: jest.fn(),
    sendToSheet: jest.fn(),
    newTransactionIds: [],
    clearNewTransactionIds: jest.fn(),
    ...over,
  };
}

const renderPage = (sync) => render(
  <MemoryRouter>
    <SyncContext.Provider value={sync}>
      <TransactionsPage view="current" />
    </SyncContext.Provider>
  </MemoryRouter>,
);

beforeEach(() => {
  jest.clearAllMocks();
  axios.get.mockImplementation((url) => {
    if (url.includes('transactions/all')) return Promise.resolve({ data: TRANSACTIONS });
    if (url.includes('person-names')) return Promise.resolve({ data: { person_1: 'A', person_2: 'B' } });
    if (url.includes('/api/balances/summary')) return Promise.resolve({ data: { accounts: [] } });
    if (url.includes('/api/categories')) return Promise.resolve({ data: { categories: [] } });
    return Promise.resolve({ data: [] });
  });
  axios.post.mockResolvedValue({
    data: {
      ai_available: true,
      candidates: ['Coffee'],
      results: [{ id: 'new-1', description: 'MERCHANT new-1', amount: 10, suggested_category: 'Coffee', source: 'ai' }],
      skipped_ids: [],
      not_found: [],
    },
  });
});

test('a sync that brought in uncategorized rows opens the suggestions for just those', async () => {
  const sync = fakeSync({ newTransactionIds: ['new-1', 'new-2'] });
  renderPage(sync);

  expect(await screen.findByText('Suggest categories')).toBeInTheDocument();
  expect(axios.post).toHaveBeenCalledWith(
    expect.stringContaining('/api/transactions/suggest-categories/bulk'),
    { transaction_ids: ['new-1'] },
  );
  expect(sync.clearNewTransactionIds).toHaveBeenCalled();
});

test('nothing is suggested when everything new already has a category', async () => {
  const sync = fakeSync({ newTransactionIds: ['new-2'] });
  renderPage(sync);

  await waitFor(() => expect(sync.clearNewTransactionIds).toHaveBeenCalled());
  expect(axios.post).not.toHaveBeenCalled();
  expect(screen.queryByText('Suggest categories')).not.toBeInTheDocument();
});

test('an empty answer from the suggester opens nothing', async () => {
  axios.post.mockResolvedValue({
    data: { ai_available: true, candidates: [], results: [], skipped_ids: ['new-1'], not_found: [] },
  });
  const sync = fakeSync({ newTransactionIds: ['new-1'] });
  renderPage(sync);

  await waitFor(() => expect(axios.post).toHaveBeenCalled());
  expect(screen.queryByText('Suggest categories')).not.toBeInTheDocument();
});

test('a page load with no sync behind it suggests nothing', async () => {
  renderPage(fakeSync());

  await screen.findByText('MERCHANT old-1');
  expect(axios.post).not.toHaveBeenCalled();
});
