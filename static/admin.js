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
                    <button class="btn btn-secondary btn-inline" onclick="openEditUserModal(${u.id})">✏️ Профиль</button>
                    ${u.status === 'pending' ? `
                        <button class="btn btn-success btn-inline" onclick="approveUser(${u.id})">✅ Доступ</button>
                        <button class="btn btn-danger btn-inline" onclick="blockUser(${u.id})">🚫 Отклонить</button>
                    ` : u.status === 'approved' ? `
                        <button class="btn btn-danger btn-inline" onclick="blockUser(${u.id})">🚫 Блок</button>
                    ` : `
                        <button class="btn btn-success btn-inline" onclick="approveUser(${u.id})">✅ Разблок</button>
                    `}
                </td>
            </tr>
        `).join('');
    }

    window.openEditUserModal = function(id) {
        const u = allUsers.find(x => x.id === id);
        if (!u) return;
        document.getElementById('editUserId').value = u.id;
        document.getElementById('editUserTitle').textContent = `Редактирование профиля: ${u.display_name}`;
        document.getElementById('editUserDisplayName').value = u.display_name || '';
        document.getElementById('editUserUsername').value = u.username || '';
        document.getElementById('editUserContact').value = u.contact || '';
        document.getElementById('editUserCommissionRate').value = u.commission_rate || 15;
        document.getElementById('editUserPassword').value = '';
        document.getElementById('editUserModal').classList.add('show');
    };

    document.getElementById('editUserCancelBtn')?.addEventListener('click', () => {
        document.getElementById('editUserModal').classList.remove('show');
    });

    document.getElementById('editUserSaveBtn')?.addEventListener('click', async () => {
        const id = document.getElementById('editUserId').value;
        const display_name = document.getElementById('editUserDisplayName').value.trim();
        const username = document.getElementById('editUserUsername').value.trim();
        const contact = document.getElementById('editUserContact').value.trim();
        const commission_rate = parseFloat(document.getElementById('editUserCommissionRate').value) || 15;
        const password = document.getElementById('editUserPassword').value.trim();

        if (!display_name || !username) {
            alert('Имя и логин обязательны');
            return;
        }

        try {
            const r = await fetch(`/api/admin/users/${id}/edit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ display_name, username, contact, commission_rate, password })
            });
            const data = await r.json();
            if (data.success) {
                document.getElementById('editUserModal').classList.remove('show');
                loadUsers();
                alert('Профиль сотрудника успешно обновлен!');
            } else {
                alert(data.error || 'Ошибка при сохранении профиля');
            }
        } catch(e) {
            alert('Ошибка сети');
        }
    });

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
            tbody.innerHTML = '<tr><td colspan="9" class="loading">Пока нет сделок</td></tr>';
            return;
        }
        tbody.innerHTML = deals.map(d => {
            const statusBadge = d.status === 'approved' 
                ? '<span class="status-badge status-approved" style="background:#1e3a29;color:#4ade80">✅ Одобрена</span>'
                : d.status === 'rejected'
                ? '<span class="status-badge status-rejected" style="background:#3b1819;color:#f87171">❌ Отклонена</span>'
                : '<span class="status-badge status-pending" style="background:#3a2e1e;color:#facc15">⏳ На проверке</span>';

            const actions = (d.status === 'pending' || !d.status) ? `
                <button class="btn btn-success btn-inline" style="padding:.25rem .5rem;font-size:.78rem" onclick="approveDeal(${d.id})">✅ Одобрить</button>
                <button class="btn btn-danger btn-inline" style="padding:.25rem .5rem;font-size:.78rem" onclick="rejectDeal(${d.id})">❌ Отклонить</button>
            ` : '—';

            return `
                <tr>
                    <td class="name-cell">${esc(d.lead_name)}<div class="address">${esc(d.lead_phone)}</div></td>
                    <td class="link-group">${dealLinksHtml(d)}</td>
                    <td style="color:var(--accent-hover)">${esc(d.manager_name)}</td>
                    <td><strong>${Number(d.amount).toLocaleString('ru')} ₽</strong></td>
                    <td>${d.commission_rate}%</td>
                    <td style="color:var(--success);font-weight:600">${Number(d.commission_amount).toLocaleString('ru')} ₽</td>
                    <td style="color:var(--text-muted);font-size:.85rem">${formatDate(d.created_at)}</td>
                    <td>${statusBadge}</td>
                    <td class="action-cell">${actions}</td>
                </tr>
            `;
        }).join('');
    }

    window.approveDeal = async function(id) {
        if (!confirm('Одобрить эту сделку?')) return;
        await fetch(`/api/admin/deals/${id}/approve`, { method: 'POST' });
        loadDeals();
        loadStats();
    };

    window.rejectDeal = async function(id) {
        if (!confirm('Отклонить сделку? Клиент вернется менеджеру.')) return;
        await fetch(`/api/admin/deals/${id}/reject`, { method: 'POST' });
        loadDeals();
        loadStats();
    };

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

    function dealLinksHtml(d) {
        let h = '';
        const ym = d.lead_yandex_url || (d.lead_website_url && d.lead_website_url.includes('yandex.ru') ? d.lead_website_url : '');
        if (ym) h += `<a href="${ym}" target="_blank" class="maps-link">📍 Карты</a>`;
        return h || '<span style="color:var(--text-muted)">—</span>';
    }

    // ═══════════════════════════════════════════════════════════
    //  IMPORT MODAL
    // ═══════════════════════════════════════════════════════════

    const importModal = document.getElementById('importModal');
    const openImportBtn = document.getElementById('openImportModalBtn');
    const cancelImportBtn = document.getElementById('importCancelBtn');
    const submitImportBtn = document.getElementById('importSubmitBtn');
    const fileInput = document.getElementById('importFileInput');
    const csvTextArea = document.getElementById('importCsvText');
    const resultBox = document.getElementById('importResultBox');

    openImportBtn?.addEventListener('click', () => {
        if (fileInput) fileInput.value = '';
        if (csvTextArea) csvTextArea.value = '';
        if (resultBox) { resultBox.style.display = 'none'; resultBox.innerHTML = ''; }
        importModal?.classList.add('show');
    });

    cancelImportBtn?.addEventListener('click', () => {
        importModal?.classList.remove('show');
    });

    importModal?.addEventListener('click', (e) => {
        if (e.target === importModal) importModal.classList.remove('show');
    });

    submitImportBtn?.addEventListener('click', async () => {
        const file = fileInput?.files[0];
        const text = csvTextArea?.value || '';

        if (!file && !text.trim()) {
            alert('Выберите CSV файл или вставьте текст CSV');
            return;
        }

        submitImportBtn.disabled = true;
        submitImportBtn.textContent = '⏳ Загрузка...';

        try {
            let res;
            if (file) {
                const formData = new FormData();
                formData.append('file', file);
                const r = await fetch('/api/admin/leads/import', {
                    method: 'POST',
                    body: formData
                });
                res = await r.json();
            } else {
                const r = await fetch('/api/admin/leads/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ csv_text: text })
                });
                res = await r.json();
            }

            if (res.success) {
                if (resultBox) {
                    resultBox.style.display = 'block';
                    resultBox.style.background = 'rgba(16,185,129,.12)';
                    resultBox.style.border = '1px solid rgba(16,185,129,.3)';
                    resultBox.style.color = 'var(--text-main)';
                    resultBox.innerHTML = `
                        <div style="font-weight:600;color:var(--success);margin-bottom:.3rem">✅ Импорт успешно завершен!</div>
                        <div>📊 Всего записей в файле: <strong>${res.total}</strong></div>
                        <div style="color:var(--success)">➕ Добавлено новых клиентов: <strong>${res.added}</strong></div>
                        <div style="color:var(--warning)">⏭️ Пропущено (дубликаты/уже есть): <strong>${res.skipped}</strong></div>
                    `;
                }
                loadAllLeads();
            } else {
                if (resultBox) {
                    resultBox.style.display = 'block';
                    resultBox.style.background = 'rgba(239,68,68,.12)';
                    resultBox.style.border = '1px solid rgba(239,68,68,.3)';
                    resultBox.style.color = 'var(--danger)';
                    resultBox.textContent = res.error || 'Ошибка загрузки';
                }
            }
        } catch(e) {
            alert('Ошибка при импорте');
        } finally {
            submitImportBtn.disabled = false;
            submitImportBtn.textContent = '🚀 Загрузить и отфильтровать';
        }
    });

    // ── Init ─────────────────────────────────────────────────────
    loadUsers();
    loadAllLeads();
    loadDeals();
});
