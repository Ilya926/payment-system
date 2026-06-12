# app.py - Платёжная система с интеграцией Stripe
# Студенты: Кожурин Илья и Мендыбаев Данил 09.07.34

from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import datetime
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv
from webhooks.stripe_webhook import StripeWebhookHandler
from src.services.payment_factory import PaymentFactory

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'секретныйключстудента123')


class User:
    """Класс для хранения информации о пользователе"""

    def __init__(self, user_id: int, name: str, email: str, password: str, balance: float = 0.0):
        self.user_id = user_id
        self.name = name
        self.email = email
        self.password = password
        self.balance = balance

    def to_dict(self) -> Dict:
        return {
            "user_id": self.user_id,
            "name": self.name,
            "email": self.email,
            "password": self.password,
            "balance": self.balance
        }


class Transaction:
    """Класс для транзакции (платеж)"""

    def __init__(self, trans_id: int, from_user_id: int, to_user_id: int,
                 amount: float, status: str = "pending",
                 payment_method: str = "internal"):
        self.trans_id = trans_id
        self.from_user_id = from_user_id
        self.to_user_id = to_user_id
        self.amount = amount
        self.status = status
        self.payment_method = payment_method
        self.created_at = datetime.datetime.now()

    def to_dict(self) -> Dict:
        return {
            "trans_id": self.trans_id,
            "from": self.from_user_id,
            "to": self.to_user_id,
            "amount": self.amount,
            "status": self.status,
            "payment_method": self.payment_method,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        }


