from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from flask_login import login_required
import requests
from models import ApiSettings

yoopayments = Blueprint('yoopayments', __name__)

@yoopayments.route('/yookassa-payments')
@yoopayments.route('/yookassa-payments/<int:page>')
@login_required
def index(page=1):
    try:
        if request.args.get('page'):
            return redirect(url_for('yoopayments.index', page=int(request.args.get('page'))))
            
        items_per_page = 50  
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        if not api_setting:
            return render_template('yookassa-payments.html', payments=None, error_message="Нет активных API настроек")

        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        base_url = api_setting.api_url.rstrip('/')
        
        response = requests.get(
            f"{base_url}/yookassa/payments", 
            headers=headers
        )
        
        total_amount = 0
        try:
            total_response = requests.get(
                f"{base_url}/statistics/payments/total", 
                headers=headers
            )
            if total_response.status_code == 200:
                total_data = total_response.json()
                total_amount = total_data.get('total_amount', 0)
        except Exception as e:
            print(f"Ошибка при получении общей суммы платежей: {str(e)}")

        if response.status_code == 200:
            data = response.json()
            all_payments = data.get('payments', [])
            total_count = len(all_payments)
            
            total_pages = (total_count + items_per_page - 1) // items_per_page
            
            start_idx = (page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, total_count)
            
            payments_for_page = all_payments[start_idx:end_idx] if start_idx < total_count else []
            
            return render_template(
                'yookassa-payments.html',
                payments=payments_for_page,
                current_page=page,
                total_pages=total_pages,
                total_items=total_count,
                total_amount=total_amount
            )
        else:
            error_message = f"Ошибка API: {response.status_code}"
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_message = error_data['message']
            except:
                pass
            
            return render_template(
                'yookassa-payments.html',
                payments=None,
                error_message=error_message
            )

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Ошибка при получении платежей ЮKassa: {error_details}")
        return render_template('yookassa-payments.html', payments=None, error_message=str(e)) 