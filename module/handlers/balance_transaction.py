from flask import Blueprint, render_template, flash, request, redirect, url_for
from flask_login import login_required
import requests
import math
from models import ApiSettings

balance_transaction = Blueprint('balance_transaction', __name__)

@balance_transaction.route('/balance-transactions')
@balance_transaction.route('/balance-transactions/<int:page>')
@login_required
def index(page=1):
    try:
        
        if request.args.get('page'):
            return redirect(url_for('balance_transaction.index', page=int(request.args.get('page'))))
            
        limit = 50  
        skip = (page - 1) * limit  
        
        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            flash('Нет активных API настроек. Пожалуйста, настройте подключение в разделе Настройки API.', 'warning')
            return render_template('balance-transaction.html', transactions=[], total_pages=0, current_page=page)
        
        base_url = api_setting.api_url.rstrip('/')
        transactions_url = f"{base_url}/statistics/balance-transactions?skip={skip}&limit={limit}"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        response = requests.get(transactions_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            transactions = data.get('transactions', [])
            total_count = data.get('total_count', 0)
            
            for transaction in transactions:
                if transaction.get('type') == 'api_transaction':
                    transaction['type_display'] = 'Пополнение Администратором веб-панели'
                elif transaction.get('type') == 'deposit':
                    transaction['type_display'] = 'Пополнение через бота'
                elif transaction.get('type') == 'pending':
                    transaction['type_display'] = 'Ожидание оплаты'
                elif transaction.get('type') == 'subscription_payment':
                    transaction['type_display'] = 'Оплата тарифа'
                else:
                    transaction['type_display'] = transaction.get('type', '')
            
            total_pages = math.ceil(total_count / limit)
            
            return render_template('balance-transaction.html', 
                transactions=transactions,
                total_pages=total_pages,
                current_page=page,
                total_count=total_count
            )
        else:
            error_message = f"Ошибка при получении транзакций: {response.status_code}"
            try:
                error_data = response.json()
                if 'message' in error_data:
                    error_message = error_data['message']
            except:
                pass
            
            flash(error_message, 'danger')
            return render_template('balance-transaction.html', transactions=[], total_pages=0, current_page=page)
            
    except requests.RequestException as e:
        flash(f'Ошибка соединения с API: {str(e)}', 'danger')
        return render_template('balance-transaction.html', transactions=[], total_pages=0, current_page=page)
    except Exception as e:
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return render_template('balance-transaction.html', transactions=[], total_pages=0, current_page=page) 