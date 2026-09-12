TEXTS: dict[str, str] = {
    # --- common ---
    "btn.back": "◀️ Back",
    "btn.cancel": "✖️ Cancel",
    "btn.menu": "🏠 Menu",
    "btn.pay": "💳 Pay",
    "btn.check": "🔄 Check payment",
    "btn.confirm": "✅ Confirm",
    "btn.buy": "🛒 Buy",
    "btn.promo": "🎟 Promo code",
    "btn.promo_clear": "🧹 Remove promo",
    "error.generic": "⚠️ Something went wrong. Try again or contact support.",
    "error.banned": "🚫 Access to this bot is restricted.",
    "error.stale": "⌛️ This message is outdated, please reopen the menu.",
    "cancelled": "Cancelled.",

    # --- menu ---
    "menu.title": (
        "<b>{shop}</b> — digital goods\n\n"
        "💰 Balance: <b>{balance}</b>\n"
        "Pick a section below."
    ),
    "menu.catalog": "🛍 Catalogue",
    "menu.profile": "👤 Profile",
    "menu.topup": "💳 Top up",
    "menu.orders": "📦 My purchases",
    "menu.referral": "🤝 Affiliates",
    "menu.support": "🆘 Support",
    "menu.language": "🌐 Language",
    "menu.admin": "⚙️ Admin",

    # --- start ---
    "start.welcome": "👋 Welcome to <b>{shop}</b>!",
    "start.referred": "🤝 You joined via an invite — thanks!",

    # --- catalog ---
    "catalog.title": "🛍 <b>Catalogue</b>\n\nChoose a category:",
    "catalog.empty": "The catalogue is empty for now. Check back later 🙂",
    "catalog.category": "{emoji} <b>{title}</b>\n\nChoose an item:",
    "catalog.category_empty": "No items in this category yet.",
    "catalog.card": (
        "{emoji} <b>{title}</b>\n\n"
        "{description}\n\n"
        "💵 Price: <b>{price}</b> per unit\n"
        "📦 In stock: <b>{stock}</b> pcs"
    ),
    "catalog.tiers": "\n\n📉 <b>Bulk prices:</b>\n{rows}",
    "catalog.tier_row": "• {qty}+ pcs — {price}/unit",
    "catalog.sold_out": "\n\n❌ <b>Out of stock</b>",
    "catalog.ask_quantity": (
        "{title}\n\n"
        "Enter the quantity (1–{max}) as a number.\n"
        "Available: <b>{stock}</b> pcs"
    ),

    # --- purchase ---
    "order.confirm": (
        "🧾 <b>Order confirmation</b>\n\n"
        "Item: <b>{title}</b>\n"
        "Quantity: <b>{quantity}</b> pcs\n"
        "Unit price: <b>{unit}</b>\n"
        "{promo_line}"
        "Total: <b>{total}</b>\n\n"
        "💰 Balance: {balance}"
    ),
    "order.promo_line": "Promo <code>{code}</code> (−{percent}%): −{discount}\n",
    "order.success": (
        "✅ <b>Order #{order_id} paid</b>\n\n"
        "Item: <b>{title}</b> × {quantity}\n"
        "Charged: <b>{total}</b>\n"
        "💰 Balance left: <b>{balance}</b>"
    ),
    "order.goods": "🎁 <b>Your goods:</b>\n\n{payloads}",
    "order.goods_file": "🎁 Your goods are attached ({quantity} pcs).",
    "order.insufficient": (
        "❌ Not enough funds.\n\nMissing: <b>{missing}</b>\n"
        "Top up your balance and try again."
    ),
    "order.out_of_stock": "❌ Not enough stock. Available: <b>{available}</b> pcs.",
    "order.invalid_quantity": "❌ Invalid quantity.",
    "order.unavailable": "❌ This item is currently unavailable.",
    "orders.title": "📦 <b>My purchases</b>",
    "orders.empty": "You haven't bought anything yet.",
    "orders.row": "#{order_id} — {title} × {quantity} — {total} ({date})",

    # --- promo ---
    "promo.ask": "🎟 Enter a promo code:",
    "promo.applied": "✅ Promo <code>{code}</code> applied: −{percent}%",
    "promo.cleared": "Promo code removed.",
    "promo.not_found": "❌ Promo code not found.",
    "promo.expired": "❌ This promo code has expired.",
    "promo.exhausted": "❌ This promo code is used up.",
    "promo.already_used": "❌ You have already used this promo code.",
    "promo.invalid": "❌ Promo code unavailable.",

    # --- balance ---
    "balance.title": (
        "💳 <b>Top up balance</b>\n\n"
        "Current balance: <b>{balance}</b>\n"
        "Min: {min} · Max: {max}\n\n"
        "Enter an amount:"
    ),
    "balance.bad_amount": "❌ Enter the amount as a number, e.g. <code>500</code>.",
    "balance.out_of_range": "❌ The amount must be between {min} and {max}.",
    "balance.invoice": (
        "🧾 Invoice for <b>{amount}</b> created.\n\n"
        "Pay via the button below — funds are credited automatically.\n"
        "The invoice is valid for {ttl} min."
    ),
    "balance.still_pending": "⏳ Payment hasn't arrived yet.",
    "balance.credited": (
        "✅ Balance topped up by <b>{amount}</b>.\n💰 Current balance: <b>{balance}</b>"
    ),
    "balance.disabled": (
        "💳 Online payments are temporarily unavailable. Contact support: {support}"
    ),
    "balance.referral_bonus": "🤝 Referral bonus: <b>{amount}</b> from {user}'s top-up.",

    # --- profile ---
    "profile.card": (
        "👤 <b>Profile</b>\n\n"
        "ID: <code>{id}</code>\n"
        "💰 Balance: <b>{balance}</b>\n"
        "🧾 Orders: <b>{orders}</b>\n"
        "💸 Spent: <b>{spent}</b>\n"
        "🤝 Referrals: <b>{referrals}</b>"
    ),
    "profile.history": "\n\n<b>Recent activity:</b>\n{rows}",
    "profile.history_row": "{sign}{amount} — {kind}",

    # --- referral ---
    "referral.card": (
        "🤝 <b>Affiliate programme</b>\n\n"
        "You earn <b>{percent}%</b> of every top-up made by people you invite.\n\n"
        "Invited: <b>{count}</b>\n"
        "Your link:\n<code>{link}</code>"
    ),

    # --- support / language ---
    "support.card": "🆘 <b>Support</b>\n\n{links}",
    "support.none": "Support contacts are not configured yet.",
    "language.choose": "🌐 Выберите язык / Choose language:",
    "language.changed": "✅ Language updated.",

    # --- manual transfers ---
    "btn.paid": "✅ I have paid",
    "btn.approve": "✅ Approve",
    "btn.reject": "❌ Reject",
    "btn.method_crypto": "🤖 Crypto (CryptoBot)",
    "btn.method_manual": "🏦 Bank transfer",
    "balance.method": (
        "💳 <b>Top up balance</b>\n\n"
        "Current balance: <b>{balance}</b>\n\n"
        "Choose a payment method:"
    ),
    "balance.no_methods": "💳 Top-ups are temporarily unavailable. Contact support: {support}",
    "manual.ask_amount": (
        "🏦 <b>Bank transfer</b>\n\n"
        "Min: {min} · Max: {max}\n\n"
        "Enter the amount to top up:"
    ),
    "manual.instructions": (
        "🏦 <b>Request for {amount}</b>\n\n"
        "Transfer the exact amount to these details:\n\n"
        "{requisites}\n\n"
        "🔖 Reference: <code>{reference}</code>\n"
        "Put it in the transfer comment if your bank allows one.\n\n"
        "Once sent, tap \u00abI have paid\u00bb and it goes to review.\n"
        "⏳ The request is valid for {ttl} min."
    ),
    "manual.claimed": (
        "⏳ <b>Request {reference} submitted for review</b>\n\n"
        "Amount: <b>{amount}</b>\n"
        "Your balance is credited as soon as the transfer is confirmed.\n"
        "This usually takes a few minutes."
    ),
    "manual.already_open": (
        "⚠️ You already have an open request {reference} for <b>{amount}</b>.\n"
        "Finish or cancel it before starting a new one."
    ),
    "manual.under_review": "⏳ Request {reference} is already under review. Please wait.",
    "manual.cancelled": "Request cancelled.",
    "manual.approved": (
        "✅ <b>Request {reference} approved</b>\n\n"
        "Credited: <b>{amount}</b>\n"
        "💰 Balance: <b>{balance}</b>"
    ),
    "manual.rejected": (
        "❌ <b>Request {reference} rejected</b>\n\n"
        "No transfer of <b>{amount}</b> was found. If you are sure you paid, "
        "contact support with the receipt: {support}"
    ),
    "manual.unavailable": "🏦 Bank details are not configured yet. Contact support: {support}",
    "admin.btn.requests": "🧾 Requests",
    "admin.btn.requisites": "🏦 Bank details",
    "admin.requests.title": "🧾 <b>Requests under review</b>",
    "admin.requests.empty": "No requests waiting for review.",
    "admin.requests.card": (
        "🧾 <b>Request {reference}</b>\n\n"
        "Customer: {user} (<code>{user_id}</code>)\n"
        "Amount: <b>{amount}</b>\n"
        "Submitted: {submitted}"
    ),
    "admin.requests.row": "{reference} · {amount} · {user}",
    "admin.requests.approved": (
        "✅ Request {reference} approved. Balance of {user}: <b>{balance}</b>"
    ),
    "admin.requests.rejected": "❌ Request {reference} rejected.",
    "admin.requests.gone": "⚠️ This request has already been handled.",
    "admin.requisites.current": (
        "🏦 <b>Bank details for transfers</b>\n\n"
        "{requisites}\n\n"
        "Send new text to replace them."
    ),
    "admin.requisites.empty": "No bank details set. Send the text customers should see.",
    "admin.requisites.saved": "✅ Bank details updated.",
    "admin.notify.review": (
        "🧾 <b>New request {reference}</b>\n\n"
        "Customer: {user} (<code>{user_id}</code>)\n"
        "Amount: <b>{amount}</b>\n\n"
        "Check the incoming transfer and approve."
    ),

    # --- admin ---
    "admin.menu": "⚙️ <b>Admin panel</b>",
    "admin.denied": "🚫 Not enough permissions.",
    "admin.stats": (
        "📊 <b>Statistics</b>\n\n"
        "👥 Users: <b>{users}</b> (banned {banned})\n"
        "🧾 Orders: <b>{orders}</b>\n"
        "💵 Revenue: <b>{revenue}</b>\n"
        "💰 Held in balances: <b>{balances}</b>"
    ),
    "admin.btn.stats": "📊 Statistics",
    "admin.btn.stock": "📥 Upload stock",
    "admin.btn.products": "🏷 Products",
    "admin.btn.balance": "💰 Adjust balance",
    "admin.btn.promo": "🎟 Promo code",
    "admin.btn.broadcast": "📢 Broadcast",
    "admin.stock.choose": "Choose a product to load stock into:",
    "admin.stock.ask": (
        "📥 Send the items for <b>{title}</b>: as text (one per line) "
        "or as a .txt file"
    ),
    "admin.stock.done": (
        "✅ Added: <b>{added}</b>\n"
        "♻️ Duplicates skipped: {duplicates}\n"
        "📦 Total in stock: <b>{stock}</b>"
    ),
    "admin.products.list": "🏷 <b>Products</b>",
    "admin.products.row": "#{id} {title} — {price} — {stock} pcs {state}",
    "admin.balance.ask_user": "Enter the user's ID or @username:",
    "admin.balance.ask_amount": (
        "User: {user} (balance {balance})\n\n"
        "Enter an amount: positive to credit, negative to debit."
    ),
    "admin.balance.done": "✅ Done. New balance for {user}: <b>{balance}</b>",
    "admin.balance.no_user": "❌ User not found.",
    "admin.balance.negative": "❌ Balance cannot go negative. Missing {missing}.",
    "admin.promo.ask": (
        "Enter a promo code as:\n"
        "<code>CODE PERCENT [max_uses] [per_user_limit]</code>\n\n"
        "Example: <code>WELCOME 10 100 1</code>"
    ),
    "admin.promo.done": "✅ Promo code <code>{code}</code> for −{percent}% created.",
    "admin.promo.bad": "❌ Invalid format.",
    "admin.broadcast.ask": "📢 Send the message to broadcast:",
    "admin.broadcast.started": "📢 Broadcast started for {count} recipients.",
    "admin.broadcast.done": "✅ Broadcast finished.\nDelivered: {sent}\nFailed: {failed}",
    "admin.notify.order": (
        "🧾 Order #{order_id}\n"
        "{user} bought {title} × {quantity} for {total}"
    ),
    "admin.notify.topup": "💳 {user} topped up {amount}",
}
