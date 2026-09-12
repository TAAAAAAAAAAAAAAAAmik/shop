TEXTS: dict[str, str] = {
    # --- common ---
    "btn.back": "◀️ Назад",
    "btn.cancel": "✖️ Отмена",
    "btn.menu": "🏠 В меню",
    "btn.pay": "💳 Оплатить",
    "btn.check": "🔄 Проверить оплату",
    "btn.confirm": "✅ Подтвердить",
    "btn.buy": "🛒 Купить",
    "btn.promo": "🎟 Промокод",
    "btn.promo_clear": "🧹 Убрать промокод",
    "error.generic": "⚠️ Что-то пошло не так. Попробуйте ещё раз или напишите в поддержку.",
    "error.banned": "🚫 Доступ к боту ограничен.",
    "error.stale": "⌛️ Это сообщение устарело, откройте меню заново.",
    "cancelled": "Отменено.",

    # --- menu ---
    "menu.title": (
        "<b>{shop}</b> — цифровые товары\n\n"
        "💰 Баланс: <b>{balance}</b>\n"
        "Выберите раздел ниже."
    ),
    "menu.catalog": "🛍 Каталог",
    "menu.profile": "👤 Профиль",
    "menu.topup": "💳 Пополнить баланс",
    "menu.orders": "📦 Мои покупки",
    "menu.referral": "🤝 Партнёрам",
    "menu.support": "🆘 Поддержка",
    "menu.language": "🌐 Язык",
    "menu.admin": "⚙️ Админка",

    # --- start ---
    "start.welcome": "👋 Добро пожаловать в <b>{shop}</b>!",
    "start.referred": "🤝 Вы пришли по приглашению — спасибо!",

    # --- catalog ---
    "catalog.title": "🛍 <b>Каталог</b>\n\nВыберите категорию:",
    "catalog.empty": "Каталог пока пуст. Загляните позже 🙂",
    "catalog.category": "{emoji} <b>{title}</b>\n\nВыберите товар:",
    "catalog.category_empty": "В этой категории пока нет товаров.",
    "catalog.card": (
        "{emoji} <b>{title}</b>\n\n"
        "{description}\n\n"
        "💵 Цена: <b>{price}</b> за 1 шт.\n"
        "📦 В наличии: <b>{stock}</b> шт."
    ),
    "catalog.tiers": "\n\n📉 <b>Оптовые цены:</b>\n{rows}",
    "catalog.tier_row": "• от {qty} шт. — {price}/шт.",
    "catalog.sold_out": "\n\n❌ <b>Нет в наличии</b>",
    "catalog.ask_quantity": (
        "{title}\n\n"
        "Введите количество (1–{max}) числом.\n"
        "Доступно: <b>{stock}</b> шт."
    ),

    # --- purchase ---
    "order.confirm": (
        "🧾 <b>Подтверждение заказа</b>\n\n"
        "Товар: <b>{title}</b>\n"
        "Количество: <b>{quantity}</b> шт.\n"
        "Цена за шт.: <b>{unit}</b>\n"
        "{promo_line}"
        "Итого: <b>{total}</b>\n\n"
        "💰 Баланс: {balance}"
    ),
    "order.promo_line": "Промокод <code>{code}</code> (−{percent}%): −{discount}\n",
    "order.success": (
        "✅ <b>Заказ #{order_id} оплачен</b>\n\n"
        "Товар: <b>{title}</b> × {quantity}\n"
        "Списано: <b>{total}</b>\n"
        "💰 Остаток: <b>{balance}</b>"
    ),
    "order.goods": "🎁 <b>Ваш товар:</b>\n\n{payloads}",
    "order.goods_file": "🎁 Товар во вложении ({quantity} шт.).",
    "order.insufficient": (
        "❌ Недостаточно средств.\n\nНе хватает: <b>{missing}</b>\n"
        "Пополните баланс и повторите."
    ),
    "order.out_of_stock": "❌ Не хватает товара на складе. Доступно: <b>{available}</b> шт.",
    "order.invalid_quantity": "❌ Некорректное количество.",
    "order.unavailable": "❌ Товар сейчас недоступен.",
    "orders.title": "📦 <b>Мои покупки</b>",
    "orders.empty": "Вы ещё ничего не покупали.",
    "orders.row": "#{order_id} — {title} × {quantity} — {total} ({date})",

    # --- promo ---
    "promo.ask": "🎟 Введите промокод:",
    "promo.applied": "✅ Промокод <code>{code}</code> применён: −{percent}%",
    "promo.cleared": "Промокод убран.",
    "promo.not_found": "❌ Промокод не найден.",
    "promo.expired": "❌ Срок действия промокода истёк.",
    "promo.exhausted": "❌ Промокод исчерпан.",
    "promo.already_used": "❌ Вы уже использовали этот промокод.",
    "promo.invalid": "❌ Промокод недоступен.",

    # --- balance ---
    "balance.title": (
        "💳 <b>Пополнение баланса</b>\n\n"
        "Текущий баланс: <b>{balance}</b>\n"
        "Минимум: {min} · Максимум: {max}\n\n"
        "Введите сумму:"
    ),
    "balance.bad_amount": "❌ Введите сумму числом, например <code>500</code>.",
    "balance.out_of_range": "❌ Сумма должна быть от {min} до {max}.",
    "balance.invoice": (
        "🧾 Счёт на <b>{amount}</b> создан.\n\n"
        "Оплатите по кнопке ниже, средства зачислятся автоматически.\n"
        "Счёт действует {ttl} мин."
    ),
    "balance.still_pending": "⏳ Оплата ещё не поступила.",
    "balance.credited": (
        "✅ Баланс пополнен на <b>{amount}</b>.\n💰 Текущий баланс: <b>{balance}</b>"
    ),
    "balance.disabled": "💳 Онлайн-оплата временно недоступна. Напишите в поддержку: {support}",
    "balance.referral_bonus": "🤝 Реферальный бонус: <b>{amount}</b> за пополнение {user}.",

    # --- profile ---
    "profile.card": (
        "👤 <b>Профиль</b>\n\n"
        "ID: <code>{id}</code>\n"
        "💰 Баланс: <b>{balance}</b>\n"
        "🧾 Покупок: <b>{orders}</b>\n"
        "💸 Потрачено: <b>{spent}</b>\n"
        "🤝 Рефералов: <b>{referrals}</b>"
    ),
    "profile.history": "\n\n<b>Последние операции:</b>\n{rows}",
    "profile.history_row": "{sign}{amount} — {kind}",

    # --- referral ---
    "referral.card": (
        "🤝 <b>Партнёрская программа</b>\n\n"
        "Вы получаете <b>{percent}%</b> с каждого пополнения приглашённых.\n\n"
        "Приглашено: <b>{count}</b>\n"
        "Ваша ссылка:\n<code>{link}</code>"
    ),

    # --- support / language ---
    "support.card": "🆘 <b>Поддержка</b>\n\n{links}",
    "support.none": "Контакты поддержки пока не настроены.",
    "language.choose": "🌐 Выберите язык / Choose language:",
    "language.changed": "✅ Язык изменён.",

    # --- admin ---
    "admin.menu": "⚙️ <b>Админка</b>",
    "admin.denied": "🚫 Недостаточно прав.",
    "admin.stats": (
        "📊 <b>Статистика</b>\n\n"
        "👥 Пользователей: <b>{users}</b> (забанено {banned})\n"
        "🧾 Заказов: <b>{orders}</b>\n"
        "💵 Выручка: <b>{revenue}</b>\n"
        "💰 На балансах: <b>{balances}</b>"
    ),
    "admin.btn.stats": "📊 Статистика",
    "admin.btn.stock": "📥 Залить товар",
    "admin.btn.products": "🏷 Товары",
    "admin.btn.balance": "💰 Баланс юзеру",
    "admin.btn.promo": "🎟 Промокод",
    "admin.btn.broadcast": "📢 Рассылка",
    "admin.stock.choose": "Выберите товар для загрузки:",
    "admin.stock.ask": (
        "📥 Пришлите позиции для <b>{title}</b>: текстом (по одной в строке) "
        "или файлом .txt"
    ),
    "admin.stock.done": (
        "✅ Загружено: <b>{added}</b>\n"
        "♻️ Дубликатов пропущено: {duplicates}\n"
        "📦 Всего в наличии: <b>{stock}</b>"
    ),
    "admin.products.list": "🏷 <b>Товары</b>",
    "admin.products.row": "#{id} {title} — {price} — {stock} шт. {state}",
    "admin.balance.ask_user": "Введите ID или @username пользователя:",
    "admin.balance.ask_amount": (
        "Пользователь: {user} (баланс {balance})\n\n"
        "Введите сумму: положительную для начисления, отрицательную для списания."
    ),
    "admin.balance.done": "✅ Готово. Новый баланс {user}: <b>{balance}</b>",
    "admin.balance.no_user": "❌ Пользователь не найден.",
    "admin.balance.negative": "❌ Баланс не может уйти в минус. Не хватает {missing}.",
    "admin.promo.ask": (
        "Введите промокод в формате:\n"
        "<code>КОД ПРОЦЕНТ [макс_использований] [лимит_на_юзера]</code>\n\n"
        "Пример: <code>WELCOME 10 100 1</code>"
    ),
    "admin.promo.done": "✅ Промокод <code>{code}</code> на −{percent}% создан.",
    "admin.promo.bad": "❌ Неверный формат.",
    "admin.broadcast.ask": "📢 Пришлите сообщение для рассылки:",
    "admin.broadcast.started": "📢 Рассылка запущена на {count} получателей.",
    "admin.broadcast.done": "✅ Рассылка завершена.\nДоставлено: {sent}\nОшибок: {failed}",
    "admin.notify.order": (
        "🧾 Заказ #{order_id}\n"
        "{user} купил {title} × {quantity} на {total}"
    ),
    "admin.notify.topup": "💳 {user} пополнил баланс на {amount}",
}
