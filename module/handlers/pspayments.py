from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
import requests
from models import ApiSettings

pspayments = Blueprint('pspayments', __name__)

@pspayments.route('/pspayments-settings')
@login_required
def index():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        if not api_setting:
            return render_template('pspayments-settings.html', settings=None)

        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        response = requests.get(f"{base_url}/providers/pspayments/", headers=headers)

        if response.status_code == 200:
            settings = response.json()
            return render_template('pspayments-settings.html', settings=settings)
        else:
            return render_template('pspayments-settings.html', settings=None)

    except Exception as e:
        return render_template('pspayments-settings.html', settings=None)

@pspayments.route('/pspayments-settings/add', methods=['POST'])
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
            f"{base_url}/providers/pspayments/",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            return jsonify({"success": True, "message": "Настройки успешно добавлены"})
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Ошибка при добавлении настроек')
            except:
                error_message = f"Ошибка сервера: {response.status_code}"
            return jsonify({"success": False, "message": error_message})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@pspayments.route('/pspayments-settings/delete', methods=['POST'])
@login_required
def delete_settings():
    try:
        data = request.json
        print(f"Полученные данные для удаления: {data}")  
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            return jsonify({"success": False, "message": "Нет активных API настроек"})

        headers = {
            'X-API-Key': api_setting.api_key,
            'Content-Type': 'application/json',
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        shop_id = str(data['shop_id']).strip()
        
        print(f"Отправка DELETE запроса на {base_url}/providers/pspayments/ с shop_id: {shop_id}")
        
        response = requests.delete(
            f"{base_url}/providers/pspayments/",
            headers=headers,
            json={"shop_id": shop_id}
        )

        print(f"Ответ сервера: {response.status_code}, {response.text}")

        if response.status_code in [200, 201, 202, 204]:
            try:
                resp_data = response.json()
                return jsonify({
                    "success": True,
                    "message": resp_data.get('message', "Настройки успешно удалены")
                })
            except:
                return jsonify({"success": True, "message": "Настройки успешно удалены"})
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('message', 'Ошибка при удалении настроек')
            except:
                error_message = f"Ошибка сервера: {response.status_code} ({response.text})"
            return jsonify({"success": False, "message": error_message})

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Ошибка при удалении настроек PSPayments: {error_details}")
        return jsonify({"success": False, "message": f"Ошибка: {str(e)}"})

@pspayments.route('/pspayments-settings/get', methods=['GET'])
@login_required
def get_settings():
    try:
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        if not api_setting:
            return jsonify({"success": True, "settings": None})

        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        response = requests.get(f"{base_url}/providers/pspayments/", headers=headers)

        if response.status_code == 200:
            settings = response.json()
            return jsonify({"success": True, "settings": settings})
        else:
            return jsonify({"success": True, "settings": None})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}) 