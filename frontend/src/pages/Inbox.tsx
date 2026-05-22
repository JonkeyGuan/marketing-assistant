import React, { useEffect, useState } from 'react';
import { authFetch } from '../auth/authFetch';
import { useVerticalConfig } from '../config/VerticalConfigProvider';


interface Email {
  id: string;
  from_name: string;
  from_email: string;
  to_name: string;
  to_email: string;
  subject: string;
  body: string;
  date: string;
  read: boolean;
  customer_id?: string;
}

export default function Inbox() {
  const vcfg = useVerticalConfig();
  const [emails, setEmails] = useState<Email[]>([]);
  const [selected, setSelected] = useState<Email | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterEmail, setFilterEmail] = useState('');

  useEffect(() => {
    if (!filterEmail && (vcfg as any).default_inbox_email) {
      setFilterEmail((vcfg as any).default_inbox_email);
    }
  }, [vcfg]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (filterEmail) {
      fetchInbox();
      const interval = setInterval(fetchInbox, 10000);
      return () => clearInterval(interval);
    }
  }, [filterEmail]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchInbox = async () => {
    try {
      const url = filterEmail
        ? `/api/inbox?email=${encodeURIComponent(filterEmail)}`
        : '/api/inbox';
      const resp = await authFetch(url);
      if (resp.ok) {
        const data = await resp.json();
        setEmails(data);
      }
    } catch {} finally { setLoading(false); }
  };

  const openEmail = async (email: Email) => {
    setSelected(email);
    if (!email.read) {
      await authFetch(`/api/inbox/${email.id}/read`, { method: 'POST' });
      setEmails(prev => prev.map(e => e.id === email.id ? { ...e, read: true } : e));
    }
  };

  const formatDate = (d: string) => {
    const date = new Date(d);
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Get unique recipients for the filter dropdown
  const recipients = Array.from(new Set(emails.map(e => e.to_email))).map(email => {
    const match = emails.find(e => e.to_email === email);
    return { email, name: match?.to_name || email };
  });

  const filteredEmails = emails;

  const unreadCount = filteredEmails.filter(e => !e.read).length;
  const currentRecipient = recipients.find(r => r.email === filterEmail);

  if (selected) {
    return (
      <div className="min-h-screen bg-surface">
        <header className="bg-surface-container-lowest border-b border-outline-variant/30 px-6 py-3 flex items-center justify-between sticky top-0 z-50">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-2xl text-red-500">mail</span>
            <span className="text-lg font-bold text-on-surface font-headline">Mail</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-on-surface-variant">
            <span className="material-symbols-outlined text-sm">account_circle</span>
            <span>{selected.to_name}</span>
          </div>
        </header>
        <div className="max-w-4xl mx-auto px-4 pt-6">
          <button
            onClick={() => setSelected(null)}
            className="flex items-center gap-2 text-on-surface-variant hover:text-on-surface mb-6 font-medium"
          >
            <span className="material-symbols-outlined">arrow_back</span>
            Back to Inbox
          </button>

          <div className="bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/20 overflow-hidden">
            <div className="p-8 border-b border-outline-variant/20">
              <h1 className="text-2xl font-headline font-bold text-on-surface mb-4">{selected.subject}</h1>
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-full bg-primary-container flex items-center justify-center">
                  <span className="text-sm font-bold text-on-primary-container">{selected.from_name.charAt(0)}</span>
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-on-surface">{selected.from_name}</span>
                    <span className="text-on-surface-variant text-sm">&lt;{selected.from_email}&gt;</span>
                  </div>
                  <div className="text-sm text-on-surface-variant">
                    to {selected.to_name} &lt;{selected.to_email}&gt;
                  </div>
                </div>
                <span className="ml-auto text-sm text-on-surface-variant">
                  {new Date(selected.date).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true })}
                </span>
              </div>
            </div>
            <div className="p-8">
              <div
                className="prose prose-sm max-w-none text-on-surface leading-relaxed"
                dangerouslySetInnerHTML={{ __html: selected.body }}
              />
              {selected.customer_id && (
                <div className="mt-8 pt-6 border-t border-outline-variant/20 flex flex-col items-center gap-3">
                  <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">Your Personalized Experience</p>
                  <div className="bg-white p-3 rounded-xl shadow-sm">
                    <img
                      alt="Personalized QR Code"
                      className="w-32 h-32"
                      src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent((selected as any).campaign_url || '')}`}
                    />
                  </div>
                  <p className="text-xs text-on-surface-variant">Scan to view your exclusive campaign page</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-surface">
      <header className="bg-surface-container-lowest border-b border-outline-variant/30 px-6 py-3 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-3">
          <span className="material-symbols-outlined text-2xl text-red-500">mail</span>
          <span className="text-lg font-bold text-on-surface font-headline">Mail</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-on-surface-variant">
          <span className="material-symbols-outlined text-sm">account_circle</span>
          <span>{currentRecipient?.name || 'Inbox'}</span>
        </div>
      </header>
      <div className="max-w-4xl mx-auto px-4 pt-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-3xl text-primary">inbox</span>
            <div>
              <h1 className="text-2xl font-headline font-bold text-on-surface">
                Inbox
              </h1>
              <p className="text-sm text-on-surface-variant">
                {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
              </p>
            </div>
          </div>
          <button onClick={fetchInbox} className="p-2 hover:bg-surface-container-high rounded-lg transition-all">
            <span className="material-symbols-outlined text-on-surface-variant">refresh</span>
          </button>
        </div>

        {/* Recipient filter */}
        {recipients.length > 1 && (
          <div className="mb-4">
            <select
              value={filterEmail}
              onChange={(e) => setFilterEmail(e.target.value)}
              className="bg-surface-container-lowest border border-outline-variant/30 rounded-lg px-4 py-2.5 text-sm font-medium focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all w-full max-w-sm"
            >
              <option value="">All Inboxes</option>
              {recipients.map(r => (
                <option key={r.email} value={r.email}>{r.name} ({r.email})</option>
              ))}
            </select>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : filteredEmails.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-on-surface-variant">
            <span className="material-symbols-outlined text-5xl mb-3 opacity-30">mail</span>
            <p>{filterEmail ? 'No emails for this recipient' : 'No emails yet'}</p>
          </div>
        ) : (
          <div className="bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant/20 overflow-hidden divide-y divide-outline-variant/10">
            {filteredEmails.map((email) => (
              <div
                key={email.id}
                onClick={() => openEmail(email)}
                className={`flex items-center gap-4 px-6 py-4 cursor-pointer transition-all hover:bg-surface-container-low ${!email.read ? 'bg-primary/[0.03]' : ''}`}
              >
                <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${!email.read ? 'bg-primary-container' : 'bg-surface-container-high'}`}>
                  <span className={`text-xs font-bold ${!email.read ? 'text-on-primary-container' : 'text-on-surface-variant'}`}>
                    {email.from_name.charAt(0)}
                  </span>
                </div>
                <div className="flex-grow min-w-0">
                  <span className={`text-sm truncate block ${!email.read ? 'font-bold text-on-surface' : 'font-medium text-on-surface-variant'}`}>
                    {email.from_name}
                  </span>
                  <span className={`text-sm truncate block ${!email.read ? 'font-semibold text-on-surface' : 'text-on-surface-variant'}`}>
                    {email.subject}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {!email.read && <span className="w-2.5 h-2.5 rounded-full bg-primary"></span>}
                  <span className={`text-xs ${!email.read ? 'font-bold text-primary' : 'text-on-surface-variant'}`}>
                    {formatDate(email.date)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
