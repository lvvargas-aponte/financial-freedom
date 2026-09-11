import React, { useState } from 'react';
import { fmt$ } from '../../utils/formatting';
import { userMessage } from '../../utils/errorMessage';
import { AlertIcon } from './icons';

function monthLabel(key) {
  const [y, m] = key.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}

function defaultEnd(periods, currentPeriod) {
  const finished = periods.filter((p) => p < currentPeriod);
  return finished.length >= 2 ? finished[finished.length - 1] : periods[periods.length - 1];
}

// Closing several open months with one payment. The figures come from each
// month's worksheet, so the preview is what the sheet will say; a month the
// app sees differently is flagged before anyone pays against it.
export default function CloseTogetherPanel({
  periods,
  currentPeriod,
  onPreview,
  onConfirm,
  onCancel,
}) {
  const [start, setStart] = useState(periods[0] || '');
  const [end, setEnd] = useState(defaultEnd(periods, currentPeriod) || '');
  const [preview, setPreview] = useState(null);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const validRange = start && end && end > start;

  const pick = (setter) => (e) => {
    setter(e.target.value);
    setPreview(null);
    setError(null);
  };

  const runPreview = async () => {
    setBusy(true);
    setError(null);
    try {
      setPreview(await onPreview(start, end));
    } catch (e) {
      setError(userMessage(e, 'Could not preview those months — please try again.'));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await onConfirm(start, end, note);
    } catch (e) {
      setError(userMessage(e, 'Could not close those months — please try again.'));
      setBusy(false);
    }
  };

  const blocked = preview && preview.blockers.length > 0;

  return (
    <section className="sh-ct" aria-label="Close several months">
      <div className="sh-ct-head">
        <b>Close several months together</b>
        <span className="sh-ct-sub">One payment settles every month in the range.</span>
      </div>

      <div className="sh-ct-range">
        <label className="sh-paid-label" htmlFor="ct-start">From</label>
        <select id="ct-start" className="sh-paid-input" value={start} onChange={pick(setStart)}>
          {periods.map((p) => <option key={p} value={p}>{monthLabel(p)}</option>)}
        </select>
        <label className="sh-paid-label" htmlFor="ct-end">To</label>
        <select id="ct-end" className="sh-paid-input" value={end} onChange={pick(setEnd)}>
          {periods.map((p) => <option key={p} value={p}>{monthLabel(p)}</option>)}
        </select>
        <button
          type="button"
          className="sh-mini"
          onClick={runPreview}
          disabled={busy || !validRange}
        >
          Preview
        </button>
        {!validRange && <span className="sh-ct-sub">Pick at least two months.</span>}
      </div>

      {preview && (
        <>
          <ul className="sh-ct-months">
            {preview.months.map((m) => (
              <li key={m.period}>
                <span className="sh-ct-month">{m.label}</span>
                <span>
                  {m.net === 0 ? 'Even' : `${m.debtor} owes ${m.creditor} ${fmt$(m.net)}`}
                </span>
                {m.mismatch && (
                  <span className="sh-ct-flag">
                    <AlertIcon size={12} />
                    The app has {fmt$(Math.abs(m.app_net || 0))} for this month — sync it first.
                  </span>
                )}
              </li>
            ))}
          </ul>

          {blocked ? (
            <div className="sh-settle-warn" role="alert">
              <AlertIcon size={14} />
              <span>{preview.blockers.join(' ')}</span>
            </div>
          ) : (
            <div className="sh-ct-total" data-testid="ct-total">
              {preview.total.net === 0
                ? 'Even overall — nobody owes anything.'
                : `${preview.total.debtor} pays ${preview.total.creditor} ${fmt$(preview.total.net)} in total`}
            </div>
          )}
        </>
      )}

      {error && (
        <div className="sh-settle-warn" role="alert">
          <AlertIcon size={14} />
          <span>{error}</span>
        </div>
      )}

      <div className="sh-ct-actions">
        {preview && !blocked && (
          <>
            <label className="sh-paid-label" htmlFor="ct-note">How was it settled? (optional)</label>
            <input
              id="ct-note"
              className="sh-paid-input"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="via Zelle"
            />
            <button type="button" className="sh-mini sh-mini--go" onClick={confirm} disabled={busy}>
              {busy ? 'Closing…' : `Close ${preview.months.length} months`}
            </button>
          </>
        )}
        <button type="button" className="sh-mini" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </section>
  );
}
