from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
import requests
from models import ApiSettings

bot_messages = Blueprint('bot_messages', __name__)

@bot_messages.route('/bot-messages')
@login_required
def index():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        if not api_setting:
            return render_template('bot-messages.html', messages=None)

        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        response = requests.get(f"{base_url}/bot-messages/", headers=headers)

        if response.status_code == 200:
            messages = response.json()
            return render_template('bot-messages.html', messages=messages)
        else:
            return render_template('bot-messages.html', messages=None)

    except Exception as e:
        return render_template('bot-messages.html', messages=None)

@bot_messages.route('/bot-messages/toggle', methods=['POST'])
@login_required
def toggle_message():
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
            f"{base_url}/bot-messages/toggle",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Ошибка при обновлении статуса"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@bot_messages.route('/bot-messages/update', methods=['POST'])
@login_required
def update_message():
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
            f"{base_url}/bot-messages/update",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            return jsonify({"success": True, "message": "Сообщение успешно обновлено"})
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Ошибка при обновлении сообщения')
            except:
                error_message = f"Ошибка сервера: {response.status_code}"
            return jsonify({"success": False, "message": error_message})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}) 