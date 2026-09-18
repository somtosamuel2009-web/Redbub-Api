from fastapi import FastAPI
from supabase import create_client
import random, smtplib, os
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
    print("WARNING: SUPABASE_URL or KEY missing!")
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
        "status": "LIVE"
    }

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

    # THIS ONE GO SAVE NAME, PHONE AND USERNAME FOR SUPABASE!
    base_data = {
        "email": email.strip().lower(),
        "full_name": full_name.strip() if full_name else "",
        "phone": phone.strip() if phone else "",
        "username": formatted_username, # <--- @username.redapp.mega
        "username_raw": clean_username, # <--- raw username
        "otp": otp,
        "verified": False,
        "last_otp_sent": datetime.now(timezone.utc).isoformat()
    }

    if supabase is not None:
        try:
            supabase.table("profiles").upsert(base_data, on_conflict="email").execute()
            print(f"SAVED: {email} | {full_name} | {formatted_username} | {phone}")
        except Exception as e:
            print(f"Save failed: {e}")
            try:
                minimal = {"email": email.strip().lower(), "full_name": full_name, "phone": phone, "username": formatted_username, "otp": otp, "verified": False}
                supabase.table("profiles").upsert(minimal, on_conflict="email").execute()
            except Exception as e2:
                print(f"Minimal save failed: {e2}")

    # Send Gmail OTP
    html_body = f"<h2>RedbubMega</h2><p>Hello {full_name or 'there'},</p><h1>{otp}</h1><p>Username: {formatted_username} | Name: {full_name} | Phone: {phone}</p>"
    sender_email = os.getenv("EMAIL")
    sender_pass = os.getenv("EMAIL_PASS")
    email_sent = False

    if sender_email and sender_pass:
        msg = MIMEText(html_body, "html")
        msg["Subject"] = f"Your Redbub OTP is {otp} - {formatted_username}"
        msg["From"] = f"RedbubMega <{sender_email}>"
        msg["To"] = email
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(sender_email, sender_pass)
                server.send_message(msg)
            email_sent = True
        except Exception as e:
            print(f"Email failed: {e}")

    return {"message": f"OTP {otp} sent", "otp": otp, "email_sent": email_sent, "saved": base_data}

@app.post("/verify-otp")
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