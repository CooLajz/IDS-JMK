// Render provider text as text, never as HTML. Preserve expanded notices across refreshes.
export function renderAlerts(container, data) {
  const open = new Set([...container.querySelectorAll('details[open]')].map(d=>d.dataset.key));
  container.replaceChildren();
  container.hidden = !data || data.realtime_enabled === false || (Array.isArray(data.alerts) && !data.alerts.length && !data.alerts_stale);
  if (container.hidden) return;
  const heading=document.createElement('h2');heading.textContent='Upozornění na dopravu';container.append(heading);
  if (!Array.isArray(data.alerts) || data.alerts_stale) {
    const message=document.createElement('p');
    message.textContent=Array.isArray(data.alerts) ? 'Upozornění nejsou aktuální. Stav omezení nyní nelze ověřit.' : 'Tento server zatím neposkytuje upozornění. Aktualizujte API server.';
    container.append(message);return;
  }
  for (const alert of data.alerts) {
    const details=document.createElement('details');details.dataset.key=alert.key || alert.id;details.open=open.has(details.dataset.key);
    const summary=document.createElement('summary');summary.textContent=alert.description?.split('\n').find(s=>s.trim()) || alert.title || 'Upozornění';
    const lines=document.createElement('span');lines.className='alert-lines';lines.textContent=`Linky: ${(alert.matched_lines || []).join(', ')}${alert.scope==='line' ? ' · Omezení na lince, podrobnosti v textu' : ''}`;
    summary.append(lines);
    const text=document.createElement('p');text.className='alert-description';text.textContent=alert.description || alert.title;
    details.append(summary,text);
    try {
      const url=new URL(alert.url);
      if (['https:','http:'].includes(url.protocol)) {
        const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent='Informace dopravního systému ↗';details.append(link);
      }
    } catch { /* Missing or unsafe source URLs are not links. */ }
    container.append(details);
  }
}
