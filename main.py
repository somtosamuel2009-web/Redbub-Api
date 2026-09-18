from fastapi import FastAPI
from supabase import create_client
import random, smtplib, os
from email.mime.text import MIMEText
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

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

REDBUB_AI_GREETING = "Hello👋, how can I help you"
DEFAULT_OWNER_GREETING = "Thanks for reaching out on us👍. How can we help you"

@app.get("/")
def home():
    return {"message": "Redbub API dey work! OTP + 2 Greetings + Auto-reply + Device + Username ready 🚀"}

@app.post("/send-otp")
def send_otp(
    email: str, 
    full_name: str = "", 
    phone: str = "", 
    username: str = "", 
    device_name: str = "", 
    device_model: str = "", 
    platform: str = ""
):
    otp = str(random.randint(100000, 999999))
    
    clean_username = username.strip().lower()
    if clean_username:
        clean_username = clean_username.replace("@", "").replace(".redapp.mega", "")
        formatted_username = f"@{clean_username}.redapp.mega"
    else:
        if full_name:
            base = full_name.lower().replace(" ", "").replace("-", "")[:15]
            base = ''.join(c for c in base if c.isalnum())[:15]
            formatted_username = f"@{base}.redapp.mega"
        else:
            formatted_username = ""
            clean_username = ""

    profile_data = {
        "email": email.strip().lower(),
        "full_name": full_name.strip() if full_name else "",
        "phone": phone.strip() if phone else "",
        "username": formatted_username,
        "username_raw": clean_username,
        "device_name": device_name.strip() if device_name else "",
        "device_model": device_model.strip() if device_model else "",
        "platform": platform.strip() if platform else "",
        "otp": otp,
        "verified": False,
        "last_otp_sent": datetime.now(timezone.utc).isoformat()
    }

    filtered_data = {}
    for k, v in profile_data.items():
        if k in ["email", "otp", "verified", "last_otp_sent"]:
            filtered_data[k] = v
        elif isinstance(v, str) and v != "":
            filtered_data[k] = v
        elif isinstance(v, bool):
            filtered_data[k] = v

    try:
        supabase.table("profiles").upsert(filtered_data, on_conflict="email").execute()
    except Exception as e:
        print(f"Upsert failed: {e}")
        try:
            supabase.table("profiles").upsert({
                "email": email.strip().lower(), 
                "full_name": full_name,
                "phone": phone, 
                "otp": otp, 
                "verified": False
            }, on_conflict="email").execute()
        except Exception as e2:
            print(f"Basic upsert also failed: {e2}")

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; text-align: center; padding: 20px; background: #ffffff;">
        <div style="max-width: 500px; margin: 0 auto; border: 1px solid #eee; border-radius: 16px; padding: 30px;">
            <h2 style="color: #FF8A1A; margin-bottom: 10px;">RedbubMega</h2>
            <h3 style="color: #333;">Confirm your email address</h3>
            <p style="color: #555;">Hello {full_name or 'there'},</p>
            <p>Your <b>6-digit verification code</b> is:</p>
            <div style="font-size: 42px; font-weight: 900; letter-spacing: 10px; color: #000; background: #FFF7ED; padding: 20px 30px; margin: 25px auto; width: fit-content; border-radius: 12px; border: 2px dashed #FF8A1A;">
                {otp}
            </div>
            <p style="color: #333;">Username: <b>{formatted_username}</b></p>
            <p style="color: #666; font-size: 14px;">Device: {device_name or 'Unknown'} | Phone: {phone}</p>
            <p style="color: #888; font-size: 13px;">This code will expire in <b>5 minutes</b>.</p>
            <p style="color: #888; font-size: 12px; margin-top: 25px;">Don't share this code with anyone.</p>
        </div>
    </body>
    </html>
    """
    msg = MIMEText(html_body, "html")
    msg["Subject"] = f"Your Redbub OTP is {otp} - {formatted_username}"
    msg["From"] = f"RedbubMega <{os.getenv('EMAIL')}>"
    msg["To"] = email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(os.getenv("EMAIL"), os.getenv("EMAIL_PASS"))
            server.send_message(msg)
    except Exception as email_err:
        print(f"Email send failed: {email_err}")
        return {"message": f"OTP {otp} generated but email failed: {str(email_err)}", "otp_for_testing": otp, "saved": filtered_data}
    
    return {
        "message": f"REAL OTP {otp} sent to {email}",
        "saved": {
            "email": email,
            "full_name": full_name,
            "username": formatted_username,
            "phone": phone,
            "device_name": device_name,
            "otp": otp
        }
    }

@app.post("/verify-otp")
def verify_otp(email: str, otp: str):
    result = supabase.table("profiles").select("*").eq("email", email).eq("otp", otp).execute()
    if result.data:
        supabase.table("profiles").update({"verified": True}).eq("email", email).execute()
        return {"verified": True, "message": "OTP correct ✅"}
    return {"verified": False, "message": "Wrong OTP ❌"}

@app.get("/ai/welcome")
def ai_welcome():
    return {"type": "redbub_ai", "message": REDBUB_AI_GREETING}

@app.post("/ai/chat")
def ai_chat(message: str):
    return {"reply": f"Redbub AI: You said '{message}'. I dey learn your thrift style!"}

@app.post("/greeting/set")
def set_greeting(owner_email: str, is_enabled: bool, custom_message: str = None):
    supabase.table("greeting_settings").upsert({
        "owner_email": owner_email,
        "is_enabled": is_enabled,
        "custom_message": custom_message
    }, on_conflict="owner_email").execute()
    return {"saved": True, "is_enabled": is_enabled, "custom_message": custom_message or DEFAULT_OWNER_GREETING}

@app.get("/greeting/get")
def get_greeting(owner_email: str):
    result = supabase.table("greeting_settings").select("*").eq("owner_email", owner_email).execute()
    if not result.data:
        return {"is_enabled": True, "custom_message": None, "effective_greeting": DEFAULT_OWNER_GREETING}
    row = result.data[0]
    effective = row["custom_message"] if row["custom_message"] else DEFAULT_OWNER_GREETING
    return {"is_enabled": row["is_enabled"], "custom_message": row["custom_message"], "effective_greeting": effective}

@app.post("/messages/start-chat")
def start_chat(customer_email: str, owner_email: str, is_redbub_ai: bool = False):
    if is_redbub_ai:
        greeting = REDBUB_AI_GREETING
        supabase.table("messages").insert({
            "sender_email": "redbub_ai",
            "receiver_email": customer_email,
            "message": greeting,
            "is_auto_reply": True
        }).execute()
        return {"greeted": True, "type": "redbub_ai", "message": greeting}

    setting = supabase.table("greeting_settings").select("*").eq("owner_email", owner_email).execute()
    
    if not setting.data:
        greeting = DEFAULT_OWNER_GREETING
        should_greet = True
    else:
        row = setting.data[0]
        should_greet = row["is_enabled"]
        if not should_greet:
            return {"greeted": False, "type": "owner", "message": None, "reason": "Toggle OFF"}
        greeting = row["custom_message"] if row["custom_message"] and row["custom_message"].strip() != "" else DEFAULT_OWNER_GREETING

    if should_greet:
        supabase.table("messages").insert({
            "sender_email": owner_email,
            "receiver_email": customer_email,
            "message": greeting,
            "is_auto_reply": True
        }).execute()
        return {"greeted": True, "type": "owner", "message": greeting}
    return {"greeted": False}

@app.post("/status/set")
def set_status(email: str, is_online: bool):
    supabase.table("user_status").upsert({"email": email, "is_online": is_online}, on_conflict="email").execute()
    return {"email": email, "is_online": is_online}

@app.post("/messages/send")
def send_message(sender: str, receiver: str, text: str):
    supabase.table("messages").insert({
        "sender_email": sender, "receiver_email": receiver,
        "message": text, "is_auto_reply": False
    }).execute()
    status = supabase.table("user_status").select("*").eq("email", receiver).execute()
    if not status.data or not status.data[0].get("is_online", False):
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