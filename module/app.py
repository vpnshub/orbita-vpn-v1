from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
import os
from datetime import timedelta
import requests
import traceback

from models import db, User, ApiSettings
from config import Config
from handlers.crypto import crypto
from handlers.bot_messages import bot_messages
from handlers.bot_settings import bot_settings
from handlers.yookassa import yookassa
from handlers.yoopayments import yoopayments
from handlers.dashboard import dashboard
from handlers.cryptopayments import cryptopayments
from handlers.balance_transaction import balance_transaction
from handlers.pspayments import pspayments

app = Flask(__name__)
app.config.from_object(Config)

app.register_blueprint(crypto)
app.register_blueprint(bot_messages)
app.register_blueprint(yookassa)
app.register_blueprint(bot_settings)
app.register_blueprint(yoopayments)
app.register_blueprint(pspayments)
app.register_blueprint(dashboard)
app.register_blueprint(cryptopayments)
app.register_blueprint(balance_transaction)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def create_tables():
    with app.app_context():
        db.create_all()
        
        if User.query.count() == 0:
            default_user = User(username='admin')
            default_user.set_password('admin')
            db.session.add(default_user)
            db.session.commit()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/auth-change', methods=['GET', 'POST'])
@login_required
def auth_change():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('Текущий пароль введен неверно', 'danger')
            return render_template('auth-change.html')
        
        if new_password != confirm_password:
            flash('Новый пароль и подтверждение не совпадают', 'danger')
            return render_template('auth-change.html')
        
        if current_user.check_password(new_password):
            flash('Новый пароль должен отличаться от текущего', 'warning')
            return render_template('auth-change.html')
            
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Пароль успешно изменен', 'success')
        return redirect(url_for('dashboard.index'))
    
    return render_template('auth-change.html')

@app.route('/settings/api')
@login_required
def api_settings():
    api_settings = ApiSettings.query.all()
    return render_template('settings_api.html', api_settings=api_settings)

