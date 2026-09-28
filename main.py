from fastapi import FastAPI
from supabase import create_client
import random, smtplib, os, time
from email.mime.text import MIMEText
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

load_dotenv()
app = FastAPI(title="Redbub-API - FULL UPDATED FOR ALL SCREENS")

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
        "message": "Redbub API dey work! OTP + Name + Username + Phone + Device + Continue + Retrieve + Login 🚀",
        "supabase_connected": supabase is not None,
        "status": "LIVE UPDATED - ALL SCREENS",
        "email_configured": bool(os.getenv("EMAIL") and os.getenv("EMAIL_PASS")),
        "features": ["send-otp", "verify-otp", "device-accounts", "check-email", "get-username", "update-password", "greetings"]
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
        "phone_no": phone.strip() if phone else "",
        "avatar_url": "",
        "profile_pic": "",
        "icon_url": "",
    }

    saved_data = base_data
    if supabase is not None:
        try:
            supabase.table("profiles").upsert(extended_data, on_conflict="email").execute()
            saved_data = extended_data
            print(f"SAVED: {email} {formatted_username} {full_name} {phone} {device_name}")
        except Exception as e:
            print(f"Extended upsert failed: {e}")
            try:
                supabase.table("profiles").upsert(base_data, on_conflict="email").execute()
                saved_data = base_data
            except Exception as e2:
                print(f"Base upsert also failed: {e2}")
                try:
                    minimal = {"email": email.strip().lower(), "otp": otp, "verified": False}
                    supabase.table("profiles").upsert(minimal, on_conflict="email").execute()
                except Exception as e3:
                    print(f"Minimal upsert failed: {e3}")

    html_body = f"""
    <html><body style="font-family: Arial; text-align: center; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; border: 1px solid #eee; border-radius: 16px; padding: 30px;">
            <h2 style="color: #FF8A1A;">RedbubMega</h2>
            <h3>Confirm your email address</h3>
            <p>Hello {full_name or 'there'},</p>
            <p>Your <b>6-digit code</b> is:</p>
            <div style="font-size: 48px; font-weight: 900; letter-spacing: 12px; background: #FFF7ED; padding: 20px; margin: 25px auto; border-radius: 12px; border: 2px dashed #FF8A1A;">{otp}</div>
            <p>Username: <b>{formatted_username}</b> | Full Name: <b>{full_name}</b></p>
            <p style="font-size: 14px;">Device: {device_name or 'Unknown'} | Phone: {phone}</p>
            <p style="font-size: 13px;">This code will expire in <b>5 minutes</b>.</p>
        </div>
    </body></html>
    """
    
    sender_email = os.getenv("EMAIL")
    sender_pass = os.getenv("EMAIL_PASS")
    email_sent = False
    email_error = None

    if sender_email and sender_pass:
        msg = MIMEText(html_body, "html")
        msg["Subject"] = f"Your Redbub OTP is {otp} - {formatted_username}"
        msg["From"] = f"RedbubMega <{sender_email}>"
        msg["To"] = email
        msg["Reply-To"] = sender_email
        
        for attempt in range(2):
            try:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
                    server.login(sender_email, sender_pass)
                    server.send_message(msg)
                email_sent = True
                print(f"✅ Email sent to {email} OTP {otp}")
                break
            except Exception as email_err:
                email_error = str(email_err)
                print(f"❌ Email failed attempt {attempt+1}: {email_err}")
                if "Username and Password not accepted" in email_error or "Authentication" in email_error:
                    email_error = "Gmail App Password WRONG - Generate NEW 16-char password"
                    break
                time.sleep(1)
    else:
        email_error = "EMAIL or EMAIL_PASS env missing on Render"

    if email_sent:
        return {"message": f"REAL OTP {otp} sent to {email}", "otp": otp, "email_sent": True, "saved": saved_data}
    else:
        return {"message": f"OTP {otp} generated but email failed: {email_error}", "otp_for_testing": otp, "otp": otp, "email_sent": False, "email_error": email_error, "saved": saved_data}

