// Only the server's attribute-free formatting subset may become markup.
const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
export function alertMarkup(alert) {
  const html = alert.description_html || alert.title_html;
  if (typeof html === 'string' && !/[<>]/.test(html.replace(/<\/?(?:p|br|strong|em|u|ul|ol|li)>/g, ''))) return html;
  return escape(alert.description || alert.title);
}
// Preserve expanded notices across refreshes.
export function renderAlerts(container, data, scope = data?.stop?.id || '') {
  const previousGroup = container.querySelector('.alerts-group');
  const sameScope = previousGroup?.dataset.scope === scope;
  const groupOpen = sameScope ? previousGroup.open : (data?.alerts?.length || 0) <= 2;
  const focusedGroup = previousGroup?.firstElementChild === document.activeElement;
  const open = new Set(sameScope ? [...container.querySelectorAll('details[data-key][open]')].map(d=>d.dataset.key) : []);
  container.replaceChildren();
  container.hidden = !data || data.realtime_enabled === false || (Array.isArray(data.alerts) && !data.alerts.length && !data.alerts_stale);
  if (container.hidden) return;
  if (!Array.isArray(data.alerts) || data.alerts_stale) {
    const heading=document.createElement('h2');heading.textContent='Upozornění na dopravu';container.append(heading);
    const message=document.createElement('p');
    message.textContent=Array.isArray(data.alerts) ? 'Upozornění nejsou aktuální. Stav omezení nyní nelze ověřit.' : 'Tento server zatím neposkytuje upozornění. Aktualizujte API server.';
    container.append(message);return;
  }
  const group=document.createElement('details');group.className='alerts-group';group.dataset.scope=scope;group.open=groupOpen;
  const groupSummary=document.createElement('summary');groupSummary.className='alerts-summary';groupSummary.textContent=`Upozornění na dopravu (${data.alerts.length})`;
  const list=document.createElement('div');list.className='alerts-list';
  group.append(groupSummary,list);container.append(group);
  if (focusedGroup) groupSummary.focus({preventScroll:true});
  for (const alert of data.alerts) {
    const details=document.createElement('details');details.dataset.key=alert.key || alert.id;details.open=open.has(details.dataset.key);
    const summary=document.createElement('summary');summary.textContent=alert.description?.split('\n').find(s=>s.trim()) || alert.title || 'Upozornění';
    const lines=document.createElement('span');lines.className='alert-lines';lines.textContent=`Linky: ${(alert.matched_lines || []).join(', ')}${alert.scope==='line' ? ' · Omezení na lince, podrobnosti v textu' : ''}`;
    summary.append(lines);
    const text=document.createElement('div');text.className='alert-description';
    text.innerHTML=alertMarkup(alert);
    if (alert.description_html || alert.title_html) text.classList.add('rich');
    details.append(summary,text);
    try {
      const url=new URL(alert.url);
      if (['https:','http:'].includes(url.protocol)) {
        const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent='Informace dopravního systému ↗';details.append(link);
      }
    } catch { /* Missing or unsafe source URLs are not links. */ }
    list.append(details);
  }
}
