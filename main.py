from fastapi import FastAPI
from supabase import create_client
import random, smtplib, os
from email.mime.text import MIMEText
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()
app = FastAPI(title="Redbub-API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# --- CONSTANTS FOR YOUR 2 GREETINGS LOGIC ---
REDBUB_AI_GREETING = "Hello👋, how can I help you"
DEFAULT_OWNER_GREETING = "Thanks for reaching out on us👍. How can we help you"

@app.get("/")
def home():
    return {"message": "Redbub API dey work! OTP + 2 Greetings + Auto-reply ready 🚀"}

# ================= OTP (REAL GMAIL) =================
@app.post("/send-otp")
def send_otp(email: str, full_name: str, phone: str):
    otp = str(random.randint(100000, 999999))
    supabase.table("profiles").upsert({
        "email": email, "full_name": full_name,
        "phone": phone, "otp": otp, "verified": False
    }, on_conflict="email").execute()
    msg = MIMEText(f"Your Redbub OTP is {otp}. E go expire in 5 mins.")
    msg["Subject"] = "Redbub OTP Verification"
    msg["From"] = os.getenv("EMAIL")
    msg["To"] = email
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.getenv("EMAIL"), os.getenv("EMAIL_PASS"))
        server.send_message(msg)
    return {"message": f"REAL OTP {otp} sent to {email}"}

@app.post("/verify-otp")
def verify_otp(email: str, otp: str):
    result = supabase.table("profiles").select("*").eq("email", email).eq("otp", otp).execute()
    if result.data:
        supabase.table("profiles").update({"verified": True}).eq("email", email).execute()
        return {"verified": True, "message": "OTP correct ✅"}
    return {"verified": False, "message": "Wrong OTP ❌"}

# ================= 1. REDBUB AI GREETING =================
# Always Hello👋, how can I help you
@app.get("/ai/welcome")
def ai_welcome():
    return {"type": "redbub_ai", "message": REDBUB_AI_GREETING}

@app.post("/ai/chat")
def ai_chat(message: str):
    return {"reply": f"Redbub AI: You said '{message}'. I dey learn your thrift style!"}

# ================= 2. PROFILE OWNER GREETING (WITH ON/OFF TOGGLE) =================
# Logic:
# If toggle OFF → No auto greeting
# If toggle ON + dem no edit → Default: Thanks for reaching out...
# If toggle ON + dem edit → Use their edited greeting

@app.post("/greeting/set")
def set_greeting(owner_email: str, is_enabled: bool, custom_message: str = None):
    """
    For Flutter toggle:
    is_enabled = true/false (ON/OFF)
    custom_message = null if dem no edit, or "Welcome 🎉 to Azure..." if dem edit
    """
    # Save to Supabase table: greeting_settings
    # Table columns: owner_email (primary), is_enabled (bool), custom_message (text, nullable)
    supabase.table("greeting_settings").upsert({
        "owner_email": owner_email,
        "is_enabled": is_enabled,
        "custom_message": custom_message  # None = use default
    }, on_conflict="owner_email").execute()
    return {"saved": True, "is_enabled": is_enabled, "custom_message": custom_message or DEFAULT_OWNER_GREETING}

@app.get("/greeting/get")
def get_greeting(owner_email: str):
    """To load toggle state for Flutter screen"""
    result = supabase.table("greeting_settings").select("*").eq("owner_email", owner_email).execute()
    if not result.data:
        return {"is_enabled": True, "custom_message": None, "effective_greeting": DEFAULT_OWNER_GREETING}
    row = result.data[0]
    effective = row["custom_message"] if row["custom_message"] else DEFAULT_OWNER_GREETING
    return {"is_enabled": row["is_enabled"], "custom_message": row["custom_message"], "effective_greeting": effective}

