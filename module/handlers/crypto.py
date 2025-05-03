from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
import requests
import json
from models import ApiSettings

crypto = Blueprint('crypto', __name__)

@crypto.route('/crypto')
@login_required
def index():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        if not api_setting:
            return render_template('crypto.html', settings=None)

        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        response = requests.get(f"{base_url}/cryptopay/", headers=headers)

        if response.status_code == 200:
            settings = response.json()
            return render_template('crypto.html', settings=settings)
        else:
            return render_template('crypto.html', settings=None)

    except Exception as e:
        return render_template('crypto.html', settings=None)

@crypto.route('/crypto/toggle', methods=['POST'])
@login_required
def toggle_settings():
    try:
        data = request.json
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})

        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        response = requests.put(
            f"{base_url}/cryptopay/toggle",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Ошибка при обновлении статуса"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@crypto.route('/crypto/settings', methods=['POST'])
@login_required
def add_settings():
    try:
        data = request.json
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})

        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        response = requests.post(
            f"{base_url}/cryptopay/",
            headers=headers,
            json={
                'api_token': data['api_token'],
                'min_amount': data['min_amount'],
                'supported_assets': ','.join(data['supported_assets']),
                'webhook_url': None,  
                'webhook_secret': None  
            }
        )

        if response.status_code in [200, 201]:
            return jsonify({"success": True, "message": "Настройки успешно сохранены"})
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Ошибка при сохранении настроек')
            except:
                error_message = f"Ошибка сервера: {response.status_code}"
            return jsonify({"success": False, "message": error_message})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}) 