@app.api_route("/verify-otp", methods=["GET", "POST"])
def verify_otp(email: str, otp: str):
    if supabase is None:
        return {"verified": False, "message": "Supabase not configured"}
    try:
        result = supabase.table("profiles").select("*").eq("email", email).eq("otp", otp).execute()
        if result.data:
            supabase.table("profiles").update({"verified": True}).eq("email", email).execute()
            return {"verified": True, "message": "OTP correct ✅", "profile": result.data[0]}
        return {"verified": False, "message": "Wrong OTP ❌"}
    except Exception as e:
        return {"verified": False, "message": f"Error: {e}"}

# ===== FOR CONTINUE, RETRIEVE, LOGIN SCREENS =====

@app.api_route("/device-accounts/add", methods=["GET","POST"])
def add_device_account(email: str = "", full_name: str = "", username: str = "", phone: str = "", device_name: str = "", device_id: str = "", profile_url: str = ""):
    if not supabase:
        return {"saved": False, "reason": "no supabase"}
    try:
        supabase.table("profiles").upsert({
            "email": email.lower(), "full_name": full_name, "username": username,
            "phone": phone, "phone_no": phone, "device_name": device_name,
            "device_id": device_id, "avatar_url": profile_url,
        }, on_conflict="email").execute()
        
        try:
            existing = supabase.table("device_accounts").select("*").eq("device_id", device_id).execute()
            if existing.data:
                accs = existing.data[0].get("accounts", []) or []
                if not any(a.get("email")==email.lower() for a in accs if isinstance(a, dict)):
                    accs.append({"email": email.lower(), "full_name": full_name, "username": username, "phone": phone, "device_name": device_name, "profile_url": profile_url})
                supabase.table("device_accounts").update({"device_id": device_id, "device_name": device_name, "accounts": accs, "last_updated": datetime.now(timezone.utc).isoformat()}).eq("device_id", device_id).execute()
            else:
                supabase.table("device_accounts").insert({"device_id": device_id, "device_name": device_name, "accounts": [{"email": email.lower(), "full_name": full_name, "username": username, "phone": phone, "device_name": device_name, "profile_url": profile_url}], "last_updated": datetime.now(timezone.utc).isoformat()}).execute()
        except Exception as e:
            print(f"device_accounts save failed: {e}")
        return {"saved": True, "device_id": device_id, "email": email}
    except Exception as e:
        return {"saved": False, "error": str(e)}

@app.api_route("/device-accounts/list", methods=["GET","POST"])
def list_device_accounts(device_id: str = ""):
    if not supabase:
        return {"accounts": []}
    try:
        result = supabase.table("device_accounts").select("*").eq("device_id", device_id).execute()
        if result.data:
            return {"device_id": device_id, "accounts": result.data[0].get("accounts", []), "device_name": result.data[0].get("device_name")}
        profiles = supabase.table("profiles").select("*").eq("device_id", device_id).execute()
        return {"device_id": device_id, "accounts": profiles.data or []}
    except Exception as e:
        return {"accounts": [], "error": str(e)}

@app.api_route("/auth/check-email", methods=["GET","POST"])
def check_email_registered(email: str = ""):
    if not supabase:
        return {"exists": False}
    try:
        result = supabase.table("profiles").select("email,username,full_name").eq("email", email.lower()).execute()
        if result.data:
            return {"exists": True, "message": "Email registered ✅", "profile": result.data[0], "username": result.data[0].get("username")}
        return {"exists": False, "message": "Email not registered on RedbubMega ❌"}
    except Exception as e:
        return {"exists": False, "error": str(e)}

@app.api_route("/auth/get-username", methods=["GET","POST"])
def get_username(email: str = "", phone: str = ""):
    if not supabase:
        return {"found": False}
    try:
        result = None
        if email and "@" in email:
            result = supabase.table("profiles").select("email,username,full_name,phone").eq("email", email.lower()).execute()
        elif phone:
            result = supabase.table("profiles").select("email,username,full_name,phone").eq("phone", phone).execute()
            if not result.data:
                result = supabase.table("profiles").select("email,username,full_name,phone").eq("phone_no", phone).execute()
        if result and result.data:
            p = result.data[0]
            return {"found": True, "username": p.get("username", "@user.redapp.mega"), "full_name": p.get("full_name"), "email": p.get("email")}
        return {"found": False}
    except Exception as e:
        return {"found": False, "error": str(e)}

