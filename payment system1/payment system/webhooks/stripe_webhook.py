"""
Обработчик вебхуков Stripe.
Автоматически подтверждает платежи при получении события от Stripe.
"""

import stripe
import os
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')


class StripeWebhookHandler:
    """Обрабатывает входящие события от Stripe"""

    def __init__(self, payment_system):
        """
        payment_system
        """
        self.payment_system = payment_system
        self.pending_payments = self._load_pending()

    def handle(self, payload, sig_header):
        """
        Главный обработчик вебхука.
        payload: сырое тело запроса (bytes)
        sig_header: заголовок Stripe-Signature
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, WEBHOOK_SECRET
            )
        except ValueError:
            return {'error': 'Invalid payload'}, 400
        except stripe.error.SignatureVerificationError:
            return {'error': 'Invalid signature'}, 400

        event_type = event['type']
        data = event['data']['object']

        # Платёж успешен -> зачисляем деньги
        if event_type == 'payment_intent.succeeded':
            return self._handle_success(data)

        # Платёж не прошёл
        elif event_type == 'payment_intent.payment_failed':
            return self._handle_failure(data)

        # Возврат
        elif event_type == 'charge.refunded':
            return self._handle_refund(data)

        return {'received': True, 'event': event_type}, 200

    def _handle_success(self, payment_intent):
        """Зачислить деньги при успешной оплате"""
        pi_id = payment_intent['id']
        print(f'✅ Webhook: платёж {pi_id} успешен')

        # Ищем ожидающий платёж
        pending = self.pending_payments.get(pi_id)

        if pending and pending.get('status') == 'pending':
            user_id = int(pending['user_id'])
            amount_rub = float(pending['amount_rub'])

            # Зачисляем через систему
            success = self.payment_system.deposit(user_id, amount_rub)

            if success:
                pending['status'] = 'completed'
                self._save_pending()
                print(f'   ✅ Баланс user_{user_id} пополнен на {amount_rub} руб.')
                return {'received': True, 'status': 'completed'}, 200
            else:
                print(f'   ❌ Ошибка зачисления')
                return {'error': 'Deposit failed'}, 500

        print(f'   ⚠️ Платёж не найден в ожидающих')
        return {'received': True, 'status': 'unknown'}, 200

    def _handle_failure(self, payment_intent):
        """Обработать проваленный платёж"""
        pi_id = payment_intent['id']
        error_msg = payment_intent.get('last_payment_error', {}).get('message', 'Неизвестно')
        print(f'❌ Webhook: платёж {pi_id} не прошёл ({error_msg})')

        # Удаляем из ожидающих
        if pi_id in self.pending_payments:
            del self.pending_payments[pi_id]
            self._save_pending()

        return {'received': True, 'status': 'failed'}, 200

    def _handle_refund(self, charge):
        """Обработать возврат"""
        print(f'↩️ Webhook: возврат {charge["id"]}')
        return {'received': True, 'status': 'refunded'}, 200

    def add_pending(self, payment_intent_id, user_id, amount_rub):
        """Добавить платёж в ожидающие подтверждения"""
        self.pending_payments[payment_intent_id] = {
            'user_id': user_id,
            'amount_rub': amount_rub,
            'status': 'pending'
        }
        self._save_pending()

    def _save_pending(self):
        """Сохранить ожидающие платежи"""
        import json
        try:
            with open('pending_payments.json', 'w', encoding='utf-8') as f:
                json.dump(self.pending_payments, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _load_pending(self):
        """Загрузить ожидающие платежи"""
        import json
        try:
            with open('pending_payments.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}