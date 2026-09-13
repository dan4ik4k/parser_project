document.addEventListener('DOMContentLoaded', () => {
    const tableBody = document.getElementById('tableBody');
    const searchInput = document.getElementById('searchInput');
    const noWebsiteFilter = document.getElementById('noWebsiteFilter');
    const totalCount = document.getElementById('totalCount');

    let leadsData = [];

    // Загрузка данных
    // Загрузка данных
    async function loadData() {
        tableBody.innerHTML = '<tr><td colspan="7" class="loading">Загрузка данных...</td></tr>';
        try {
            const response = await fetch('/api/leads');
            leadsData = await response.json();
            renderTable();
        } catch (error) {
            console.error('Ошибка загрузки:', error);
            tableBody.innerHTML = '<tr><td colspan="7" class="loading" style="color:var(--danger)">Ошибка загрузки данных. Проверьте, запущен ли сервер и существует ли data.csv.</td></tr>';
        }
    }

    // Отрисовка таблицы
    function renderTable() {
        const query = searchInput.value.toLowerCase();
        const noWebOnly = noWebsiteFilter.checked;

        const filtered = leadsData.filter(lead => {
            const matchesSearch = (lead.name || '').toLowerCase().includes(query) || 
                                  (lead.phone || '').includes(query);
            const matchesWeb = noWebOnly ? lead.has_website !== '1' : true;
            return matchesSearch && matchesWeb;
        });

        totalCount.textContent = filtered.length;
        tableBody.innerHTML = '';

        if (filtered.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="loading">Ничего не найдено</td></tr>';
            return;
        }

        filtered.forEach(lead => {
            const tr = document.createElement('tr');
            
            // Название и адрес
            const nameTd = document.createElement('td');
            nameTd.className = 'name-cell';
            nameTd.innerHTML = `
                ${lead.name || 'Без названия'}
                <div class="address">${lead.address || ''}</div>
            `;
            
            // Рейтинг
            const ratingTd = document.createElement('td');
            ratingTd.innerHTML = `
                <div class="rating">
                    <span class="rating-val">★ ${lead.rating || '-'}</span>
                    <span class="rating-count">(${lead.reviews_count || 0})</span>
                </div>
            `;

            // Телефон
            const phoneTd = document.createElement('td');
            if (lead.phone) {
                const badge = document.createElement('div');
                badge.className = 'phone-badge';
                badge.textContent = lead.phone;
                badge.title = "Кликните, чтобы скопировать";
                badge.onclick = () => {
                    navigator.clipboard.writeText(lead.phone);
                    badge.classList.add('copied');
                    badge.textContent = 'Скопировано!';
                    setTimeout(() => {
                        badge.classList.remove('copied');
                        badge.textContent = lead.phone;
                    }, 1500);
                };
                phoneTd.appendChild(badge);
            } else {
                phoneTd.innerHTML = '<span style="color:var(--text-muted); font-size:0.85rem">Нет телефона</span>';
            }

            // Сайт компании
            const siteTd = document.createElement('td');
            if (lead.has_website === '1' && lead.website_url && !lead.website_url.includes('yandex.ru')) {
                let url = lead.website_url;
                if (!url.startsWith('http')) url = 'https://' + url;
                siteTd.innerHTML = `<a href="${url}" target="_blank" class="website-link">Перейти на сайт ↗</a>`;
            } else {
                siteTd.innerHTML = `<span class="no-website">Сайта нет</span>`;
            }

            // Яндекс Карты
            const yandexTd = document.createElement('td');
            const ymapsUrl = lead.yandex_url || (lead.website_url && lead.website_url.includes('yandex.ru') ? lead.website_url : '');
            if (ymapsUrl) {
                yandexTd.innerHTML = `<a href="${ymapsUrl}" target="_blank" class="maps-link">📍 Яндекс Карты ↗</a>`;
            } else {
                yandexTd.innerHTML = `<span style="color:var(--text-muted); font-size:0.85rem">-</span>`;
            }

            // Статус ML
            const statusTd = document.createElement('td');
            const select = document.createElement('select');
            select.className = 'status-select';
            select.dataset.val = lead.target_result || '';
            
            const options = [
                { val: '', text: 'Не обработан' },
                { val: '0', text: 'Отказ (0)' },
                { val: '1', text: 'Думают (1)' },
                { val: '2', text: 'Продажа/Лид (2)' }
            ];
            
            options.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt.val;
                option.textContent = opt.text;
                if (lead.target_result === opt.val) option.selected = true;
                select.appendChild(option);
            });

            select.addEventListener('change', async (e) => {
                const newVal = e.target.value;
                e.target.dataset.val = newVal;
                lead.target_result = newVal;
                
                try {
                    const response = await fetch(`/api/leads/${lead.id}`, {
                        method: 'PATCH',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ target_result: newVal })
                    });
                    if (!response.ok) throw new Error("Server error");
                } catch (err) {
                    console.error('Ошибка сохранения статуса', err);
                    alert('Не удалось сохранить статус! Убедитесь, что сервер работает.');
                }
            });
            
            statusTd.appendChild(select);

            // Кнопка удаления
            const actionTd = document.createElement('td');
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'delete-btn';
            deleteBtn.innerHTML = '🗑';
            deleteBtn.title = 'Удалить из базы';
            deleteBtn.onclick = async () => {
                if (confirm(`Удалить "${lead.name || 'эту запись'}" из базы?`)) {
                    try {
                        const response = await fetch(`/api/leads/${lead.id}`, { method: 'DELETE' });
                        if (!response.ok) throw new Error("Server error");
                        leadsData = leadsData.filter(l => l.id !== lead.id);
                        renderTable();
                    } catch (err) {
                        console.error('Ошибка удаления:', err);
                        alert('Не удалось удалить запись!');
                    }
                }
            };
            actionTd.appendChild(deleteBtn);

            tr.append(nameTd, ratingTd, phoneTd, siteTd, yandexTd, statusTd, actionTd);
            tableBody.appendChild(tr);
        });
    }

    // Слушатели событий
    searchInput.addEventListener('input', renderTable);
    noWebsiteFilter.addEventListener('change', renderTable);

    // Первичная загрузка
    loadData();
});
