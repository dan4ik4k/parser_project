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

    let allUsers = [];
    let allLeads = [];
    let approvedManagers = [];

    // ═══════════════════════════════════════════════════════════
    //  USERS TAB
    // ═══════════════════════════════════════════════════════════

    async function loadUsers() {
        try {
            const r = await fetch('/api/admin/users');
            allUsers = await r.json();
            approvedManagers = allUsers.filter(u => u.role === 'manager' && u.status === 'approved');
            renderUsers();
        } catch (e) { console.error(e); }
    }

    function renderUsers() {
        const tbody = document.getElementById('usersTableBody');
        const managers = allUsers.filter(u => u.role !== 'admin');
        if (!managers.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="loading">Нет зарегистрированных сотрудников</td></tr>';
            return;
        }
        tbody.innerHTML = managers.map(u => `
            <tr>
                <td class="name-cell">${esc(u.display_name)}</td>
                <td style="color:var(--text-muted)">${esc(u.username)}</td>
                <td style="color:var(--text-muted);font-size:.85rem">${esc(u.contact) || '—'}</td>
                <td><span class="status-badge status-${u.status}">${statusUserLabel(u.status)}</span></td>
                <td>
                    <div style="display:flex;align-items:center;gap:.35rem">
                        <input type="number" class="commission-input" value="${u.commission_rate}"
                               onchange="updateCommission(${u.id}, this.value)" min="0" max="100" step="0.5">
                        <span style="color:var(--text-muted);font-size:.8rem">%</span>
                    </div>
                </td>
                <td style="color:var(--purple);font-size:.85rem">${esc(u.referred_by) || '—'}</td>
                <td class="action-cell">
                    ${u.status === 'pending' ? `
                        <button class="btn btn-success btn-inline" onclick="approveUser(${u.id})">✅ Выдать доступ</button>
                        <button class="btn btn-danger btn-inline" onclick="blockUser(${u.id})">🚫 Отклонить</button>
                    ` : u.status === 'approved' ? `
                        <button class="btn btn-danger btn-inline" onclick="blockUser(${u.id})">🚫 Заблокировать</button>
                    ` : `
                        <button class="btn btn-success btn-inline" onclick="approveUser(${u.id})">✅ Разблокировать</button>
                    `}
                </td>
            </tr>
        `).join('');
    }

    window.approveUser = async function(id) {
        await fetch(`/api/admin/users/${id}/approve`, { method: 'POST' });
        loadUsers();
    };

    window.blockUser = async function(id) {
        if (!confirm('Заблокировать этого сотрудника?')) return;
        await fetch(`/api/admin/users/${id}/block`, { method: 'POST' });
        loadUsers();
    };

    window.updateCommission = async function(id, rate) {
        await fetch(`/api/admin/users/${id}/commission`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rate: parseFloat(rate) })
        });
    };

    // ═══════════════════════════════════════════════════════════
    //  LEADS TAB
    // ═══════════════════════════════════════════════════════════

    async function loadAllLeads() {
        try {
            const r = await fetch('/api/leads/all');
            allLeads = await r.json();
            renderAdminLeads();
        } catch(e) { console.error(e); }
    }

    function renderAdminLeads() {
        const tbody = document.getElementById('adminLeadsTableBody');
        const search = (document.getElementById('adminLeadSearch')?.value || '').toLowerCase();
        const filter = document.getElementById('adminLeadFilter')?.value || 'all';

        let filtered = allLeads.filter(l => {
            const ms = (l.name||'').toLowerCase().includes(search) || (l.phone||'').includes(search);
            const mf = filter === 'all' ? true : l.status === filter;
            return ms && mf;
        });

        if (!filtered.length) {
            tbody.innerHTML = '<tr><td colspan="5" class="loading">Ничего не найдено</td></tr>';
            return;
        }

        tbody.innerHTML = filtered.map(l => `
            <tr>
                <td class="name-cell">
                    ${esc(l.name) || 'Без названия'}
                    <div class="address">${esc(l.address) || ''}</div>
                </td>
                <td>${phoneHtml(l.phone)}</td>
                <td><span class="status-badge status-${l.status}">${statusLeadLabel(l.status)}</span></td>
                <td style="color:var(--text-muted);font-size:.85rem">
                    ${l.manager_name ? esc(l.manager_name) : '—'}
                </td>
                <td class="action-cell">
                    ${l.status !== 'free' ? `
                        <button class="btn btn-warning btn-inline" onclick="freeLead('${l.id}')">🔓 Освободить</button>
                    ` : ''}
                    ${approvedManagers.length ? `
                        <select class="status-select" onchange="reassignLead('${l.id}', this.value)" style="font-size:.78rem;padding:.25rem">
                            <option value="">Назначить →</option>
                            ${approvedManagers.map(m => `<option value="${m.id}">${esc(m.display_name)}</option>`).join('')}
                        </select>
                    ` : ''}
                </td>
            </tr>
        `).join('');
    }

    window.freeLead = async function(id) {
        await fetch(`/api/admin/leads/${id}/free`, { method: 'POST' });
        loadAllLeads();
    };

    window.reassignLead = async function(id, managerId) {
        if (!managerId) return;
        await fetch(`/api/admin/leads/${id}/reassign`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ manager_id: parseInt(managerId) })
        });
        loadAllLeads();
    };

    document.getElementById('adminLeadSearch')?.addEventListener('input', renderAdminLeads);
    document.getElementById('adminLeadFilter')?.addEventListener('change', renderAdminLeads);

    // ═══════════════════════════════════════════════════════════
    //  DEALS TAB
    // ═══════════════════════════════════════════════════════════

    async function loadDeals() {
        try {
            const r = await fetch('/api/admin/deals');
            const deals = await r.json();
            renderDeals(deals);
        } catch(e) { console.error(e); }
    }

    function renderDeals(deals) {
        const tbody = document.getElementById('dealsTableBody');
        if (!deals.length) {
            tbody.innerHTML = '<tr><td colspan="6" class="loading">Пока нет сделок</td></tr>';
            return;
        }
        tbody.innerHTML = deals.map(d => `
            <tr>
                <td class="name-cell">${esc(d.lead_name)}<div class="address">${esc(d.lead_phone)}</div></td>
                <td style="color:var(--accent-hover)">${esc(d.manager_name)}</td>
                <td><strong>${Number(d.amount).toLocaleString('ru')} ₽</strong></td>
                <td>${d.commission_rate}%</td>
                <td style="color:var(--success);font-weight:600">${Number(d.commission_amount).toLocaleString('ru')} ₽</td>
                <td style="color:var(--text-muted);font-size:.85rem">${formatDate(d.created_at)}</td>
            </tr>
        `).join('');
    }

    // ═══════════════════════════════════════════════════════════
    //  HELPERS
    // ═══════════════════════════════════════════════════════════

    function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
    function formatDate(d) { if (!d) return '-'; try { return new Date(d).toLocaleDateString('ru'); } catch(e) { return d; } }

    function phoneHtml(phone) {
        if (!phone) return '<span style="color:var(--text-muted)">—</span>';
        return `<div class="phone-badge" onclick="copyPhone(this,'${esc(phone)}')">${esc(phone)}</div>`;
    }

    window.copyPhone = function(el, phone) {
        navigator.clipboard.writeText(phone);
        el.classList.add('copied');
        const orig = el.textContent;
        el.textContent = 'Скопировано!';
        setTimeout(() => { el.classList.remove('copied'); el.textContent = orig; }, 1500);
    };

    function statusUserLabel(s) {
        return { pending: 'Ожидает', approved: 'Активен', blocked: 'Заблокирован' }[s] || s;
    }

    function statusLeadLabel(s) {
        return { free:'Свободен', taken:'Взят', in_progress:'В работе', callback:'Перезвонить', deal:'Сделка', refused:'Отказ' }[s] || s;
    }

    // ── Init ─────────────────────────────────────────────────────
    loadUsers();
    loadAllLeads();
    loadDeals();
});