class PaymentSystem:
    """Класс для работы с платежами"""

    def __init__(self):
        self.users: Dict[int, User] = {}
        self.transactions: List[Transaction] = []
        self.next_user_id = 1
        self.next_trans_id = 1
        self.load_from_file()

    def register_user(self, name: str, email: str, password: str) -> int:
        for user in self.users.values():
            if user.email == email:
                return -1
        user = User(self.next_user_id, name, email, password)
        self.users[self.next_user_id] = user
        self.next_user_id += 1
        self.save_to_file()
        return user.user_id

    def login(self, email: str, password: str) -> Optional[int]:
        for user in self.users.values():
            if user.email == email and user.password == password:
                return user.user_id
        return None

    def deposit(self, user_id: int, amount: float, payment_method: str = "internal") -> bool:
        """Пополнение баланса"""
        if user_id not in self.users or amount <= 0:
            return False

        user = self.users[user_id]
        user.balance += amount

        trans = Transaction(
            self.next_trans_id, 0, user_id, amount,
            "completed", payment_method
        )
        self.transactions.append(trans)
        self.next_trans_id += 1
        self.save_to_file()
        return True

    def transfer(self, from_user_id: int, to_user_id: int, amount: float) -> tuple:
        if from_user_id not in self.users:
            return False, "Отправитель не найден"
        if to_user_id not in self.users:
            return False, "Получатель не найден"
        if from_user_id == to_user_id:
            return False, "Нельзя переводить деньги самому себе"
        if amount <= 0:
            return False, "Сумма перевода должна быть больше 0"

        sender = self.users[from_user_id]
        receiver = self.users[to_user_id]

        if sender.balance < amount:
            return False, f"Недостаточно средств. Ваш баланс: {sender.balance} руб."

        trans = Transaction(self.next_trans_id, from_user_id, to_user_id, amount, "completed")
        self.transactions.append(trans)
        self.next_trans_id += 1

        sender.balance -= amount
        receiver.balance += amount
        self.save_to_file()
        return True, f"Перевод {amount} руб. выполнен успешно!"

    def get_balance(self, user_id: int) -> Optional[float]:
        if user_id not in self.users:
            return None
        return self.users[user_id].balance

    def get_user(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        return self.users.get(user_id)

    def get_all_users(self) -> List[User]:
        return list(self.users.values())

    def get_user_transactions(self, user_id: int) -> List[Transaction]:
        user_trans = []
        for trans in self.transactions:
            if trans.from_user_id == user_id or trans.to_user_id == user_id:
                user_trans.append(trans)
        return user_trans

    def save_to_file(self):
        data = {
            "users": {uid: user.to_dict() for uid, user in self.users.items()},
            "transactions": [trans.to_dict() for trans in self.transactions],
            "next_user_id": self.next_user_id,
            "next_trans_id": self.next_trans_id
        }
        with open("payment_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_from_file(self):
        try:
            with open("payment_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            self.users = {}
            for uid, user_data in data["users"].items():
                user = User(
                    user_data["user_id"],
                    user_data["name"],
                    user_data["email"],
                    user_data["password"],
                    user_data["balance"]
                )
                self.users[int(uid)] = user

            self.transactions = []
            for trans_data in data["transactions"]:
                trans = Transaction(
                    trans_data["trans_id"],
                    trans_data["from"],
                    trans_data["to"],
                    trans_data["amount"],
                    trans_data.get("status", "completed"),
                    trans_data.get("payment_method", "internal")
                )
                trans.created_at = datetime.datetime.strptime(
                    trans_data["created_at"], "%Y-%m-%d %H:%M:%S"
                )
                self.transactions.append(trans)

            self.next_user_id = data["next_user_id"]
            self.next_trans_id = data["next_trans_id"]
        except:
            pass


# СОЗДАНИЕ ГЛОБАЛЬНЫХ ОБЪЕКТОВ

payment_system = PaymentSystem()

webhook_handler = StripeWebhookHandler(payment_system)
payment_factory = PaymentFactory('stripe')
stripe_service = payment_factory.get_service()


@app.route('/')
def index():
    """Главная страница"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация пользователя"""
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        user_id = payment_system.register_user(name, email, password)
        if user_id == -1:
            flash('Пользователь с таким email уже существует!', 'error')
            return redirect(url_for('register'))

        flash(f'Регистрация успешна! Ваш ID: {user_id}', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вход в систему"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user_id = payment_system.login(email, password)
        if user_id:
            session['user_id'] = user_id
            flash(f'Добро пожаловать, {payment_system.get_user(user_id).name}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный email или пароль!', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Выход из системы"""
    session.pop('user_id', None)
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    """Личный кабинет"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = payment_system.get_user(session['user_id'])
    balance = payment_system.get_balance(session['user_id'])
    transactions = payment_system.get_user_transactions(session['user_id'])

    # Флаг Stripe
    stripe_enabled = bool(os.getenv('STRIPE_SECRET_KEY'))

    return render_template('dashboard.html',
                           user=user,
                           balance=balance,
                           transactions=transactions,
                           stripe_enabled=stripe_enabled)


@app.route('/deposit', methods=['POST'])
def deposit():
    """Пополнение баланса (внутреннее)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        amount = float(request.form['amount'])
        if payment_system.deposit(session['user_id'], amount):
            flash(f'Баланс пополнен на {amount} руб.', 'success')
        else:
            flash('Ошибка пополнения! Сумма должна быть больше 0', 'error')
    except:
        flash('Введите корректную сумму!', 'error')

    return redirect(url_for('dashboard'))


@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    """Перевод денег"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            to_user_id = int(request.form['to_user_id'])
            amount = float(request.form['amount'])

            success, message = payment_system.transfer(session['user_id'], to_user_id, amount)
            flash(message, 'success' if success else 'error')
        except:
            flash('Ошибка! Проверьте введенные данные', 'error')

        return redirect(url_for('dashboard'))

    users = payment_system.get_all_users()
    current_user = payment_system.get_user(session['user_id'])
    return render_template('transfer.html', users=users, current_user=current_user)


@app.route('/history')
def history():
    """История всех операций"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    transactions = payment_system.get_user_transactions(session['user_id'])
    all_users = {u.user_id: u for u in payment_system.get_all_users()}

    return render_template('history.html', transactions=transactions, users=all_users)

@app.route('/stripe')
def stripe_page():
    """Страница выбора суммы для пополнения через Stripe"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('stripe_deposit.html')


@app.route('/stripe', methods=['POST'])
def stripe_create_payment():
    """Создание платежа в Stripe и показ формы оплаты"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        amount_rub = float(request.form['amount'])

        # Конвертация рублей в доллары (примерный курс 90 руб/$)
        amount_usd = round(amount_rub / 90, 2)

        # Минимальная сумма в Stripe — $0.50
        if amount_usd < 0.50:
            flash('Минимальная сумма пополнения: 45 руб.', 'error')
            return redirect(url_for('stripe_page'))

        # Создаём платёж через Stripe
        result = stripe_service.create_payment(
            amount=amount_usd,
            currency='usd',
            user_id=session['user_id']
        )

        if result['success']:
            # Сохраняем платёж как ожидающий подтверждения
            webhook_handler.add_pending(
                result['payment_intent_id'],
                session['user_id'],
                amount_rub
            )

            # Показываем форму для ввода карты
            return render_template('stripe_pay.html',
                                   client_secret=result['client_secret'],
                                   payment_intent_id=result['payment_intent_id'],
                                   amount_rub=amount_rub,
                                   amount_usd=amount_usd,
                                   publishable_key=os.getenv('STRIPE_PUBLISHABLE_KEY')
                                   )
        else:
            flash('Ошибка создания платежа в Stripe', 'error')
            return redirect(url_for('stripe_page'))

    except ValueError:
        flash('Введите корректную сумму!', 'error')
        return redirect(url_for('stripe_page'))
    except Exception as e:
        flash(f'Ошибка: {str(e)}', 'error')
        return redirect(url_for('stripe_page'))


@app.route('/stripe/success')
def stripe_success():
    """Страница после успешной оплаты (проверка и зачисление)"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    payment_intent_id = request.args.get('payment_intent_id')

    if not payment_intent_id:
        flash('Не указан ID платежа', 'error')
        return redirect(url_for('dashboard'))

    # Проверяем статус в Stripe
    try:
        status = stripe_service.get_status(payment_intent_id)
    except Exception as e:
        flash(f'Не удалось проверить статус: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

    if status['status'] == 'succeeded':
        # Зачисляем деньги
        pending = webhook_handler.pending_payments.get(payment_intent_id)

        if pending and pending.get('status') == 'pending':
            user_id = int(pending['user_id'])
            amount_rub = float(pending['amount_rub'])

            # Зачисление через систему
            success = payment_system.deposit(user_id, amount_rub, payment_method="stripe")

            if success:
                pending['status'] = 'completed'
                webhook_handler._save_pending()
                flash(f'✅ Баланс пополнен на {amount_rub} руб. через Stripe!', 'success')
            else:
                flash('Ошибка зачисления на баланс', 'error')
        else:
            flash('Платёж уже был обработан ранее', 'info')
    else:
        flash(f'Платёж не завершён. Статус: {status["status"]}', 'error')

    return redirect(url_for('dashboard'))


@app.route('/stripe/cancel')
def stripe_cancel():
    """Страница при отмене платежа"""
    flash('Платёж отменён', 'info')
    return redirect(url_for('dashboard'))


@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """
    Приём вебхуков от Stripe.
    Этот маршрут вызывается автоматически серверами Stripe.
    """
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')

    result, status_code = webhook_handler.handle(payload, sig_header)
    return result, status_code


# ЗАПУСК

if __name__ == '__main__':
    # Создаём папки, если их нет
    os.makedirs('src/services', exist_ok=True)
    os.makedirs('webhooks', exist_ok=True)
    os.makedirs('templates', exist_ok=True)

    print("=" * 50)
    print("🚀 Платёжная система запущена!")
    print(f"   Локальный доступ: http://localhost:5000")
    print(f"   Stripe пополнение: http://localhost:5000/stripe")
    print(f"   Stripe вебхук: http://localhost:5000/webhook/stripe")
    print("=" * 50)

    app.run(debug=True, host='0.0.0.0', port=5000)