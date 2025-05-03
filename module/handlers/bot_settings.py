from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
import requests
from models import ApiSettings

bot_settings = Blueprint('bot_settings', __name__)

@bot_settings.route('/bot-settings')
@login_required
def index():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        if not api_setting:
            return render_template('bot-settings.html', settings=None)

        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        response = requests.get(f"{base_url}/bot-settings/", headers=headers)

        if response.status_code == 200:
            data = response.json()
            settings = data.get('settings', None)
            return render_template('bot-settings.html', settings=settings)
        else:
            return render_template('bot-settings.html', settings=None)

    except Exception as e:
        print(f"Ошибка при получении настроек бота: {str(e)}")
        return render_template('bot-settings.html', settings=None)

@bot_settings.route('/bot-settings/update', methods=['POST'])
@login_required
def update_settings():
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
        
        update_data = {
            'bot_token': data.get('bot_token'),
            'admin_id': data.get('admin_id'),
            'chat_id': data.get('chat_id', ''),
            'chanel_id': data.get('chanel_id', ''),
            'is_enable': data.get('is_enable', True),
            'reg_notify': int(data.get('reg_notify', 0)),
            'pay_notify': int(data.get('pay_notify', 0))
        }
        
        response = requests.put(
            f"{base_url}/bot-settings/",
            headers=headers,
            json=update_data
        )

        if response.status_code == 200:
            resp_data = response.json()
            return jsonify({
                "success": True, 
                "message": resp_data.get('message', "Настройки бота успешно обновлены")
            })
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Ошибка при обновлении настроек бота')
            except:
                error_message = f"Ошибка сервера: {response.status_code} ({response.text})"
            return jsonify({"success": False, "message": error_message})

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Ошибка при обновлении настроек бота: {error_details}")
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"}) 