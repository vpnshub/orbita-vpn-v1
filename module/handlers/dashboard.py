from flask import Blueprint, render_template, flash
from flask_login import login_required
import requests
from models import ApiSettings
from operator import itemgetter
from datetime import datetime

dashboard = Blueprint('dashboard', __name__)

@dashboard.route('/dashboard')
@login_required
def index():
    try:
        default_data = {
            'total_users': 0,
            'total_subscriptions': 0,
            'popular_tariff': {'name': 'Нет данных', 'count': 0},
            'last_payment': {'price': 0, 'payment_date': 'Нет данных'},
            'total_amount': 0,
            'top_buyer': {'username': 'Нет данных', 'telegram_id': 0},
            'servers': [],
            'total_balance': 0,
            'users_with_balance': 0,
            'last_deposit': {
                'created_at': 'Нет данных',
                'username': 'Нет данных',
                'telegram_id': 0,
                'description': 'Нет данных',
                'amount': 0,
                'type': 'Нет данных'
            },
            'yookassa_payments': [],
            'crypto_payments': []
        }

        api_setting = ApiSettings.query.filter_by(is_active=True).first()
        
        if not api_setting:
            flash('Нет активных API настроек. Пожалуйста, настройте подключение в разделе Настройки API.', 'warning')
            return render_template('dashboard.html', **default_data)
        
        base_url = api_setting.api_url.rstrip('/')
        stats_url = f"{base_url}/statistics/summary"
        earnings_url = f"{base_url}/servers/earnings/stats"
        subscriptions_url = f"{base_url}/servers/subscriptions/stats"
        balance_url = f"{base_url}/statistics/user-balance"
        transactions_url = f"{base_url}/statistics/balance-transactions?skip=0&limit=1"
        yookassa_url = f"{base_url}/yookassa/payments"
        crypto_url = f"{base_url}/cryptopay/payments"
        
        headers = {
            'X-API-Key': api_setting.api_key,
            'accept': 'application/json'
        }
        
        responses = {}
        urls = {
            'stats': stats_url, 
            'earnings': earnings_url, 
            'subscriptions': subscriptions_url,
            'balance': balance_url,
            'transactions': transactions_url,
            'yookassa': yookassa_url,
            'crypto': crypto_url
        }
        
        for key, url in urls.items():
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 200:
                    responses[key] = resp.json()
                else:
                    flash(f"Ошибка при получении {key}: {resp.status_code}", 'danger')
            except requests.RequestException as e:
                flash(f'Ошибка соединения с API ({key}): {str(e)}', 'danger')
        
        stats_data = responses.get('stats', {})
        earnings_data = responses.get('earnings', [])
        subscriptions_data = responses.get('subscriptions', [])
        balance_data = responses.get('balance', {})
        transactions_data = responses.get('transactions', {})
        yookassa_data = responses.get('yookassa', {}).get('payments', [])
        crypto_data = responses.get('crypto', {}).get('payments', [])

        if yookassa_data:
            yookassa_data.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d %H:%M:%S'), reverse=True)
            yookassa_data = yookassa_data[:5]  

        if crypto_data:
            crypto_data.sort(key=lambda x: datetime.strptime(x['created_at'], '%Y-%m-%d %H:%M:%S'), reverse=True)
            crypto_data = crypto_data[:5]  
        
        servers = []
        for earnings in earnings_data:
            server_name = earnings.get('server_name', 'Нет данных')
            total_subs = earnings.get('total_subscriptions', 0)
            active_subs = next((s['subscriptions_count'] for s in subscriptions_data if s['server_name'] == server_name), 0)
            servers.append({
                'server_name': server_name,
                'total_subscriptions': total_subs,
                'subscriptions_count': active_subs
            })
        
        last_deposit = default_data['last_deposit']
        if 'transactions' in responses and 'transactions' in transactions_data:
            deposit_transactions = [t for t in transactions_data['transactions'] 
                                   if t.get('type') in ['deposit', 'api_transaction', 'transfer_in', 'transfer_out', 'referral_reward', 'subscription_payment']]
            if deposit_transactions:
                deposit_transactions.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                last_deposit = deposit_transactions[0]
        
        dashboard_data = {
            'total_users': stats_data.get('total_users', default_data['total_users']),
            'total_subscriptions': stats_data.get('total_subscriptions', default_data['total_subscriptions']),
            'popular_tariff': stats_data.get('popular_tariff', default_data['popular_tariff']),
            'last_payment': stats_data.get('last_payment', default_data['last_payment']),
            'total_amount': stats_data.get('total_amount', default_data['total_amount']),
            'top_buyer': stats_data.get('top_buyer', default_data['top_buyer']),
            'servers': servers,
            'total_balance': balance_data.get('total_balance', default_data['total_balance']),
            'users_with_balance': balance_data.get('users_count', default_data['users_with_balance']),
            'last_deposit': last_deposit,
            'yookassa_payments': yookassa_data,
            'crypto_payments': crypto_data
        }
        
        return render_template('dashboard.html', **dashboard_data)
    
    except Exception as e:
        flash(f'Произошла ошибка: {str(e)}', 'danger')
        return render_template('dashboard.html', **default_data)
