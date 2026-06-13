# Catbox Image Bot

Channel mein jo bhi photo post ya forward hogi, bot us image ko **catbox.moe** par
upload karke original post edit kar deta hai aur link caption mein laga deta hai.

---

## Setup

### 1. Bot Token lo
- [@BotFather](https://t.me/BotFather) se naya bot banao
- Token copy karo

### 2. Bot ko Channel Admin banao
- Apne channel mein bot ko add karo
- **Admin** bana do — sirf **Edit Messages** permission kaafi hai

### 3. Environment Variable set karo
```
BOT_TOKEN=123456:ABCdef...
CATBOX_USERHASH=          # optional – catbox.moe account hash for permanent storage
```

### 4. Install & Run (local)
```bash
pip install -r requirements.txt
BOT_TOKEN="your_token" python bot.py
```

### 5. Render par deploy karna ho to
- `Start Command`: `python bot.py`
- Environment Variables mein `BOT_TOKEN` add karo
- Python version: **3.11** pin karo (`runtime.txt` mein `python-3.11.9` likh do)

---

## Kaise kaam karta hai

1. Channel mein koi bhi photo post hoti hai (direct ya forward)
2. Bot photo download karta hai
3. Catbox.moe par upload karta hai (anonymous ya account-linked)
4. Original post ka caption edit karke catbox link laga deta hai

---

## runtime.txt (Render ke liye)
```
python-3.11.9
```
