"""
Фабрика платёжных провайдеров.
Сейчас только Stripe, позже можно добавить YooKassa.
"""

from src.services.stripe_service import StripeService


class PaymentFactory:
    """Выбор платёжного провайдера"""

    PROVIDERS = {
        'stripe': StripeService,
        # 'yookassa'
    }

    def __init__(self, provider='stripe'):
        if provider not in self.PROVIDERS:
            raise ValueError(f'Провайдер {provider} не найден')
        self.provider = provider

    def get_service(self):
        """Возвращает класс сервиса"""
        return self.PROVIDERS[self.provider]