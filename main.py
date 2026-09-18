
from fastapi import FastAPI
from supabase import create_client
import random, smtplib, os, time
from email.mime.text import MIMEText
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

load_dotenv()
app = FastAPI(title="Redbub-API - Firestore nam5 US LIVE")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("WARNING: SUPABASE_URL or KEY missing! Check Render Env")
    supabase = None
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print(f"Supabase connected: {SUPABASE_URL}")
    except Exception as e:
        print(f"Supabase create_client failed: {e}")
        supabase = None

REDBUB_AI_GREETING = "Hello👋, how can I help you"
DEFAULT_OWNER_GREETING = "Thanks for reaching out on us👍. How can we help you"

@app.get("/")
def home():
    return {
        "message": "Redbub API dey work! OTP + Name + Username + Phone + Device + Firestore nam5 🚀",
        "supabase_connected": supabase is not None,
        "firestore_region": "nam5",
        "status": "LIVE",
        "email_configured": bool(os.getenv("EMAIL") and os.getenv("EMAIL_PASS"))
    }

@app.api_route("/send-otp", methods=["GET", "POST"])
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
        clean_username = clean_username.replace("@", "").replace(".redapp.mega", "").replace(" ", "")
        formatted_username = f"@{clean_username}.redapp.mega"
    else:
        if full_name:
            base = full_name.lower().replace(" ", "").replace("-", "")[:15]
            base = ''.join(c for c in base if c.isalnum())[:15]
            formatted_username = f"@{base}.redapp.mega" if base else f"@user{random.randint(100,999)}.redapp.mega"
            clean_username = base
        else:
            formatted_username = f"@user{random.randint(1000,9999)}.redapp.mega"
            clean_username = formatted_username.replace("@","").replace(".redapp.mega","")

    base_data = {
        "email": email.strip().lower(),
        "full_name": full_name.strip() if full_name else "",
        "phone": phone.strip() if phone else "",
        "username": formatted_username,
        "otp": otp,
        "verified": False,
        "last_otp_sent": datetime.now(timezone.utc).isoformat()
    }

    extended_data = {
        **base_data,
        "username_raw": clean_username,
        "device_name": device_name.strip() if device_name else "",
        "device_model": device_model.strip() if device_model else "",
        "platform": platform.strip() if platform else "",
    }

    saved_data = base_data
    if supabase is not None:
        try:
            supabase.table("profiles").upsert(extended_data, on_conflict="email").execute()
            saved_data = extended_data
            print(f"SAVED extended: {email} {formatted_username} {full_name} {phone}")
        except Exception as e:
            print(f"Extended upsert failed (columns missing?): {e}")
            try:
                supabase.table("profiles").upsert(base_data, on_conflict="email").execute()
                saved_data = base_data
                print(f"SAVED base: {email} {formatted_username}")
            except Exception as e2:
                print(f"Base upsert also failed: {e2}")
                try:
                    minimal = {"email": email.strip().lower(), "otp": otp, "verified": False}
                    supabase.table("profiles").upsert(minimal, on_conflict="email").execute()
                except Exception as e3:
                    print(f"Minimal upsert failed: {e3}")
    else:
        print("Supabase is None - skipping DB save")

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; text-align: center; padding: 20px; background: #ffffff;">
        <div style="max-width: 500px; margin: 0 auto; border: 1px solid #eee; border-radius: 16px; padding: 30px;">
            <h2 style="color: #FF8A1A; margin-bottom: 10px;">RedbubMega</h2>
            <h3 style="color: #333;">Confirm your email address</h3>
            <p style="color: #555;">Hello {full_name or 'there'},</p>
            <p>Your <b>6-digit verification code</b> is:</p>
            <div style="font-size: 48px; font-weight: 900; letter-spacing: 12px; color: #000; background: #FFF7ED; padding: 20px 30px; margin: 25px auto; width: fit-content; border-radius: 12px; border: 2px dashed #FF8A1A;">
                {otp}
            </div>
            <p style="color: #333;">Username: <b>{formatted_username}</b> | Full Name: <b>{full_name}</b></p>
            <p style="color: #666; font-size: 14px;">Device: {device_name or 'Unknown'} | Phone: {phone} | Platform: {platform}</p>
            <p style="color: #888; font-size: 13px;">This code will expire in <b>5 minutes</b>.</p>
            <p style="color: #888; font-size: 12px; margin-top: 25px;">Don't share this code with anyone. Firestore: nam5 US</p>
            <p style="color: #888; font-size: 10px; margin-top: 10px;">If you didn't request this, ignore this email.</p>
        </div>
    </body>
    </html>
    """
    
    sender_email = os.getenv("EMAIL")
    sender_pass = os.getenv("EMAIL_PASS")
    email_sent = False
    email_error = None

    # FIXED: Better email sending with retry and proper headers
    if sender_email and sender_pass:
        msg = MIMEText(html_body, "html")
        msg["Subject"] = f"Your Redbub OTP is {otp} - {formatted_username}"
        msg["From"] = f"RedbubMega <{sender_email}>"
        msg["To"] = email
        # Important: Add Reply-To and prevent spam flag
        msg["Reply-To"] = sender_email
        
        # Retry logic - try 2 times
        for attempt in range(2):
            try:
                print(f"Attempt {attempt+1}: Sending email to {email} from {sender_email}")
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
                    server.login(sender_email, sender_pass)
                    server.send_message(msg)
                email_sent = True
                print(f"✅ Email sent to {email} OTP {otp} on attempt {attempt+1}")
                break
            except Exception as email_err:
                email_error = str(email_err)
                print(f"❌ Email send failed attempt {attempt+1}: {email_err}")
                if "Username and Password not accepted" in email_error or "Authentication" in email_error:
                    email_error = "Gmail App Password WRONG or EXPIRED - Go to myaccount.google.com → App Passwords → Generate NEW 16-char password"
                    break
                time.sleep(1)
    else:
        email_error = "EMAIL or EMAIL_PASS env missing on Render - Go to Render Dashboard → Environment → Add EMAIL and EMAIL_PASS"
        print(email_error)

    # ALWAYS return OTP info so frontend can show error reason
    if email_sent:
        return {
            "message": f"REAL OTP {otp} sent to {email}",
            "otp": otp,
            "email_sent": True,
            "firestore_region": "nam5",
            "saved": saved_data
        }
    else:
        return {
            "message": f"OTP {otp} generated but email failed: {email_error}",
            "otp_for_testing": otp,
            "otp": otp,
            "email_sent": False,
            "email_error": email_error,
            "firestore_region": "nam5",
            "saved": saved_data,
            "debug_email": sender_email
        }

@app.api_route("/verify-otp", methods=["GET", "POST"])
def verify_otp(email: str, otp: str):
    if supabase is None:
        return {"verified": False, "message": "Supabase not configured on server"}
    try:
        result = supabase.table("profiles").select("*").eq("email", email).eq("otp", otp).execute()
        if result.data:
            supabase.table("profiles").update({"verified": True}).eq("email", email).execute()
            return {"verified": True, "message": "OTP correct ✅", "profile": result.data[0]}
        return {"verified": False, "message": "Wrong OTP ❌"}
    except Exception as e:
        print(f"verify-otp error: {e}")
        return {"verified": False, "message": f"Error: {e}"}

@app.get("/ai/welcome")
def ai_welcome():
    return {"type": "redbub_ai", "message": REDBUB_AI_GREETING}

@app.post("/ai/chat")
def ai_chat(message: str):
    return {"reply": f"Redbub AI: You said '{message}'. I dey learn your thrift style!"}

@app.post("/greeting/set")
def set_greeting(owner_email: str, is_enabled: bool, custom_message: str = None):
    if supabase:
        try:
            supabase.table("greeting_settings").upsert({
                "owner_email": owner_email,
                "is_enabled": is_enabled,
                "custom_message": custom_message
            }, on_conflict="owner_email").execute()
        except Exception as e:
            print(f"greeting set failed: {e}")
    return {"saved": True, "is_enabled": is_enabled, "custom_message": custom_message or DEFAULT_OWNER_GREETING}

@app.get("/greeting/get")
def get_greeting(owner_email: str):
    if not supabase:
        return {"is_enabled": True, "custom_message": None, "effective_greeting": DEFAULT_OWNER_GREETING}
    try:
        result = supabase.table("greeting_settings").select("*").eq("owner_email", owner_email).execute()
        if not result.data:
            return {"is_enabled": True, "custom_message": None, "effective_greeting": DEFAULT_OWNER_GREETING}
        row = result.data[0]
        effective = row["custom_message"] if row["custom_message"] else DEFAULT_OWNER_GREETING
        return {"is_enabled": row["is_enabled"], "custom_message": row["custom_message"], "effective_greeting": effective}
    except Exception as e:
        print(f"greeting get failed: {e}")
        return {"is_enabled": True, "custom_message": None, "effective_greeting": DEFAULT_OWNER_GREETING}

@app.post("/messages/start-chat")
def start_chat(customer_email: str, owner_email: str, is_redbub_ai: bool = False):
    if not supabase:
        return {"greeted": False, "reason": "supabase not configured"}
    try:
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
    except Exception as e:
        print(f"start-chat error: {e}")
        return {"greeted": False, "error": str(e)}

@app.post("/status/set")
def set_status(email: str, is_online: bool):
    if supabase:
        try:
            supabase.table("user_status").upsert({"email": email, "is_online": is_online}, on_conflict="email").execute()
        except Exception as e:
            print(f"status set failed: {e}")
    return {"email": email, "is_online": is_online}

@app.post("/messages/send")
def send_message(sender: str, receiver: str, text: str):
    if not supabase:
        return {"status": "supabase not configured"}
    try:
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
    except Exception as e:
        print(f"send message error: {e}")
        return {"status": f"error: {e}"}

@app.post("/quick-replies/save")
def save_quick_reply(owner_email: str, shortcut: str, reply_text: str):
    if supabase:
        try:
            supabase.table("quick_replies").upsert({
                "owner_email": owner_email, "shortcut": shortcut, "reply_text": reply_text
            }, on_conflict="owner_email,shortcut").execute()
        except Exception as e:
            print(f"quick-reply save failed: {e}")
    return {"message": f"Quick reply /{shortcut} saved ✅"}

@app.post("/quick-replies/use")
def use_quick_reply(owner_email: str, shortcut: str, customer_email: str):
    if not supabase:
        return {"error": "supabase not configured"}
    try:
        result = supabase.table("quick_replies").select("*").eq("owner_email", owner_email).eq("shortcut", shortcut).execute()
        if result.data:
            text = result.data[0]["reply_text"]
            supabase.table("messages").insert({
                "sender_email": owner_email, "receiver_email": customer_email,
                "message": text, "is_auto_reply": False
            }).execute()
            return {"sent": text}
        return {"error": "Shortcut no dey"}
    except Exception as e:
        print(f"quick-reply use failed: {e}")
        return {"error": str(e)}