@app.route('/settings/api/save', methods=['POST'])
@login_required
def save_api_settings():
    if request.method == 'POST':
        try:
            data = request.json
            
            new_api = ApiSettings(
                api_name=data.get('api_name'),
                api_key=data.get('api_key'),
                api_url=data.get('api_url'),
                is_active=True
            )
            
            db.session.add(new_api)
            db.session.commit()
            
            return jsonify({"success": True, "message": "API настройки успешно сохранены"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

@app.route('/settings/api/update', methods=['POST'])
@login_required
def update_api_settings():
    if request.method == 'POST':
        try:
            data = request.json
            
            api_setting = ApiSettings.query.filter_by(id=data.get('id')).first()
            
            if not api_setting:
                return jsonify({"success": False, "message": "API настройка не найдена"})
            
            api_setting.api_name = data.get('api_name')
            api_setting.api_url = data.get('api_url')
            api_setting.api_key = data.get('api_key')
            api_setting.is_active = data.get('is_active', True)
            
            db.session.commit()
            
            return jsonify({"success": True, "message": "API настройки успешно обновлены"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

@app.route('/settings/api/delete', methods=['POST'])
@login_required
def delete_api_settings():
    if request.method == 'POST':
        try:
            data = request.json
            
            api_setting = ApiSettings.query.filter_by(id=data.get('id')).first()
            
            if not api_setting:
                return jsonify({"success": False, "message": "API настройка не найдена"})
            
            db.session.delete(api_setting)
            db.session.commit()
            
            return jsonify({"success": True, "message": "API настройки успешно удалены"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(hours=12)

@app.route('/tariffs')
@login_required
def tariffs():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return render_template('tariff.html', tariffs=[], 
                                  error_message="Нет активных API настроек. Пожалуйста, настройте API в разделе настроек.")
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/tariffs/?is_enable=true"
        
        print(f"Запрос к API: {api_url}")
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            tariffs_data = response.json()
            
            if not isinstance(tariffs_data, list):
                tariffs_data = [tariffs_data]
                
            return render_template('tariff.html', tariffs=tariffs_data)
        else:
            error_message = f"Ошибка API: {response.status_code} - {response.text}"
            print(f"Ошибка API запроса: {error_message}")
            return render_template('tariff.html', tariffs=[], error_message=error_message)
            
    except requests.RequestException as e:
        error_message = f"Ошибка соединения с API: {str(e)}"
        print(f"Ошибка запроса: {error_message}")
        return render_template('tariff.html', tariffs=[], error_message=error_message)
    except Exception as e:
        error_message = f"Произошла ошибка: {str(e)}"
        print(f"Общая ошибка: {error_message}")
        return render_template('tariff.html', tariffs=[], error_message=error_message)

@app.route('/tariffs/update', methods=['POST'])
@login_required
def update_tariff():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/tariffs/{data.get('id')}/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        update_data = {
            'name': data.get('name'),
            'description': data.get('description'),
            'price': float(data.get('price')),
            'left_day': int(data.get('left_day'))
        }
        
        response = requests.patch(api_url, json=update_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201, 204]:
            return jsonify({"success": True, "message": "Тариф успешно обновлен"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/tariffs/delete', methods=['POST'])
@login_required
def delete_tariff():
    try:
        data = request.json
        tariff_id = data.get('id')
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/tariffs/{tariff_id}/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.delete(api_url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Тариф успешно удален"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/servers', methods=['GET'])
@login_required
def get_servers():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/servers/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            servers_data = response.json()
            
            if not isinstance(servers_data, list):
                servers_data = [servers_data]
                
            return jsonify({"success": True, "servers": servers_data})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/tariffs/create', methods=['POST'])
@login_required
def create_tariff():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/tariffs/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        tariff_data = {
            'name': data.get('name'),
            'description': data.get('description'),
            'price': float(data.get('price')),
            'left_day': int(data.get('left_day')),
            'server_id': int(data.get('server_id'))
        }
        
        response = requests.post(api_url, json=tariff_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Тариф успешно создан"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/trial-tariffs')
@login_required
def trial_tariffs():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return render_template('trial-tariff.html', trials=[], 
                                  error_message="Нет активных API настроек. Пожалуйста, настройте API в разделе настроек.")
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/trial/"
        
        print(f"Запрос к API: {api_url}")
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            trials_data = response.json()
            
            if not isinstance(trials_data, list):
                trials_data = [trials_data]
                
            return render_template('trial-tariff.html', trials=trials_data)
        else:
            error_message = f"Ошибка API: {response.status_code} - {response.text}"
            print(f"Ошибка API запроса: {error_message}")
            return render_template('trial-tariff.html', trials=[], error_message=error_message)
            
    except requests.RequestException as e:
        error_message = f"Ошибка соединения с API: {str(e)}"
        print(f"Ошибка запроса: {error_message}")
        return render_template('trial-tariff.html', trials=[], error_message=error_message)
    except Exception as e:
        error_message = f"Произошла ошибка: {str(e)}"
        print(f"Общая ошибка: {error_message}")
        return render_template('trial-tariff.html', trials=[], error_message=error_message)

@app.route('/trial-tariffs/create', methods=['POST'])
@login_required
def create_trial():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        get_url = f"{base_url}/trial/"
        response = requests.get(get_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            trials_data = response.json()
            
            if not isinstance(trials_data, list):
                trials_data = [trials_data]
            
            for trial in trials_data:
                if trial.get('is_enable') == 1:
                    delete_url = f"{base_url}/trial/{trial.get('id')}"
                    delete_response = requests.delete(delete_url, headers=headers, timeout=10)
                    
                    if delete_response.status_code not in [200, 204]:
                        print(f"Ошибка при удалении пробного тарифа {trial.get('id')}: {delete_response.status_code} - {delete_response.text}")
        
        create_url = f"{base_url}/trial/"
        
        trial_data = {
            'name': data.get('name'),
            'left_day': int(data.get('left_day')),
            'server_id': int(data.get('server_id'))
        }
        
        create_response = requests.post(create_url, json=trial_data, headers=headers, timeout=10)
        
        if create_response.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Пробный тариф успешно создан. Предыдущие пробные тарифы деактивированы."})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {create_response.status_code} - {create_response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/trial-tariffs/update', methods=['POST'])
@login_required
def update_trial():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/trial/{data.get('id')}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        update_data = {
            'name': data.get('name'),
            'left_day': int(data.get('left_day')),
            'server_id': int(data.get('server_id'))
        }
        
        response = requests.patch(api_url, json=update_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201, 204]:
            return jsonify({"success": True, "message": "Пробный тариф успешно обновлен"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/trial-tariffs/delete', methods=['POST'])
@login_required
def delete_trial():
    try:
        data = request.json
        trial_id = data.get('id')
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/trial/{trial_id}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.delete(api_url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Пробный тариф успешно удален"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/promo-tariffs')
@login_required
def promo_tariffs():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return render_template('promo-tariff.html', promos=[], 
                                  error_message="Нет активных API настроек. Пожалуйста, настройте API в разделе настроек.")
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promo-tariffs/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            promos_data = response.json()
            
            if not isinstance(promos_data, list):
                promos_data = [promos_data]
                
            return render_template('promo-tariff.html', promos=promos_data)
        else:
            error_message = f"Ошибка API: {response.status_code} - {response.text}"
            print(f"Ошибка API запроса: {error_message}")
            return render_template('promo-tariff.html', promos=[], error_message=error_message)
            
    except requests.RequestException as e:
        error_message = f"Ошибка соединения с API: {str(e)}"
        print(f"Ошибка запроса: {error_message}")
        return render_template('promo-tariff.html', promos=[], error_message=error_message)
    except Exception as e:
        error_message = f"Произошла ошибка: {str(e)}"
        print(f"Общая ошибка: {error_message}")
        return render_template('promo-tariff.html', promos=[], error_message=error_message)

@app.route('/promo-tariffs/create', methods=['POST'])
@login_required
def create_promo():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promo-tariffs/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        promo_data = {
            'name': data.get('name'),
            'description': data.get('description'),
            'left_day': int(data.get('left_day')),
            'server_id': int(data.get('server_id'))
        }
        
        response = requests.post(api_url, json=promo_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Промо-тариф успешно создан"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/promo-tariffs/send', methods=['POST'])
@login_required
def send_promo():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promo-tariffs/send-with-server"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        send_data = {
            'promo_id': int(data.get('promo_id')),
            'telegram_id': int(data.get('telegram_id'))
        }
        
        response = requests.post(api_url, json=send_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            try:
                result = response.json()
                if result.get('success'):
                    return jsonify({"success": True, "message": "Промо-тариф успешно отправлен пользователю"})
                else:
                    return jsonify({"success": False, "message": result.get('message', 'Ошибка отправки промо-тарифа')})
            except:
                return jsonify({"success": True, "message": "Промо-тариф успешно отправлен пользователю"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/promo-tariffs/delete', methods=['POST'])
@login_required
def delete_promo():
    try:
        data = request.json
        promo_id = data.get('id')
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promo-tariffs/{promo_id}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.delete(api_url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Промо-тариф успешно удален"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/promocodes')
@login_required
def promocodes():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return render_template('promocode.html', promocodes=[], 
                                  error_message="Нет активных API настроек. Пожалуйста, настройте API в разделе настроек.")
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promocodes/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            promocodes_data = response.json()
            
            if not isinstance(promocodes_data, list):
                promocodes_data = [promocodes_data]
                
            return render_template('promocode.html', promocodes=promocodes_data)
        else:
            error_message = f"Ошибка API: {response.status_code} - {response.text}"
            print(f"Ошибка API запроса: {error_message}")
            return render_template('promocode.html', promocodes=[], error_message=error_message)
            
    except requests.RequestException as e:
        error_message = f"Ошибка соединения с API: {str(e)}"
        print(f"Ошибка запроса: {error_message}")
        return render_template('promocode.html', promocodes=[], error_message=error_message)
    except Exception as e:
        error_message = f"Произошла ошибка: {str(e)}"
        print(f"Общая ошибка: {error_message}")
        return render_template('promocode.html', promocodes=[], error_message=error_message)

@app.route('/promocodes/create', methods=['POST'])
@login_required
def create_promocode():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promocodes/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        promocode_data = {
            'activation_limit': int(data.get('activation_limit')),
            'percentage': int(data.get('percentage'))
        }
        
        response = requests.post(api_url, json=promocode_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            resp_data = response.json()
            return jsonify({
                "success": True, 
                "message": "Промокод успешно создан",
                "promocode": resp_data.get("promocode") 
            })
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/promocodes/delete', methods=['POST'])
@login_required
def delete_promocode():
    try:
        data = request.json
        promocode = data.get('code')
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promocodes/{promocode}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.delete(api_url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Промокод успешно удален"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/payment-codes')
@app.route('/payment-codes/<int:page>')
@login_required
def payment_codes(page=1):
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return render_template('payment_codes.html', pay_codes=[], 
                                  error_message="Нет активных API настроек. Пожалуйста, настройте API в разделе настроек.")
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/pay-codes/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            pay_codes_data = response.json()
            
            if not isinstance(pay_codes_data, list):
                pay_codes_data = [pay_codes_data]
            
            active_codes = [code for code in pay_codes_data if code.get('is_enable') == 1]
            inactive_codes = [code for code in pay_codes_data if code.get('is_enable') != 1]
            
            active_codes = sorted(active_codes, key=lambda x: x.get('create_date', ''), reverse=True)
            inactive_codes = sorted(inactive_codes, key=lambda x: x.get('create_date', ''), reverse=True)
            
            pay_codes_data = active_codes + inactive_codes
            
            
            per_page = 10
            total_items = len(pay_codes_data)
            total_pages = (total_items + per_page - 1) // per_page  
            
            if page < 1:
                page = 1
            elif page > total_pages and total_pages > 0:
                page = total_pages
            
            start_idx = (page - 1) * per_page
            end_idx = min(start_idx + per_page, total_items)
            current_page_data = pay_codes_data[start_idx:end_idx]
            
            return render_template('payment_codes.html', 
                                  pay_codes=current_page_data,
                                  current_page=page,
                                  total_pages=total_pages,
                                  total_items=total_items)
        else:
            error_message = f"Ошибка API: {response.status_code} - {response.text}"
            print(f"Ошибка API запроса: {error_message}")
            return render_template('payment_codes.html', 
                                  pay_codes=[], 
                                  error_message=error_message,
                                  current_page=1,
                                  total_pages=0,
                                  total_items=0)
            
    except requests.RequestException as e:
        error_message = f"Ошибка соединения с API: {str(e)}"
        print(f"Ошибка запроса: {error_message}")
        return render_template('payment_codes.html', 
                              pay_codes=[], 
                              error_message=error_message,
                              current_page=1,
                              total_pages=0,
                              total_items=0)
    except Exception as e:
        error_message = f"Произошла ошибка: {str(e)}"
        print(f"Общая ошибка: {error_message}")
        return render_template('payment_codes.html', 
                              pay_codes=[], 
                              error_message=error_message,
                              current_page=1,
                              total_pages=0,
                              total_items=0)

@app.route('/payment-codes/create', methods=['POST'])
@login_required
def create_pay_code():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/pay-codes/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        pay_code_data = {
            'amount': int(data.get('amount')),
            'count': int(data.get('count'))
        }
        
        response = requests.post(api_url, json=pay_code_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            return jsonify({
                "success": True, 
                "message": "Коды оплаты успешно созданы"
            })
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/payment-codes/delete', methods=['POST'])
@login_required
def delete_pay_code():
    try:
        data = request.json
        pay_code = data.get('code')
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/pay-codes/{pay_code}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.delete(api_url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Код оплаты успешно удален"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/servers')
@login_required
def servers():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return render_template('servers.html', servers=[], 
                                  error_message="Нет активных API настроек. Пожалуйста, настройте API в разделе настроек.")
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/servers/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            servers_data = response.json()
            
            if not isinstance(servers_data, list):
                servers_data = [servers_data]
                
            return render_template('servers.html', servers=servers_data)
        else:
            error_message = f"Ошибка API: {response.status_code} - {response.text}"
            print(f"Ошибка API запроса: {error_message}")
            return render_template('servers.html', servers=[], error_message=error_message)
            
    except requests.RequestException as e:
        error_message = f"Ошибка соединения с API: {str(e)}"
        print(f"Ошибка запроса: {error_message}")
        return render_template('servers.html', servers=[], error_message=error_message)
    except Exception as e:
        error_message = f"Произошла ошибка: {str(e)}"
        print(f"Общая ошибка: {error_message}")
        return render_template('servers.html', servers=[], error_message=error_message)

@app.route('/servers/create', methods=['POST'])
@login_required
def create_server():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/servers/"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        server_data = {
            'name': data.get('name'),
            'url': data.get('url'),
            'port': data.get('port'),
            'secret_path': data.get('secret_path'),
            'username': data.get('username'),
            'password': data.get('password'),
            'inbound_id': int(data.get('inbound_id')),
            'protocol': data.get('protocol'),
            'ip': data.get('ip')
        }
        
        response = requests.post(api_url, json=server_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            return jsonify({
                "success": True, 
                "message": "Сервер успешно создан"
            })
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/servers/delete', methods=['POST'])
@login_required
def delete_server():
    try:
        data = request.json
        server_id = data.get('id')
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/servers/{server_id}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.delete(api_url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Сервер успешно удален"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/servers/info', methods=['POST'])
@login_required
def get_server_info():
    try:
        data = request.json
        server_id = data.get('id')
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/servers/{server_id}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            server_data = response.json()
            return jsonify({"success": True, "data": server_data})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/referral')
@login_required
def referral():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return render_template('referral.html', referrals=[], rewards_history=[],
                                error_message="Нет активных API настроек. Пожалуйста, настройте подключение в разделе Настройки API.")
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/referral/conditions"
        rewards_history_url = f"{base_url}/referral/rewards/history?limit=100&offset=0"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers)
        referrals = []
        if response.status_code == 200:
            referrals = response.json()
            
        rewards_response = requests.get(rewards_history_url, headers=headers)
        rewards_history = []
        if rewards_response.status_code == 200:
            rewards_history = rewards_response.json()
        
        return render_template('referral.html', referrals=referrals, rewards_history=rewards_history)
    
    except Exception as e:
        return render_template('referral.html', referrals=[], rewards_history=[],
                             error_message=f"Произошла ошибка: {str(e)}")


@app.route('/referral/create', methods=['POST'])
@login_required
def create_referral():
    try:
        data = request.json
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/referral/conditions"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        referral_data = {
            'name': data.get('name'),
            'description': data.get('description'),
            'invitations': int(data.get('invitations')),
            'reward_sum': int(data.get('reward_sum'))
        }
        
        response = requests.post(api_url, json=referral_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            return jsonify({
                "success": True, 
                "message": "Реферальная программа успешно создана"
            })
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/referral/delete', methods=['POST'])
@login_required
def delete_referral():
    try:
        data = request.json
        referral_id = data.get('id')
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/referral/conditions/{referral_id}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.delete(api_url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            return jsonify({"success": True, "message": "Реферальная программа успешно удалена"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/users')
@app.route('/users/<int:page>')
@login_required
def users(page=1):
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return render_template('users.html', users=[], 
                                  error_message="Нет активных API настроек. Пожалуйста, настройте подключение в разделе Настройки API.")
        
        items_per_page = 25
        skip = (page - 1) * items_per_page
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/users/all?skip={skip}&limit={items_per_page}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=60)
        
        total_count = 0
        try:
            count_url = f"{base_url}/statistics/users/count"
            count_response = requests.get(count_url, headers=headers, timeout=10)
            if count_response.status_code == 200:
                count_data = count_response.json()
                total_count = count_data.get('total_users', 0)
            else:
                total_count = 2000  
        except Exception as e:
            print(f"Ошибка при получении общего количества пользователей: {str(e)}")
            total_count = 2000  
        
        if response.status_code == 200:
            users_data = response.json()
            
            if not isinstance(users_data, list):
                users_data = [users_data]
            
            for user in users_data:
                balance_url = f"{base_url}/users/{user['telegram_id']}/balance"
                balance_response = requests.get(balance_url, headers=headers, timeout=5)
                
                if balance_response.status_code == 200:
                    balance_data = balance_response.json()
                    user['balance'] = balance_data.get('balance', 0)
                else:
                    user['balance'] = 0

                payments_url = f"{base_url}/users/{user['telegram_id']}/payments/sum"
                payments_response = requests.get(payments_url, headers=headers, timeout=5)
                
                if payments_response.status_code == 200:
                    payments_data = payments_response.json()
                    user['total_payments'] = payments_data.get('total_payments', 0)
                else:
                    user['total_payments'] = 0
            
            from datetime import datetime
            
            def parse_date(date_str):
                try:
                    return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    return datetime(1970, 1, 1)  
            
            users_data = sorted(users_data, key=lambda user: parse_date(user.get('date')), reverse=True)
            
                
            total_pages = (total_count + items_per_page - 1) // items_per_page  
            
            return render_template('users.html', 
                users=users_data,
                current_page=page,
                total_pages=total_pages,
                total_items=total_count,
                error_message=None
            )
        else:
            error_message = f"Ошибка API: {response.status_code} - {response.text}"
            print(f"Ошибка API запроса: {error_message}")
            return render_template('users.html', users=[], error_message=error_message)
            
    except requests.RequestException as e:
        error_message = f"Ошибка соединения с API: {str(e)}"
        print(f"Ошибка запроса: {error_message}")
        return render_template('users.html', users=[], error_message=error_message)
    except Exception as e:
        error_message = f"Произошла ошибка: {str(e)}"
        print(f"Общая ошибка: {error_message}")
        return render_template('users.html', users=[], error_message=error_message)

@app.route('/users/details', methods=['POST'])
@login_required
def get_user_details():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        
        if not telegram_id:
            return jsonify({"success": False, "message": "Не указан Telegram ID"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        user_url = f"{base_url}/users/{telegram_id}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(user_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            user_data = response.json()
            
            balance_url = f"{base_url}/users/{telegram_id}/balance"
            balance_response = requests.get(balance_url, headers=headers, timeout=5)
            
            if balance_response.status_code == 200:
                balance_data = balance_response.json()
                user_data['balance'] = balance_data.get('balance', 0)
            else:
                user_data['balance'] = 0
            
            payments_url = f"{base_url}/users/{telegram_id}/payments/sum"
            payments_response = requests.get(payments_url, headers=headers, timeout=5)
            
            if payments_response.status_code == 200:
                payments_data = payments_response.json()
                user_data['total_payments'] = payments_data.get('total_payments', 0)
            else:
                user_data['total_payments'] = 0
            
            subscriptions_url = f"{base_url}/users/{telegram_id}/subscriptions"
            subscriptions_response = requests.get(subscriptions_url, headers=headers, timeout=5)
            
            if subscriptions_response.status_code == 200:
                subscriptions_data = subscriptions_response.json()
                
                if not isinstance(subscriptions_data, list):
                    subscriptions_data = [subscriptions_data]
                    
                user_data['subscriptions'] = subscriptions_data
            else:
                user_data['subscriptions'] = []
            
            return jsonify({"success": True, "data": user_data})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/users/ban', methods=['POST'])
@login_required
def ban_user():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        
        if not telegram_id:
            return jsonify({"success": False, "message": "Не указан Telegram ID"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/users/{telegram_id}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.delete(api_url, headers=headers, timeout=10)
        
        if response.status_code in [200, 204]:
            try:
                result = response.json()
                if result.get('success'):
                    return jsonify({"success": True, "message": "Пользователь успешно заблокирован"})
                else:
                    return jsonify({"success": False, "message": result.get('message', 'Ошибка блокировки пользователя')})
            except:
                return jsonify({"success": True, "message": "Пользователь успешно заблокирован"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/users/unban', methods=['POST'])
@login_required
def unban_user():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        
        if not telegram_id:
            return jsonify({"success": False, "message": "Не указан Telegram ID"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/users/{telegram_id}/enable"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(api_url, headers=headers, data='', timeout=10)
        
        if response.status_code in [200, 201]:
            try:
                result = response.json()
                if result.get('success'):
                    return jsonify({"success": True, "message": "Пользователь успешно разблокирован"})
                else:
                    return jsonify({"success": False, "message": result.get('message', 'Ошибка разблокировки пользователя')})
            except:
                return jsonify({"success": True, "message": "Пользователь успешно разблокирован"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/users/create', methods=['POST'])
@login_required
def create_user():
    try:
        data = request.json
        email = data.get('email')
        server_id = data.get('server_id')
        tariff_id = data.get('tariff_id')
        telegram_id = data.get('telegram_id')
        
        if not all([email, server_id, tariff_id, telegram_id]):
            return jsonify({"success": False, "message": "Необходимо заполнить все поля"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/users/create"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        user_data = {
            'email': email,
            'server_id': int(server_id),
            'tariff_id': int(tariff_id),
            'telegram_id': int(telegram_id),
            'username': email  
        }
        
        response = requests.post(api_url, json=user_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            response_data = response.json()
            return jsonify({
                "success": True,
                "message": "Пользователь успешно создан",
                "user_data": response_data.get('user_data', {}),
                "connect_link": response_data.get('connect_link', '')
            })
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/users/add-balance', methods=['POST'])
@login_required
def add_balance():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        amount = data.get('amount')
        description = data.get('description', 'Пополнение баланса администратором')
        
        if not telegram_id or not amount:
            return jsonify({"success": False, "message": "Необходимо указать ID пользователя и сумму пополнения"})
        
        try:
            amount = float(amount)
            if amount <= 0:
                return jsonify({"success": False, "message": "Сумма пополнения должна быть положительным числом"})
        except:
            return jsonify({"success": False, "message": "Некорректная сумма пополнения"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/users/balance/update"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        balance_data = {
            'user_id': telegram_id,
            'amount': amount,
            'type': 'api_transaction',
            'description': description
        }
        
        response = requests.post(api_url, json=balance_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            try:
                result = response.json()
                if result.get('success'):
                    return jsonify({"success": True, "message": "Баланс пользователя успешно пополнен"})
                else:
                    return jsonify({"success": False, "message": result.get('message', 'Ошибка пополнения баланса')})
            except:
                return jsonify({"success": True, "message": "Баланс пользователя успешно пополнен"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/promo-tariffs/list', methods=['GET'])
@login_required
def get_promo_tariffs():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promo-tariffs"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            servers_url = f"{base_url}/servers"
            servers_response = requests.get(servers_url, headers=headers, timeout=10)
            
            servers_data = {}
            if servers_response.status_code == 200:
                servers = servers_response.json()
                if isinstance(servers, list):
                    for server in servers:
                        servers_data[server['id']] = server['name']
            
            promo_tariffs = response.json()
            
            if not isinstance(promo_tariffs, list):
                promo_tariffs = [promo_tariffs]
            
            for tariff in promo_tariffs:
                server_id = tariff.get('server_id')
                tariff['server_name'] = servers_data.get(server_id, f"Сервер ID: {server_id}")
            
            return jsonify({"success": True, "data": promo_tariffs})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/promo-tariffs/send', methods=['POST'])
@login_required
def send_promo_tariff():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        tariff_id = data.get('tariff_id')
        
        if not telegram_id or not tariff_id:
            return jsonify({"success": False, "message": "Необходимо указать ID пользователя и ID тарифа"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promo-tariffs/{tariff_id}/send"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        send_data = {
            'user_id': telegram_id
        }
        
        response = requests.post(api_url, json=send_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            try:
                result = response.json()
                if result.get('success'):
                    return jsonify({"success": True, "message": "Промо-тариф успешно отправлен пользователю"})
                else:
                    return jsonify({"success": False, "message": result.get('message', 'Ошибка отправки промо-тарифа')})
            except:
                return jsonify({"success": True, "message": "Промо-тариф успешно отправлен пользователю"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/users/send-promo-tariff', methods=['POST'])
@login_required
def user_send_promo_tariff():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        tariff_id = data.get('tariff_id')
        
        if not telegram_id or not tariff_id:
            return jsonify({"success": False, "message": "Необходимо указать ID пользователя и ID тарифа"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/promo-tariffs/send-with-server"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        send_data = {
            'promo_id': int(tariff_id),
            'telegram_id': int(telegram_id)
        }
        
        response = requests.post(api_url, json=send_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Промо-тариф успешно отправлен пользователю"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/users/send-message', methods=['POST'])
@login_required
def send_user_message():
    try:
        data = request.json
        telegram_id = data.get('telegram_id')
        message = data.get('message')
        
        if not telegram_id or not message:
            return jsonify({"success": False, "message": "Необходимо указать ID пользователя и текст сообщения"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/broadcast/user"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        send_data = {
            'telegram_id': int(telegram_id),
            'message': message
        }
        
        response = requests.post(api_url, json=send_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Сообщение успешно отправлено"})
        else:
            return jsonify({"success": False, "message": f"Ошибка API: {response.status_code} - {response.text}"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/get_tariffs', methods=['GET'])
@login_required
def get_tariffs():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
            
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        response = requests.get(f"{base_url}/tariffs", headers=headers)
        
        if response.status_code == 200:
            return jsonify({"success": True, "tariffs": response.json()})
        else:
            return jsonify({"success": False, "message": "Ошибка получения списка тарифов"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/servers/update', methods=['POST'])
@login_required
def update_server():
    try:
        data = request.json
        server_id = data.get('id')
        
        if not server_id:
            return jsonify({"success": False, "message": "ID сервера не указан"})
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})
        
        update_data = {
            "name": data.get('name'),
            "ip": data.get('ip'),
            "port": data.get('port'),
            "inbound_id": data.get('inbound_id'),
            "is_enable": data.get('is_enable', 1)
        }
        
        if 'inbound_id_promo' in data:
            update_data["inbound_id_promo"] = data.get('inbound_id_promo')
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        api_url = f"{base_url}/servers/{server_id}"
        
        response = requests.put(api_url, json=update_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            resp_data = response.json()
            return jsonify({
                "success": True, 
                "message": resp_data.get('message', "Сервер успешно обновлен"),
                "server": resp_data.get('server')
            })
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('message', f"Ошибка API: {response.status_code}")
            except:
                error_message = f"Ошибка API: {response.status_code} - {response.text}"
            return jsonify({"success": False, "message": error_message})
             
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Ошибка при обновлении сервера: {error_details}")
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    create_tables()
    app.run(host='0.0.0.0', port=5000, debug=True) 