import os
import secrets
from functools import wraps

from flask import (Flask, render_template, jsonify, request,
                   redirect, url_for)
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from werkzeug.security import check_password_hash

from models import (
    init_db, create_admin, migrate_csv_to_db,
    get_user_by_id, get_user_by_username, create_user, get_all_users,
    update_user_status, update_user_commission,
    get_free_leads, get_leads_by_manager, get_all_leads,
    claim_lead, release_lead, update_lead_status, reassign_lead,
    create_deal, get_deals_by_manager, get_all_deals,
    get_manager_stats, get_admin_stats, get_user_cooldown,
    import_leads_csv
)

# ─── App config ──────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

ADMIN_USERNAME = '9i7777'
ADMIN_PASSWORD = 'GiD4@*fdv7qlZNZoMlYR'

# ─── Flask-Login ─────────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = ''


class User(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.username = row['username']
        self.display_name = row['display_name']
        self.role = row['role']
        self.status = row['status']
        self.commission_rate = row['commission_rate']
        self.contact = row['contact']

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_approved(self):
        return self.status == 'approved'


@login_manager.user_loader
def load_user(user_id):
    row = get_user_by_id(int(user_id))
    return User(row) if row else None


# ─── Decorators ──────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            return jsonify({'error': 'Доступ запрещён'}), 403
        return f(*args, **kwargs)
    return decorated


def approved_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_approved and not current_user.is_admin:
            return redirect(url_for('pending'))
        return f(*args, **kwargs)
    return decorated


# ─── Bootstrap DB ────────────────────────────────────────────────
init_db()
create_admin(ADMIN_USERNAME, ADMIN_PASSWORD)
migrate_csv_to_db()


# ═════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ═════════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for('admin_panel'))
        return redirect(url_for('index'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        row = get_user_by_username(username)
        if row and check_password_hash(row['password_hash'], password):
            user = User(row)
            if user.status == 'blocked':
                error = 'Ваш аккаунт заблокирован. Обратитесь к администратору.'
            else:
                login_user(user, remember=True)
                if user.is_admin:
                    return redirect(url_for('admin_panel'))
                elif user.is_approved:
                    return redirect(url_for('index'))
                else:
                    return redirect(url_for('pending'))
        else:
            error = 'Неверный логин или пароль'

    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    ref = request.args.get('ref', '')
    error = None

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        display_name = request.form.get('display_name', '').strip()
        contact = request.form.get('contact', '').strip()
        referred_by = request.form.get('referred_by', '').strip() or None

        if not username or not password or not display_name:
            error = 'Заполните все обязательные поля'
        elif len(password) < 6:
            error = 'Пароль должен быть не менее 6 символов'
        else:
            ok, msg = create_user(username, password, display_name, contact, referred_by)
            if ok:
                row = get_user_by_username(username)
                login_user(User(row), remember=True)
                return redirect(url_for('pending'))
            else:
                error = msg

    return render_template('register.html', error=error, ref=ref)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/pending')
@login_required
def pending():
    if current_user.is_admin:
        return redirect(url_for('admin_panel'))
    if current_user.is_approved:
        return redirect(url_for('index'))
    return render_template('pending.html', user=current_user)


# ═════════════════════════════════════════════════════════════════
#  PAGES
# ═════════════════════════════════════════════════════════════════

@app.route('/')
@approved_required
def index():
    if current_user.is_admin:
        return redirect(url_for('admin_panel'))
    stats = get_manager_stats(current_user.id)
    return render_template('index.html', user=current_user, stats=stats)


@app.route('/admin')
@admin_required
def admin_panel():
    stats = get_admin_stats()
    return render_template('admin.html', user=current_user, stats=stats)


# ═════════════════════════════════════════════════════════════════
#  API – LEADS (manager)
# ═════════════════════════════════════════════════════════════════

@app.route('/api/cooldown')
@login_required
def api_cooldown():
    return jsonify({'cooldown': get_user_cooldown(current_user.id, 60)})


@app.route('/api/leads/free')
@login_required
def api_free_leads():
    if not current_user.is_approved and not current_user.is_admin:
        return jsonify([])
    return jsonify([dict(r) for r in get_free_leads()])


@app.route('/api/leads/my')
@login_required
def api_my_leads():
    return jsonify([dict(r) for r in get_leads_by_manager(current_user.id)])


@app.route('/api/leads/all')
@admin_required
def api_all_leads():
    return jsonify([dict(r) for r in get_all_leads()])


@app.route('/api/leads/<lead_id>/claim', methods=['POST'])
@login_required
def api_claim_lead(lead_id):
    if not current_user.is_approved:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    ok, msg = claim_lead(lead_id, current_user.id)
    return (jsonify({'success': True}) if ok
            else (jsonify({'success': False, 'error': msg}), 409))


@app.route('/api/leads/<lead_id>/release', methods=['POST'])
@login_required
def api_release_lead(lead_id):
    release_lead(lead_id, current_user.id, current_user.is_admin)
    return jsonify({'success': True})


@app.route('/api/leads/<lead_id>/status', methods=['PATCH'])
@login_required
def api_update_lead_status(lead_id):
    data = request.json or {}
    new_status = data.get('status')
    if new_status not in ('taken', 'in_progress', 'callback', 'refused'):
        return jsonify({'error': 'Недопустимый статус'}), 400
    update_lead_status(lead_id, new_status, current_user.id, current_user.is_admin)
    return jsonify({'success': True})


@app.route('/api/leads/<lead_id>/deal', methods=['POST'])
@login_required
def api_create_deal(lead_id):
    data = request.json or {}
    try:
        amount = float(data.get('amount', 0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Некорректная сумма'}), 400
    if amount <= 0:
        return jsonify({'error': 'Сумма должна быть больше 0'}), 400
    commission = create_deal(lead_id, current_user.id, amount)
    return jsonify({'success': True, 'commission': commission})


# ═════════════════════════════════════════════════════════════════
#  API – ADMIN
# ═════════════════════════════════════════════════════════════════

@app.route('/api/admin/users')
@admin_required
def api_admin_users():
    users = get_all_users()
    result = []
    for u in users:
        d = dict(u)
        d.pop('password_hash', None)
        result.append(d)
    return jsonify(result)


@app.route('/api/admin/users/<int:user_id>/approve', methods=['POST'])
@admin_required
def api_approve_user(user_id):
    update_user_status(user_id, 'approved')
    return jsonify({'success': True})


@app.route('/api/admin/users/<int:user_id>/block', methods=['POST'])
@admin_required
def api_block_user(user_id):
    update_user_status(user_id, 'blocked')
    return jsonify({'success': True})


@app.route('/api/admin/users/<int:user_id>/commission', methods=['PATCH'])
@admin_required
def api_update_commission(user_id):
    data = request.json or {}
    try:
        rate = float(data.get('rate', 15.0))
    except (ValueError, TypeError):
        return jsonify({'error': 'Некорректный процент'}), 400
    update_user_commission(user_id, rate)
    return jsonify({'success': True})


@app.route('/api/admin/leads/<lead_id>/reassign', methods=['POST'])
@admin_required
def api_reassign_lead(lead_id):
    data = request.json or {}
    new_manager_id = data.get('manager_id')
    if not new_manager_id:
        return jsonify({'error': 'manager_id required'}), 400
    reassign_lead(lead_id, int(new_manager_id))
    return jsonify({'success': True})


@app.route('/api/admin/leads/<lead_id>/free', methods=['POST'])
@admin_required
def api_free_lead(lead_id):
    release_lead(lead_id, is_admin=True)
    return jsonify({'success': True})


@app.route('/api/admin/leads/import', methods=['POST'])
@admin_required
def api_import_leads():
    content = ""
    if 'file' in request.files:
        file = request.files['file']
        if file.filename:
            content = file.read().decode('utf-8-sig', errors='ignore')
    elif request.is_json:
        data = request.json or {}
        content = data.get('csv_text', '')
    else:
        content = request.form.get('csv_text', '')

    if not content.strip():
        return jsonify({'error': 'Файл или текст CSV пуст'}), 400

    added, skipped, total = import_leads_csv(content)
    return jsonify({
        'success': True,
        'added': added,
        'skipped': skipped,
        'total': total
    })


@app.route('/api/admin/deals')
@admin_required
def api_admin_deals():
    return jsonify([dict(d) for d in get_all_deals()])


@app.route('/api/deals/my')
@login_required
def api_my_deals():
    return jsonify([dict(d) for d in get_deals_by_manager(current_user.id)])


@app.route('/api/stats/my')
@login_required
def api_my_stats():
    return jsonify(get_manager_stats(current_user.id))


# ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("CRM запущена!")
    print("http://127.0.0.1:5000")
    print("=" * 50 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5000)
