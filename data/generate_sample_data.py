"""Generates the SYNTHETIC NovaCart demo datasets (deterministic, seed 42).

NovaCart is a FICTIONAL e-commerce application. Every record below is invented for demonstration -
none of it is real customer feedback. Records carry ``is_synthetic=True`` and ``data_origin=synthetic_demo``.

The data intentionally contains these business blind spots:
  * refunds           - many, rapidly rising complaints (spike mid-October); company barely mentions refunds
  * customer support  - rising complaints about unreachable humans; company only uses vague 'we're here for you'
  * delivery delays   - rising, while the company PROMISES 'lightning-fast delivery' (covered but contradicted)
  * payment failures  - small but emerging in October; almost no company mention
  * discounts/features- heavily promoted, customers mostly positive / low priority (misplaced emphasis)
  * app performance   - complaints early on, fading later (a declining issue, NOT a blind spot)
Run:  python data/generate_sample_data.py
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parent
START = datetime(2026, 8, 3)  # Monday of week 0; data spans 13 weeks to 2026-11-01
SEED = 42

# --------------------------------------------------------------------------- customer text pools
REFUNDS = [
    "I've been waiting three days for a refund and nobody can tell me where my money is.",
    "Refund still not credited after 12 days. Support keeps saying it is 'being processed'.",
    "Returned the item two weeks ago, still no refund. This is unacceptable.",
    "The refund process is a nightmare. Every step needs another form and another wait.",
    "Why does a refund take 10 working days when the payment took 2 seconds?",
    "Got the refund email but the money never reached my account. Been over a week now.",
    "Refund rejected without any explanation. I returned the product in its original packaging.",
    "I was promised my refund in 5 days. It's been 15. Still nothing.",
    "Cancelled my order the same day and the refund still hasn't shown up after a week.",
    "Partial refund only. Nobody explains why they kept part of my money.",
    "Requested a refund for a damaged item, they asked for photos three separate times and still no money back.",
    "Refund status in the app just says 'pending' for 9 days. No updates, no timeline.",
    "I only wanted my money back and it has turned into a month long ordeal.",
    "Refund went to store credit even though I asked for the original payment method. Not what I agreed to.",
    "The product was great but the refund for my second order took forever. Really put me off.",
    "App is smooth and easy to use, but refunds take far too long.",
    "Love the prices, hate the refund experience. Two weeks and counting.",
    "Still waiting on my refund. Opened a ticket last week, nothing.",
    "No way to track my refund anywhere. I have to guess when it will arrive.",
    "Refund promised in 3-5 business days, actual wait was 18 days. Misleading.",
    "Money deducted for a cancelled order and not returned. Third time this has happened.",
    "Disappointed with how slow NovaCart is at refunding. Other shops do it in a day.",
    "Waited 11 days for a refund of 24 dollars. Ridiculous.",
    "They refunded the item but not the delivery fee that I paid for a failed delivery.",
    "My refund request was closed automatically without being resolved. Had to start over.",
    "It takes forever to get your money back here. Think twice before ordering.",
    "Refund timeline is not clear anywhere on the site. Every agent gives a different answer.",
    "Waiting for a refund for 20 days now. Escalated twice and nothing has changed.",
    "Cancelled order, refund credited fine within two days. Happy with that one.",
    "Refund arrived quicker than I expected this time, thanks.",
]
SUPPORT = [
    "Nobody responds when I raise a support ticket. Three tickets, zero replies.",
    "The automated chatbot never solves anything. I just want to speak to a real person.",
    "It takes forever to speak to an actual human. The bot sends you in circles.",
    "Customer support took 6 days to reply to a simple question.",
    "There is no phone number anywhere. How do I reach someone when the app does not help?",
    "Support agents copy paste the same answer and close the ticket without reading it.",
    "Waited 40 minutes in live chat and got disconnected. Terrible customer service.",
    "Support promised a callback and never called. Typical.",
    "Every time I contact support I have to explain my issue from scratch to a new agent.",
    "Chat support is only available during office hours which is useless for people who work.",
    "The support team was polite but could not actually fix anything.",
    "I escalated my complaint and got an automated 'we value your feedback' email. That is all.",
    "Please give us a way to reach a human agent without going through five bot menus.",
    "Support ticket closed as 'resolved' when my problem was not resolved at all.",
    "Great product, awful customer care. Replies take days and nobody owns the problem.",
    "Customer service has gotten much worse recently. Used to get answers within a day.",
    "Email support never answered me. Social media DM finally got a reply after a week.",
    "I need faster support when an order goes wrong. Waiting days is not acceptable.",
    "The support chatbot does not understand simple questions like 'where is my refund'.",
    "Agent was helpful and solved my issue in ten minutes. Good experience for once.",
    "Support is slow but at least this agent was friendly and apologised.",
    "Why is it so hard to contact NovaCart? I have been looking for a support number for an hour.",
]
DELIVERY = [
    "My order was supposed to arrive in 2 days and it took 9. So much for fast delivery.",
    "Delivery delayed again. Tracking has shown 'out for delivery' for three days.",
    "Package marked delivered but I never received it. Support has not helped.",
    "Delivery partner never called and the parcel was returned to the warehouse.",
    "Ordered before a deadline and it arrived a week late. Completely useless to me now.",
    "Second delayed order in a month. The delivery promise on the website is not true.",
    "The estimated delivery date keeps changing every day. Now it says next week.",
    "Fast delivery? Mine took 11 days and there was no update from the company.",
    "Delivery was on time and the packaging was neat. Happy with this order.",
    "Courier left my parcel outside in the rain and the box was soaked.",
    "Order stuck at the sorting centre for 6 days with no explanation.",
    "Delivery slots are never respected. I stayed home all day and nobody came.",
    "Express delivery cost extra and arrived no faster than standard shipping.",
    "Items from the same order arrived on different days, two weeks apart.",
    "My delivery got delayed because of a wrong address that I never entered.",
    "Delivery experience is getting worse every month. Used to arrive in two days.",
    "Free delivery sounds great but it takes ages. I would rather pay for quicker shipping.",
    "Tracking shows no movement for 5 days. When will my order actually move?",
    "Parcel arrived 8 days late, but at least the product was fine.",
    "Delivery was quick this time, arrived the next day. Nice.",
]
APP_PERF = [
    "The app keeps crashing when I open my cart. Very frustrating.",
    "App is really slow on my phone, pages take ages to load.",
    "Search is laggy and freezes after typing a few letters.",
    "App performance dropped after the last update. Checkout screen hangs.",
    "The app crashes every time I try to apply a coupon code.",
    "Pages load slowly during evenings, sometimes I get a blank screen.",
    "Battery drain from this app is crazy. It runs hot when browsing.",
    "Latest update fixed the crashes. App is much faster now, thank you.",
    "Loads quickly and runs smoothly on my old phone. Impressed.",
    "Images take forever to load on mobile data.",
]
QUALITY = [
    "The product quality is much worse than the photos suggested.",
    "Received the wrong item, ordered a blue jacket and got a grey one.",
    "The headphones stopped working after two weeks. Poor quality.",
    "Stitching on the bag came apart on the first use. Cheap material.",
    "Item arrived with a cracked screen protector and scratches.",
    "Excellent quality for the price, exactly as described.",
    "The shoes are comfortable and the material feels premium. Very happy.",
    "Sizes run smaller than the size chart says. Had to return.",
]
PRICING = [
    "Great discounts this festive season, saved a lot on my electronics order.",
    "Prices are lower than other apps and the coupons actually work.",
    "The sale prices are good but some of the discounts seem inflated.",
    "Loved the flash sale, got a really good deal on kitchen items.",
    "Coupon codes are easy to apply and the savings are real.",
    "Good prices overall. Nothing special but I keep coming back for the offers.",
    "The 'up to 70% off' banner is misleading, most items are 10 to 15 percent off.",
    "Decent discounts but I care more about getting my orders on time.",
    "Price is fine. I just wish delivery and support were as good as the discounts.",
    "Bank offer discount did not apply at checkout even though the banner said it would.",
    "Cheaper than the local shops, saved around 20 dollars.",
    "Reasonable pricing and a good range of products.",
]
UX = [
    "Please add a dark mode option, the white screen hurts my eyes at night.",
    "Would love a wishlist that notifies me when prices drop.",
    "The app is easy to use and the checkout is simple. Nicely designed.",
    "Can you add live order tracking on a map? Right now it is just text updates.",
    "Please add a way to compare two products side by side.",
    "Navigation is clean and I can find things quickly. Good job.",
    "It would be great to have voice search in the app.",
    "I wish the app allowed saving multiple delivery addresses with labels.",
    "Filters are limited. Add a filter for brand and customer rating please.",
    "Love the clean layout. The product pages are clear and readable.",
    "Please let us edit an order before it ships. Right now we have to cancel and reorder.",
    "App design looks good but the notifications are too frequent and spammy.",
]
PAYMENTS = [
    "Payment failed but the money was deducted from my account. Still no reversal.",
    "I was charged twice for the same order. Waiting for the duplicate charge to be returned.",
    "UPI payments keep failing at checkout, card works only after three tries.",
    "My card got declined on NovaCart but works everywhere else. Payment page is unreliable.",
    "Payment went through but the order shows as failed. Money gone and no order.",
    "Checkout payment timed out twice and I was billed both times.",
]
RETURNS = [
    "Return pickup was scheduled three times and the agent never showed up.",
    "The return window is too short. Seven days is not enough for gifts.",
    "Returning an item is easy in the app, pickup happened the next day. Smooth.",
    "I had to ship the return myself and pay for it even though the item was faulty.",
    "Exchange request got cancelled automatically, had to place a new order at a higher price.",
    "Return policy is confusing. Different pages say different things.",
]
LOYALTY = [
    "NovaCart Plus points are nice, redeemed them for a decent discount.",
    "The rewards programme is okay. Would like more ways to earn points.",
    "Loyalty points expired without any warning email. Lost 400 points.",
    "Using Plus membership for early access to sales. Worth it so far.",
]

# multi-aspect reviews (positive on one aspect, negative on another) - demonstrate aspect-based sentiment
MIXED = [
    ("App is fast and checkout is smooth, but refunds take way too long.", "refunds"),
    ("Great prices and lots of discounts, but customer support never replies to my tickets.", "support"),
    ("Product quality is good, but the delivery was nearly a week late.", "delivery"),
    ("I love the design of the app but my payment failed and I was charged anyway.", "payments"),
    ("The discounts are great, but getting a refund is painful and slow.", "refunds"),
    ("Easy to browse and order, however the chatbot cannot connect me to a real person.", "support"),
]

WEEK_WEIGHTS = {
    "refunds":  [1, 1, 1, 1, 1, 2, 2, 3, 3, 4, 8, 6, 5],
    "support":  [1, 1, 1, 1, 2, 2, 3, 4, 5, 6, 7, 7, 6],
    "delivery": [1, 1, 1, 2, 2, 3, 3, 4, 5, 5, 6, 6, 5],
    "app_perf": [5, 5, 4, 3, 2, 1, 1, 0.3, 0.3, 1, 0.2, 0.2, 0.2],
    "quality":  [2] * 13,
    "pricing":  [2, 2, 2, 2, 2, 2, 2, 2, 2, 4, 4, 3, 2],
    "ux":       [2] * 13,
    "payments": [0, 0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 3, 3],
    "returns":  [1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 3, 3, 3],
    "loyalty":  [1] * 13,
}
SOURCES = ["Play Store review", "App Store review", "Twitter/X post", "Reddit r/novacart_users", "Trustpilot review",
           "Support survey", "Email feedback"]
SOURCE_BY_TOPIC_BIAS = {"support": ["Twitter/X post", "Trustpilot review", "Email feedback", "Reddit r/novacart_users"],
                        "refunds": ["Twitter/X post", "Trustpilot review", "Play Store review", "Reddit r/novacart_users"]}


def _pick_date(rng: random.Random, weights: list[float]) -> datetime:
    week = rng.choices(range(13), weights=weights)[0]
    return START + timedelta(days=week * 7 + rng.randint(0, 6), hours=rng.randint(7, 23), minutes=rng.randint(0, 59))


def build_customer(rng: random.Random) -> pd.DataFrame:
    pools = {"refunds": REFUNDS, "support": SUPPORT, "delivery": DELIVERY, "app_perf": APP_PERF, "quality": QUALITY,
             "pricing": PRICING, "ux": UX, "payments": PAYMENTS, "returns": RETURNS, "loyalty": LOYALTY}
    rows = []
    heavy_users = [f"CUST-{i:04d}" for i in range(1, 9)]  # repeat complainers -> recurring frustrations
    uid = 100
    for topic, texts in pools.items():
        for t in texts:
            if topic in ("refunds", "support", "delivery") and rng.random() < 0.18:
                cid = rng.choice(heavy_users)
            else:
                uid += 1
                cid = f"CUST-{uid:04d}"
            src = rng.choice(SOURCE_BY_TOPIC_BIAS.get(topic, SOURCES))
            rows.append((t, src, _pick_date(rng, WEEK_WEIGHTS[topic]), topic, cid))
    for t, topic in MIXED:
        uid += 1
        rows.append((t, rng.choice(SOURCES), _pick_date(rng, WEEK_WEIGHTS[{"refunds": "refunds", "support": "support", "delivery": "delivery", "payments": "payments"}[topic]]), topic, f"CUST-{uid:04d}"))
    df = pd.DataFrame(rows, columns=["text", "source", "date", "category", "customer_id"])
    df["rating"] = None
    df["is_synthetic"] = True
    df["data_origin"] = "synthetic_demo"
    # 'category' holds the generator's intent label. We keep a neutral public label so the NLP
    # pipeline still has to DISCOVER topics itself rather than read them from a column.
    df["generator_label"] = df["category"]
    df["category"] = "customer_feedback"
    df = df.sort_values("date").reset_index(drop=True)
    df["date"] = df["date"].dt.strftime("%Y-%m-%d %H:%M")
    return df


COMPANY = [
    # discounts & offers (heavily promoted)
    ("NovaCart Mega Festive Sale: up to 70% off on electronics, fashion and home. Shop now!", "Twitter/X post", "2026-08-05", "social_post"),
    ("Flat 20% off your first order with code WELCOME20. Download the NovaCart app today.", "Advertisement", "2026-08-08", "advertisement"),
    ("Weekend Flash Deals are live! Grab the best prices on top brands before they are gone.", "Instagram post", "2026-08-15", "social_post"),
    ("Save more with bank offers: extra 10% instant discount on selected cards this month.", "Website banner", "2026-08-22", "website"),
    ("Back to School Sale: unbeatable prices on laptops, backpacks and stationery.", "Advertisement", "2026-08-28", "advertisement"),
    ("Big Savings Days are here. Free coupons for every shopper, every day.", "Email newsletter", "2026-09-03", "newsletter"),
    ("Festive Season Preview: early-bird discounts for NovaCart Plus members.", "Website banner", "2026-09-18", "website"),
    ("Biggest Diwali Sale ever! Deals so good you will want to share them.", "Advertisement", "2026-10-02", "advertisement"),
    ("Price drop alert: thousands of products now at their lowest price this year.", "Twitter/X post", "2026-10-09", "social_post"),
    ("Grab bonus cashback on every festive order placed this week.", "Instagram post", "2026-10-14", "social_post"),
    ("Mega Clearance: save big on last season's fashion with deals up to 60% off.", "Advertisement", "2026-10-24", "advertisement"),
    # product features / catalogue
    ("Discover over 5 million products across 40 categories, all in one app.", "Website", "2026-08-02", "website"),
    ("Introducing AI-powered recommendations that learn what you love.", "Company announcement", "2026-08-12", "announcement"),
    ("New in the app: personalised home feed and smarter search filters.", "Product update", "2026-08-25", "announcement"),
    ("Explore our new Home & Kitchen store with 10,000 new products.", "Company announcement", "2026-09-09", "announcement"),
    ("NovaCart now features premium brands from over 500 verified sellers.", "Website", "2026-09-14", "website"),
    ("Try our new Visual Search: snap a photo and find similar products instantly.", "Product update", "2026-09-26", "announcement"),
    ("Our all-new fashion catalogue brings the latest trends to your screen.", "Instagram post", "2026-10-06", "social_post"),
    ("Wishlist, price alerts and curated collections: everything you need to shop smarter.", "Website", "2026-10-17", "website"),
    # performance / app speed
    ("Faster, smoother, better: the new NovaCart app loads twice as fast.", "Company announcement", "2026-08-18", "announcement"),
    ("Version 5.2 brings blazing-fast checkout and a lighter app size.", "Product update", "2026-09-01", "announcement"),
    ("Experience lightning-quick browsing even on slow networks.", "Advertisement", "2026-09-20", "advertisement"),
    ("Our engineers rebuilt the cart for rock-solid stability.", "Blog post", "2026-09-28", "blog"),
    # delivery promise
    ("Lightning-fast delivery on millions of products, straight to your doorstep.", "Advertisement", "2026-08-10", "advertisement"),
    ("Order today, get it in 2 days with NovaCart Express.", "Website banner", "2026-09-05", "website"),
    ("Free delivery on orders above 499, because great shopping should never cost extra.", "Website", "2026-10-01", "website"),
    # loyalty
    ("Join NovaCart Plus for free delivery, early sale access and bonus reward points.", "Website", "2026-08-20", "website"),
    ("Earn points on every purchase and unlock exclusive member perks.", "Email newsletter", "2026-09-12", "newsletter"),
    ("Plus members get first access to the Diwali sale. Join today.", "Email newsletter", "2026-09-29", "newsletter"),
    # support / refunds / payments: barely mentioned or vague
    ("We are always here for you, wherever you shop.", "Website", "2026-08-30", "website"),
    ("Hassle-free returns on eligible items.", "Website", "2026-09-22", "website"),
    ("Your trust matters. Shop with confidence on NovaCart.", "Website", "2026-10-12", "website"),
    ("Secure checkout with multiple payment options including UPI, cards and wallets.", "Website", "2026-09-07", "website"),
    ("Our customer happiness team keeps working to improve your experience.", "Blog post", "2026-10-20", "blog"),
]


def build_company() -> pd.DataFrame:
    df = pd.DataFrame(COMPANY, columns=["text", "source", "date", "category"])
    df["customer_id"] = None
    df["rating"] = None
    df["is_synthetic"] = True
    df["data_origin"] = "synthetic_demo"
    return df


if __name__ == "__main__":
    rng = random.Random(SEED)
    cust = build_customer(rng)
    comp = build_company()
    cust.to_csv(OUT / "sample_customer_data.csv", index=False)
    comp.to_csv(OUT / "sample_company_data.csv", index=False)
    print(f"customer records: {len(cust)} | company records: {len(comp)}")
