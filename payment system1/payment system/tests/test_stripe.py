import pytest
from unittest.mock import patch, MagicMock
from src.services.stripe_service import StripeService


class TestStripeService:

    @patch('src.services.stripe_service.stripe.PaymentIntent')
    def test_create_payment(self, mock_pi):
        """Тест создания платежа"""
        mock_instance = MagicMock()
        mock_instance.id = 'pi_test_123'
        mock_instance.client_secret = 'cs_test_abc'
        mock_instance.status = 'requires_payment_method'
        mock_pi.create.return_value = mock_instance

        result = StripeService.create_payment(10.00, 'usd', 'user123')

        assert result['success'] is True
        assert result['payment_intent_id'] == 'pi_test_123'
        assert result['client_secret'] == 'cs_test_abc'

    @patch('src.services.stripe_service.stripe.PaymentIntent')
    def test_get_status(self, mock_pi):
        """Тест проверки статуса"""
        mock_instance = MagicMock()
        mock_instance.status = 'succeeded'
        mock_instance.amount = 1000
        mock_instance.currency = 'usd'
        mock_pi.retrieve.return_value = mock_instance

        result = StripeService.get_status('pi_test_123')

        assert result['status'] == 'succeeded'
        assert result['amount'] == 10.00

    @patch('src.services.stripe_service.stripe.Refund')
    def test_refund(self, mock_ref):
        """Тест возврата платежа"""
        mock_instance = MagicMock()
        mock_instance.id = 'rf_test_456'
        mock_instance.status = 'succeeded'
        mock_ref.create.return_value = mock_instance

        result = StripeService.refund('pi_test_123')

        assert result['success'] is True
        assert result['refund_id'] == 'rf_test_456'

    @patch('src.services.stripe_service.stripe.PaymentIntent')
    def test_stripe_error(self, mock_pi):
        """Тест обработки ошибки Stripe"""
        import stripe
        mock_pi.create.side_effect = stripe.error.StripeError('Ошибка')

        with pytest.raises(Exception, match='Stripe error'):
            StripeService.create_payment(10.00, 'usd', 'user123')