@app.post("/messages/start-chat")
def start_chat(customer_email: str, owner_email: str, is_redbub_ai: bool = False):
    """
    When customer opens chat with owner
    is_redbub_ai = True → Return Redbub AI greeting
    is_redbub_ai = False → Check owner toggle logic
    """
    # CASE 1: Redbub AI chat
    if is_redbub_ai:
        greeting = REDBUB_AI_GREETING
        supabase.table("messages").insert({
            "sender_email": "redbub_ai",
            "receiver_email": customer_email,
            "message": greeting,
            "is_auto_reply": True
        }).execute()
        return {"greeted": True, "type": "redbub_ai", "message": greeting}

    # CASE 2: Profile Owner chat
    setting = supabase.table("greeting_settings").select("*").eq("owner_email", owner_email).execute()
    
    if not setting.data:
        # No settings yet → Assume ON + Default
        greeting = DEFAULT_OWNER_GREETING
        should_greet = True
    else:
        row = setting.data[0]
        should_greet = row["is_enabled"]  # OFF = no greeting
        
        if not should_greet:
            return {"greeted": False, "type": "owner", "message": None, "reason": "Toggle OFF"}

        # ON but check if custom or default
        if row["custom_message"] and row["custom_message"].strip() != "":
            greeting = row["custom_message"]  # Use edited: e.g Welcome to Azure...
        else:
            greeting = DEFAULT_OWNER_GREETING  # Default

    # Send greeting message
    if should_greet:
        supabase.table("messages").insert({
            "sender_email": owner_email,
            "receiver_email": customer_email,
            "message": greeting,
            "is_auto_reply": True
        }).execute()
        return {"greeted": True, "type": "owner", "message": greeting}
    
    return {"greeted": False}

# ================= ONLINE STATUS =================
@app.post("/status/set")
def set_status(email: str, is_online: bool):
    supabase.table("user_status").upsert({"email": email, "is_online": is_online}, on_conflict="email").execute()
    return {"email": email, "is_online": is_online}

# ================= AUTO-REPLY + QUICK REPLY =================
@app.post("/messages/send")
def send_message(sender: str, receiver: str, text: str):
    supabase.table("messages").insert({
        "sender_email": sender, "receiver_email": receiver,
        "message": text, "is_auto_reply": False
    }).execute()
    # Check if receiver offline → auto reply with owner greeting logic
    status = supabase.table("user_status").select("*").eq("email", receiver).execute()
    if not status.data or not status.data[0].get("is_online", False):
        # Get receiver's greeting setting
        greet_setting = supabase.table("greeting_settings").select("*").eq("owner_email", receiver).execute()
        if greet_setting.data and not greet_setting.data[0]["is_enabled"]:
            return {"status": "sent, no auto-reply (OFF)"}
        
        auto_text = DEFAULT_OWNER_GREETING
        if greet_setting.data and greet_setting.data[0].get("custom_message"):
            auto_text = greet_setting.data[0]["custom_message"]
            
        supabase.table("messages").insert({
            "sender_email": receiver, "receiver_email": sender,
            "message": auto_text, "is_auto_reply": True
        }).execute()
        return {"status": "sent + auto-reply", "auto_reply": auto_text}
    return {"status": "sent"}

@app.post("/quick-replies/save")
def save_quick_reply(owner_email: str, shortcut: str, reply_text: str):
    supabase.table("quick_replies").upsert({
        "owner_email": owner_email, "shortcut": shortcut, "reply_text": reply_text
    }, on_conflict="owner_email,shortcut").execute()
    return {"message": f"Quick reply /{shortcut} saved ✅"}

@app.post("/quick-replies/use")
def use_quick_reply(owner_email: str, shortcut: str, customer_email: str):
    result = supabase.table("quick_replies").select("*").eq("owner_email", owner_email).eq("shortcut", shortcut).execute()
    if result.data:
        text = result.data[0]["reply_text"]
        supabase.table("messages").insert({
            "sender_email": owner_email, "receiver_email": customer_email,
            "message": text, "is_auto_reply": False
        }).execute()
        return {"sent": text}
    return {"error": "Shortcut no dey"}