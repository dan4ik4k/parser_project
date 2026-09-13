import os
import csv
from flask import Flask, render_template, jsonify, request
from config import CSV_FILE_PATH

app = Flask(__name__)

# Поля, которые мы ожидаем в CSV
FIELDNAMES = [
    'id', 'source', 'name', 'phone', 'has_website', 
    'website_url', 'yandex_url', 'rating', 'reviews_count', 'address', 'target_result'
]

def read_csv():
    if not os.path.exists(CSV_FILE_PATH):
        return []
    data = []
    with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            data.append(row)
    # Отдаем в обратном порядке (последние добавленные сверху)
    return list(reversed(data))

def write_csv(data):
    with open(CSV_FILE_PATH, mode='w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';')
        writer.writeheader()
        writer.writerows(data)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/leads', methods=['GET'])
def get_leads():
    return jsonify(read_csv())

@app.route('/api/leads/<lead_id>', methods=['PATCH'])
def update_lead(lead_id):
    update_data = request.json
    all_leads = []
    found = False
    
    if not os.path.exists(CSV_FILE_PATH):
        return jsonify({'success': False, 'error': 'File not found'}), 404
        
    with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        all_leads = list(reader)
        
    for lead in all_leads:
        if lead.get('id') == lead_id:
            lead['target_result'] = update_data.get('target_result', lead.get('target_result'))
            found = True
            break
            
    if found:
        write_csv(all_leads)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Lead not found'}), 404

@app.route('/api/leads/<lead_id>', methods=['DELETE'])
def delete_lead(lead_id):
    if not os.path.exists(CSV_FILE_PATH):
        return jsonify({'success': False, 'error': 'File not found'}), 404
        
    all_leads = []
    found = False
    
    with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            if row.get('id') == lead_id:
                found = True
            else:
                all_leads.append(row)
                
    if found:
        write_csv(all_leads)
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Lead not found'}), 404

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Web-интерфейс запущен!")
    print("Откройте в браузере: http://127.0.0.1:5000")
    print("="*50 + "\n")
    # debug=False чтобы не было лишнего лога, use_reloader=False для запуска в потоке, если надо
    app.run(debug=True, host='127.0.0.1', port=5000)
