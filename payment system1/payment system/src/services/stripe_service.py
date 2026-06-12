"""
Базовый сервис Stripe.
Создаёт платежи, проверяет статус, делает возвраты.
"""

import os
import stripe
from dotenv import load_dotenv

load_dotenv()
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')


class StripeService:
    """Прямая работа с API Stripe"""

    @staticmethod
    def create_payment(amount, currency='usd', user_id=None):
        """
        Создать PaymentIntent в Stripe.
        amount: сумма в долларах (10.00 = $10)
        """
        try:
            amount_in_cents = int(amount * 100)
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency=currency.lower(),
                metadata={'user_id': str(user_id)} if user_id else {}
            )
            return {
                'success': True,
                'client_secret': payment_intent.client_secret,
                'payment_intent_id': payment_intent.id,
                'status': payment_intent.status
            }
        except stripe.error.StripeError as e:
            raise Exception(f'Stripe error: {str(e)}')

    @staticmethod
    def get_status(payment_intent_id):
        """Получить статус платежа по ID"""
        try:
            pi = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                'status': pi.status,
                'amount': pi.amount / 100,
                'currency': pi.currency
            }
        except stripe.error.StripeError as e:
            raise Exception(f'Status check failed: {str(e)}')

    @staticmethod
    def refund(payment_intent_id):
        """Полный возврат платежа"""
        try:
            ref = stripe.Refund.create(payment_intent=payment_intent_id)
            return {
                'success': True,
                'refund_id': ref.id,
                'status': ref.status
            }
        except stripe.error.StripeError as e:
            raise Exception(f'Refund failed: {str(e)}')