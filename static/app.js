document.addEventListener('DOMContentLoaded', () => {
    // ── Tab switching ───────────────────────────────────────────
    document.querySelectorAll('.tab').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            btn.classList.add('active');
            document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
        });
    });

    // ── Referral link ───────────────────────────────────────────
    const refLink = document.getElementById('refLink');
    const copyBtn = document.getElementById('copyRefBtn');
    if (refLink) {
        const link = location.origin + '/register?ref=' + CURRENT_USERNAME;
        refLink.textContent = link;
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(link);
            copyBtn.textContent = '✅ Скопировано!';
            setTimeout(() => copyBtn.textContent = '📋 Скопировать', 2000);
        });
    }

    // ── Data ─────────────────────────────────────────────────────
    let freeLeads = [];
    let myLeads = [];
    let hasActiveLead = false;
    let cooldownRemaining = 0;
    let cooldownTimer = null;

    // ── Cooldown check ───────────────────────────────────────────
    async function checkCooldown() {
        try {
            const r = await fetch('/api/cooldown');
            const data = await r.json();
            cooldownRemaining = data.cooldown || 0;
            startCooldownTimer();
        } catch(e) {}
    }

    function startCooldownTimer() {
        if (cooldownTimer) clearInterval(cooldownTimer);
        renderFreeTable();
        if (cooldownRemaining > 0) {
            cooldownTimer = setInterval(() => {
                cooldownRemaining--;
                renderFreeTable();
                if (cooldownRemaining <= 0) {
                    clearInterval(cooldownTimer);
                    cooldownTimer = null;
                }
            }, 1000);
        }
    }

    // ── Load free leads ──────────────────────────────────────────
    async function loadFreeLeads() {
        try {
            const r = await fetch('/api/leads/free');
            freeLeads = await r.json();
            renderFreeTable();
        } catch (e) { console.error(e); }
    }

    // ── Load my leads ────────────────────────────────────────────
    async function loadMyLeads() {
        try {
            const r = await fetch('/api/leads/my');
            myLeads = await r.json();
            // Check if user has an active lead (not deal/refused)
            hasActiveLead = myLeads.some(l => ['taken', 'in_progress', 'callback'].includes(l.status));
            renderMyTable();
            renderFreeTable(); // re-render to update claim buttons
        } catch (e) { console.error(e); }
    }

    // ── Load my deals ────────────────────────────────────────────
    async function loadMyDeals() {
        try {
            const r = await fetch('/api/deals/my');
            const deals = await r.json();
            renderMyDeals(deals);
        } catch (e) { console.error(e); }
    }

    // ── Render free leads table (ONLY name visible) ──────────────
    function renderFreeTable() {
        const tbody = document.getElementById('freeTableBody');
        const search = (document.getElementById('freeSearch')?.value || '').toLowerCase();
        const filtered = freeLeads.filter(l =>
            (l.name || '').toLowerCase().includes(search)
        );
        document.getElementById('freeCount').textContent = filtered.length;

        if (!filtered.length) {
            tbody.innerHTML = '<tr><td colspan="2" class="loading">Нет свободных клиентов</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(l => `
            <tr>
                <td class="name-cell">${esc(l.name) || 'Без названия'}</td>
                <td>
                    ${hasActiveLead
                        ? '<span style="color:var(--text-muted);font-size:.8rem">Завершите текущего клиента</span>'
                        : cooldownRemaining > 0
                        ? `<button class="btn btn-secondary btn-sm" disabled style="opacity:0.75">⏳ КД: ${cooldownRemaining} сек</button>`
                        : `<button class="btn btn-claim btn-sm" onclick="claimLead('${l.id}')">🚀 Взять клиента</button>`
                    }
                </td>
            </tr>
        `).join('');
    }

    // ── Render my leads table ────────────────────────────────────
    function renderMyTable() {
        const tbody = document.getElementById('myTableBody');
        if (!myLeads.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading">У вас пока нет клиентов. Возьмите клиента из свободного пула!</td></tr>';
            return;
        }
        tbody.innerHTML = myLeads.map(l => `
            <tr>
                <td class="name-cell">
                    ${esc(l.name) || 'Без названия'}
                    <div class="address">${esc(l.address) || ''}</div>
                </td>
                <td>${phoneHtml(l.phone)}</td>
                <td class="link-group">${linksHtml(l)}</td>
                <td><span class="status-badge status-${l.status}">${statusLabel(l.status)}</span></td>
                <td class="action-cell">
                    ${l.status !== 'deal' && l.status !== 'refused' ? `
                        <select class="status-select" onchange="updateStatus('${l.id}', this.value)">
                            <option value="taken" ${l.status==='taken'?'selected':''}>Взят</option>
                            <option value="in_progress" ${l.status==='in_progress'?'selected':''}>Звоню</option>
                            <option value="callback" ${l.status==='callback'?'selected':''}>Перезвонить</option>
                            <option value="refused" ${l.status==='refused'?'selected':''}>Отказ</option>
                        </select>
                        <button class="btn btn-success btn-inline" onclick="openDealModal('${l.id}','${esc(l.name)}')">💰 Сделка</button>
                        <button class="btn btn-danger btn-inline" onclick="releaseLead('${l.id}')">✕</button>
                    ` : l.status === 'deal' ? `
                        <span style="color:var(--success);font-size:.85rem">✅ ${l.deal_amount ? Number(l.deal_amount).toLocaleString('ru') + ' ₽' : 'Закрыта'}</span>
                    ` : `
                        <span style="color:var(--danger);font-size:.85rem">Отказ</span>
                        <button class="btn btn-secondary btn-inline" onclick="releaseLead('${l.id}')">Вернуть в пул</button>
                    `}
                </td>
            </tr>
        `).join('');
    }

    // ── Render my deals (with map links) ─────────────────────────
    function renderMyDeals(deals) {
        const tbody = document.getElementById('myDealsTableBody');
        if (!deals.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">Пока нет сделок</td></tr>';
            return;
        }
        tbody.innerHTML = deals.map(d => `
            <tr>
                <td class="name-cell">${esc(d.lead_name)}<div class="address">${esc(d.lead_phone)}</div></td>
                <td class="link-group">${dealLinksHtml(d)}</td>
                <td><strong>${Number(d.amount).toLocaleString('ru')} ₽</strong></td>
                <td>${d.commission_rate}%</td>
                <td style="color:var(--success);font-weight:600">${Number(d.commission_amount).toLocaleString('ru')} ₽</td>
                <td style="color:var(--text-muted);font-size:.85rem">${formatDate(d.created_at)}</td>
            </tr>
        `).join('');
    }

    // ── Actions ──────────────────────────────────────────────────
    window.claimLead = async function(id) {
        try {
            const r = await fetch(`/api/leads/${id}/claim`, { method: 'POST' });
            const data = await r.json();
            if (data.success) {
                checkCooldown();
                loadFreeLeads();
                loadMyLeads();
                refreshStats();
            } else {
                alert(data.error || 'Не удалось взять клиента');
                checkCooldown();
            }
        } catch(e) { alert('Ошибка сети'); }
    };

    window.releaseLead = async function(id) {
        if (!confirm('Вернуть клиента в свободный пул?')) return;
        await fetch(`/api/leads/${id}/release`, { method: 'POST' });
        checkCooldown();
        loadFreeLeads();
        loadMyLeads();
        refreshStats();
    };

    window.updateStatus = async function(id, status) {
        await fetch(`/api/leads/${id}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status })
        });
        if (status === 'refused') {
            checkCooldown();
        }
        loadMyLeads();
    };

    // ── Deal modal ───────────────────────────────────────────────
    let dealLeadId = null;
    const modal = document.getElementById('dealModal');
    const amountInput = document.getElementById('dealAmount');
    const commPreview = document.getElementById('dealCommPreview');

    window.openDealModal = function(id, name) {
        dealLeadId = id;
        document.getElementById('dealLeadName').textContent = name;
        amountInput.value = '';
        commPreview.textContent = '0 ₽';
        modal.classList.add('show');
        amountInput.focus();
    };

    amountInput?.addEventListener('input', () => {
        const amt = parseFloat(amountInput.value) || 0;
        const comm = Math.round(amt * COMMISSION_RATE / 100);
        commPreview.textContent = comm.toLocaleString('ru') + ' ₽';
    });

    document.getElementById('dealCancel')?.addEventListener('click', () => {
        modal.classList.remove('show');
    });

    document.getElementById('dealConfirm')?.addEventListener('click', async () => {
        const amt = parseFloat(amountInput.value);
        if (!amt || amt <= 0) { alert('Введите сумму сделки'); return; }
        try {
            const r = await fetch(`/api/leads/${dealLeadId}/deal`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount: amt })
            });
            const data = await r.json();
            if (data.success) {
                modal.classList.remove('show');
                checkCooldown();
                loadMyLeads();
                loadMyDeals();
                refreshStats();
                alert(`✅ Сделка оформлена!\nВаша комиссия: ${Number(data.commission).toLocaleString('ru')} ₽`);
            }
        } catch(e) { alert('Ошибка'); }
    });

    modal?.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('show');
    });

    // ── Refresh stats ────────────────────────────────────────────
    async function refreshStats() {
        try {
            const r = await fetch('/api/stats/my');
            const s = await r.json();
            setText('statMyLeads', s.total_leads);
            setText('statActiveLeads', s.active_leads);
            setText('statDeals', s.deals_count);
            setText('statAmount', Math.round(s.total_amount).toLocaleString('ru') + ' ₽');
            setText('statCommission', Math.round(s.total_commission).toLocaleString('ru') + ' ₽');
        } catch(e) {}
    }

    // ── Helpers ──────────────────────────────────────────────────
    function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
    function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }
    function formatDate(d) { if (!d) return '-'; try { return new Date(d).toLocaleDateString('ru'); } catch(e) { return d; } }

    function phoneHtml(phone) {
        if (!phone) return '<span style="color:var(--text-muted);font-size:.85rem">—</span>';
        return `<div class="phone-badge" onclick="copyPhone(this,'${esc(phone)}')">${esc(phone)}</div>`;
    }

    window.copyPhone = function(el, phone) {
        navigator.clipboard.writeText(phone);
        el.classList.add('copied');
        const orig = el.textContent;
        el.textContent = 'Скопировано!';
        setTimeout(() => { el.classList.remove('copied'); el.textContent = orig; }, 1500);
    };

    function linksHtml(l) {
        let h = '';
        const ym = l.yandex_url || (l.website_url && l.website_url.includes('yandex.ru') ? l.website_url : '');
        if (ym) h += `<a href="${ym}" target="_blank" class="maps-link">📍 Карты</a>`;
        if (l.has_website === '1' && l.website_url && !l.website_url.includes('yandex.ru')) {
            let u = l.website_url;
            if (!u.startsWith('http')) u = 'https://' + u;
            h += `<a href="${u}" target="_blank" class="website-link">🌐 Сайт</a>`;
        }
        return h || '<span class="no-website">Нет</span>';
    }

    function dealLinksHtml(d) {
        let h = '';
        const ym = d.lead_yandex_url || (d.lead_website_url && d.lead_website_url.includes('yandex.ru') ? d.lead_website_url : '');
        if (ym) h += `<a href="${ym}" target="_blank" class="maps-link">📍 Карты</a>`;
        return h || '<span style="color:var(--text-muted)">—</span>';
    }

    function statusLabel(s) {
        const m = { free:'Свободен', taken:'Взят', in_progress:'В работе', callback:'Перезвонить', deal:'Сделка', refused:'Отказ' };
        return m[s] || s;
    }

    // ── Search ───────────────────────────────────────────────────
    document.getElementById('freeSearch')?.addEventListener('input', renderFreeTable);

    // ── Init ─────────────────────────────────────────────────────
    checkCooldown();
    loadMyLeads();   // load first to set hasActiveLead before rendering free table
    loadFreeLeads();
    loadMyDeals();
});