@app.api_route("/auth/update-password", methods=["GET","POST"])
def update_password(email: str = "", new_password: str = "", device_name: str = ""):
    if not supabase:
        return {"updated": False}
    try:
        supabase.table("profiles").update({"password": new_password, "last_password_update": datetime.now(timezone.utc).isoformat(), "device_name": device_name}).eq("email", email.lower()).execute()
        try:
            all_devices = supabase.table("device_accounts").select("*").execute()
            for dev in all_devices.data or []:
                accs = dev.get("accounts", [])
                updated = False
                for acc in accs:
                    if isinstance(acc, dict) and acc.get("email")==email.lower():
                        acc["password"] = new_password
                        updated = True
                if updated:
                    supabase.table("device_accounts").update({"accounts": accs}).eq("device_id", dev["device_id"]).execute()
        except Exception as e:
            print(f"device_accounts pwd update failed: {e}")
        return {"updated": True, "message": "Password updated ✅ Saved to DB & Password Manager", "email": email}
    except Exception as e:
        return {"updated": False, "error": str(e)}

# ===== GREETINGS & MESSAGES =====

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
            supabase.table("greeting_settings").upsert({"owner_email": owner_email, "is_enabled": is_enabled, "custom_message": custom_message}, on_conflict="owner_email").execute()
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
        return {"is_enabled": True, "custom_message": None, "effective_greeting": DEFAULT_OWNER_GREETING}

@app.post("/messages/start-chat")
def start_chat(customer_email: str, owner_email: str, is_redbub_ai: bool = False):
    if not supabase:
        return {"greeted": False, "reason": "supabase not configured"}
    try:
        if is_redbub_ai:
            greeting = REDBUB_AI_GREETING
            supabase.table("messages").insert({"sender_email": "redbub_ai", "receiver_email": customer_email, "message": greeting, "is_auto_reply": True}).execute()
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
            supabase.table("messages").insert({"sender_email": owner_email, "receiver_email": customer_email, "message": greeting, "is_auto_reply": True}).execute()
            return {"greeted": True, "type": "owner", "message": greeting}
        return {"greeted": False}
    except Exception as e:
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
        supabase.table("messages").insert({"sender_email": sender, "receiver_email": receiver, "message": text, "is_auto_reply": False}).execute()
        status = supabase.table("user_status").select("*").eq("email", receiver).execute()
        if not status.data or not status.data[0].get("is_online", False):
            greet_setting = supabase.table("greeting_settings").select("*").eq("owner_email", receiver).execute()
            if greet_setting.data and not greet_setting.data[0]["is_enabled"]:
                return {"status": "sent, no auto-reply (OFF)"}
            auto_text = DEFAULT_OWNER_GREETING
            if greet_setting.data and greet_setting.data[0].get("custom_message"):
                auto_text = greet_setting.data[0]["custom_message"]
            supabase.table("messages").insert({"sender_email": receiver, "receiver_email": sender, "message": auto_text, "is_auto_reply": True}).execute()
            return {"status": "sent + auto-reply", "auto_reply": auto_text}
        return {"status": "sent"}
    except Exception as e:
        return {"status": f"error: {e}"}

@app.post("/quick-replies/save")
def save_quick_reply(owner_email: str, shortcut: str, reply_text: str):
    if supabase:
        try:
            supabase.table("quick_replies").upsert({"owner_email": owner_email, "shortcut": shortcut, "reply_text": reply_text}, on_conflict="owner_email,shortcut").execute()
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
            supabase.table("messages").insert({"sender_email": owner_email, "receiver_email": customer_email, "message": text, "is_auto_reply": False}).execute()
            return {"sent": text}
        return {"error": "Shortcut no dey"}
    except Exception as e:
        return {"error": str(e)}