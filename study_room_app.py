"""
StudyConnect - メール確認付き登録 + パスワードログイン版（UI全面刷新）
"""

import streamlit as st
from datetime import datetime, timedelta
import time
import random
import string
import hashlib
import re
import boto3
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ─────────────────────────────────────────────
# ページ設定 & CSS
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="StudyConnect - 一緒に勉強しよう",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;600;700;900&family=DM+Sans:wght@400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', 'DM Sans', sans-serif;
    }

    /* ── ブラウザUIツールバー類を非表示 ── */
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { display: none !important; }
    .stDeployButton { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    footer { visibility: hidden !important; display: none !important; }
    ._profileContainer_gzau3_53 { display: none !important; }
    [data-testid="baseButton-headerNoPadding"] { display: none !important; }
    .viewerBadge_container__r5tak { display: none !important; }
    .viewerBadge_link__qRIco { display: none !important; }
    button[title="View fullscreen"] { display: none !important; }
    button[title="Share"] { display: none !important; }
    button[aria-label="Share"] { display: none !important; }
    [data-testid="manage-app-button"] { display: none !important; }
    [data-testid="stAppViewBlockContainer"] > div:first-child { padding-top: 1rem !important; }

    /* ── X風 全体背景（真っ黒） ── */
    .stApp { background: #000000; }
    .main { background: #000000; }
    [data-testid="stAppViewContainer"] { background: #000000; }
    [data-testid="block-container"] { background: #000000; }

    /* ── サイドバー全体 ── */
    [data-testid="stSidebar"] {
        background: #000000 !important;
        border-right: 1px solid #2f3336 !important;
    }
    [data-testid="stSidebar"] * { color: #e7e9ea !important; }
    [data-testid="stSidebar"] .stTextInput input {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #e7e9ea !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.1) !important;
        margin: 0.75rem 0 !important;
    }

    /* ── ユーザーセクション ── */
    .user-section {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 14px;
        padding: 1.1rem 1rem;
        margin-bottom: 0.8rem;
        text-align: center;
    }
    .user-avatar {
        width: 46px; height: 46px;
        background: linear-gradient(135deg, #667eea, #764ba2);
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 1.25rem;
        margin: 0 auto 0.55rem auto;
    }
    .user-name { font-size: 0.92rem; font-weight: 700; color: #fff !important; margin-bottom: 0.15rem; }
    .user-email { font-size: 0.7rem; color: rgba(255,255,255,0.4) !important; word-break: break-all; }
    .admin-pill {
        display: inline-block;
        background: linear-gradient(135deg, #f59e0b, #ef4444);
        color: white !important; border-radius: 20px;
        padding: 0.1rem 0.65rem; font-size: 0.65rem; font-weight: 700;
        margin-top: 0.4rem;
    }

    /* ── AIランチャー ── */
    .launcher-label {
        font-size: 0.63rem; font-weight: 700; letter-spacing: 0.15em;
        text-transform: uppercase; color: rgba(255,255,255,0.3) !important;
        margin: 0 0 0.6rem 0.1rem; display: block;
    }
    .ai-card {
        display: flex; align-items: center; gap: 0.8rem;
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.09) !important;
        border-radius: 12px; padding: 0.8rem 1rem;
        margin-bottom: 0.5rem; text-decoration: none !important;
        transition: background 0.2s, border-color 0.2s, transform 0.15s;
    }
    .ai-card:hover {
        background: rgba(102,126,234,0.22) !important;
        border-color: rgba(102,126,234,0.45) !important;
        transform: translateX(4px);
        text-decoration: none !important;
    }
    .ai-card-emoji { font-size: 1.6rem; flex-shrink: 0; line-height: 1; }
    .ai-card-body { flex: 1; min-width: 0; }
    .ai-card-title {
        font-size: 0.84rem; font-weight: 700;
        color: #c7d2fe !important; display: block;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .ai-card-sub {
        font-size: 0.7rem; color: rgba(199,210,254,0.5) !important;
        display: block; margin-top: 0.1rem;
    }
    .ai-card-arrow { font-size: 0.8rem; color: rgba(255,255,255,0.22) !important; flex-shrink: 0; }

    /* ── メインヘッダー ── */
    .main-header {
        background: linear-gradient(135deg, #000000 0%, #0d0d0d 100%); border-radius: 20px;
        padding: 2.2rem 2rem; margin-bottom: 1.5rem;
        text-align: center; position: relative; overflow: hidden;
        border: 1px solid #2f3336;
    }
    .main-header::before {
        content: ''; position: absolute; inset: 0;
        background:
            radial-gradient(ellipse at 25% 50%, rgba(102,126,234,0.18) 0%, transparent 55%),
            radial-gradient(ellipse at 75% 50%, rgba(118,75,162,0.14) 0%, transparent 55%);
    }
    .main-header h1 {
        font-size: 2.2rem; font-weight: 900; color: #e7e9ea;
        margin: 0 0 0.3rem 0; position: relative;
    }
    .main-header p {
        color: rgba(231,233,234,0.5); font-size: 0.9rem;
        margin: 0; position: relative;
    }

    /* ── ルームカード ── */
    .room-card {
        background: #16181c; border-radius: 16px; padding: 1.4rem 1.6rem;
        margin-bottom: 1rem; border: 1px solid #2f3336;
        box-shadow: none;
    }
    .room-card-host {
        font-size: 1rem; font-weight: 700; color: #e7e9ea; margin-bottom: 0.8rem;
    }
    .room-url-box {
        background: #0d0d0d; border-radius: 10px;
        padding: 0.9rem 1.1rem; word-break: break-all;
        border: 1px solid #2f3336;
    }
    .room-url-box a {
        color: #a5b4fc !important; font-size: 0.82rem;
        font-weight: 500; text-decoration: none;
    }

    /* ── 空ステート ── */
    .empty-state {
        background: #16181c; border-radius: 16px; padding: 2.8rem 2rem;
        text-align: center; border: 2px dashed #2f3336; color: #71767b;
    }
    .empty-state-icon { font-size: 2.8rem; margin-bottom: 0.8rem; }
    .empty-state-title { font-weight: 700; color: #e7e9ea; margin-bottom: 0.3rem; }
    .empty-state-sub { font-size: 0.85rem; }

    /* ── ルーム追加パネル ── */
    .add-room-title { font-size: 1rem; font-weight: 800; color: #e7e9ea; margin-bottom: 0.25rem; }
    .add-room-sub { font-size: 0.78rem; color: #71767b; margin-bottom: 0; }

    /* ── セクションタイトル ── */
    .section-title {
        font-size: 1.05rem; font-weight: 800; color: #e7e9ea;
        margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;
    }

    /* ── ユーザー管理：ユーザー行カード ── */
    .user-row-card {
        background: #16181c;
        border: 1px solid #2f3336;
        border-radius: 12px;
        padding: 0.9rem 1.1rem;
        margin-bottom: 0.6rem;
        display: grid;
        grid-template-columns: 140px 1fr auto;
        align-items: center;
        gap: 0 1.5rem;
    }
    .user-row-name { font-size: 1rem; font-weight: 700; color: #e7e9ea; }
    .user-row-email { font-size: 0.88rem; color: #71767b; font-weight: 500; }
    .user-row-meta { display: flex; align-items: center; gap: 0.8rem; }
    .user-row-date { font-size: 0.82rem; color: #71767b; font-weight: 500; white-space: nowrap; }
    .user-row-admin {
        display: inline-block;
        background: linear-gradient(135deg, #f59e0b, #ef4444);
        color: white; border-radius: 20px;
        padding: 0.08rem 0.55rem; font-size: 0.65rem; font-weight: 700;
        margin-left: 0.5rem; vertical-align: middle;
    }

    /* ── expander 共通（ダーク統一）── */
    [data-testid="stExpander"] {
        background: #16181c !important;
        border: 1px solid #2f3336 !important;
        border-radius: 14px !important;
        overflow: hidden;
    }
    /* expander のすべての子要素を強制ダーク */
    [data-testid="stExpander"] *,
    [data-testid="stExpander"] > *,
    [data-testid="stExpander"] details,
    [data-testid="stExpander"] details > *,
    [data-testid="stExpander"] details > div,
    [data-testid="stExpander"] details > summary,
    [data-testid="stExpanderDetails"],
    [data-testid="stExpanderDetails"] > *,
    [data-testid="stExpanderDetails"] > div,
    [data-testid="stExpanderDetails"] > div > *,
    [data-testid="stExpanderDetails"] > div > div,
    [data-testid="stExpanderDetails"] > div > div > * {
        background-color: #16181c !important;
        color: #e7e9ea !important;
    }
    /* ボタン・入力系は個別上書きで対応するので色指定のみ除外 */
    [data-testid="stExpander"] summary {
        background: #16181c !important;
        color: #e7e9ea !important;
    }

    /* サイドバー内 expander */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        border-radius: 12px !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] *,
    [data-testid="stSidebar"] [data-testid="stExpander"] details,
    [data-testid="stSidebar"] [data-testid="stExpander"] details > *,
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"],
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"] > *,
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"] > div,
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"] > div > div {
        background-color: rgba(255,255,255,0.05) !important;
        color: #e8e8f0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] input {
        background: rgba(255,255,255,0.10) !important;
        color: #e8e8f0 !important;
        border-color: rgba(255,255,255,0.2) !important;
    }

    /* ── テキスト入力・パスワード入力（全域ダーク）── */
    input, textarea {
        background: #000000 !important;
        color: #e7e9ea !important;
        border-color: #2f3336 !important;
    }
    input::placeholder, textarea::placeholder {
        color: #71767b !important;
    }
    .stTextInput input,
    [data-testid="stTextInput"] input,
    input[type="text"],
    input[type="password"],
    input[type="email"] {
        background: #000000 !important;
        border: 1px solid #2f3336 !important;
        color: #e7e9ea !important;
        border-radius: 8px !important;
    }
    .stTextInput input:focus,
    [data-testid="stTextInput"] input:focus {
        border-color: #1d9bf0 !important;
        box-shadow: 0 0 0 2px rgba(29,155,240,0.2) !important;
    }

    /* ── Selectbox ダーク化 ── */
    [data-testid="stSelectbox"] > div > div,
    [data-testid="stSelectbox"] > div > div > div {
        background: #000000 !important;
        border: 1px solid #2f3336 !important;
        color: #e7e9ea !important;
        border-radius: 8px !important;
    }
    [data-testid="stSelectbox"] svg { fill: #e7e9ea !important; }
    /* ドロップダウンリスト */
    ul[data-testid="stSelectboxVirtualDropdown"] {
        background: #16181c !important;
        border: 1px solid #2f3336 !important;
    }
    li[role="option"] {
        background: #16181c !important;
        color: #e7e9ea !important;
    }
    li[role="option"]:hover {
        background: #2f3336 !important;
    }

    /* ── ログイン ── */
    .login-title { text-align: center; font-size: 1.8rem; font-weight: 900; color: #e7e9ea; margin-bottom: 0.3rem; }
    .login-subtitle { text-align: center; color: #71767b; font-size: 0.9rem; }
    .otp-hint {
        background: #0d1117; border: 1px solid #1d4ed8; border-radius: 10px;
        padding: 0.8rem 1rem; margin-bottom: 1rem; font-size: 0.88rem;
        color: #93c5fd; line-height: 1.55;
    }
    .step-badge {
        display: inline-block; background: #2f3336; color: #e7e9ea;
        border-radius: 20px; padding: 0.15rem 0.75rem; font-size: 0.72rem;
        font-weight: 700; margin-bottom: 0.6rem; letter-spacing: 0.04em;
    }

    /* ── タブ ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #16181c; border-radius: 12px; padding: 4px; gap: 2px;
        border: 1px solid #2f3336;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 9px !important; font-weight: 600 !important;
        font-size: 0.84rem !important; padding: 0.4rem 1rem !important;
        color: #71767b !important;
    }
    .stTabs [aria-selected="true"] {
        background: #e7e9ea !important; color: #000000 !important;
    }

    /* ── ボタン ── */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="baseButton-primary"] {
        background: #e7e9ea !important; color: #000000 !important;
        border: none !important;
        border-radius: 10px !important; font-weight: 700 !important;
        transition: opacity 0.2s !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="baseButton-primary"]:hover { opacity: 0.82 !important; }

    .stButton > button:not([kind="primary"]) {
        background: #16181c !important; color: #e7e9ea !important;
        border: 1px solid #2f3336 !important;
        border-radius: 10px !important; font-weight: 600 !important;
        transition: background 0.2s !important;
    }
    .stButton > button:not([kind="primary"]):hover {
        background: #1d1f23 !important; border-color: #71767b !important;
    }
    .stButton > button:disabled {
        background: #0d0d0d !important; color: #71767b !important;
        border-color: #2f3336 !important; opacity: 0.5 !important;
    }

    /* サイドバー内ボタン */
    [data-testid="stSidebar"] .stButton > button {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #e7e9ea !important;
        border-radius: 10px !important;
        font-size: 0.85rem !important;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(255,255,255,0.15) !important;
    }
    /* サイドバー expander 内ボタン */
    [data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button {
        background: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.12) !important;
        color: #e7e9ea !important;
        font-weight: 700 !important;
        border-radius: 10px !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button:hover {
        background: rgba(255,255,255,0.15) !important;
    }

    /* ── メイン右カラム（ルーム追加パネル）── */
    .add-panel-wrap {
        background: #16181c;
        border: 1px solid #2f3336;
        border-radius: 16px;
        padding: 1.4rem 1.5rem;
        box-shadow: none;
    }

    /* ── container border ── */
    [data-testid="stVerticalBlockBorderWrapper"] {
        background: #16181c !important;
        border: 1px solid #2f3336 !important;
        border-radius: 14px !important;
    }
    /* container 内部もダーク */
    [data-testid="stVerticalBlockBorderWrapper"] > div,
    [data-testid="stVerticalBlockBorderWrapper"] > div > div {
        background: #16181c !important;
    }

    /* ── テキスト全般をX風白に ── */
    .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: #e7e9ea !important;
    }
    label { color: #e7e9ea !important; }
    .stAlert { background: #16181c !important; border-color: #2f3336 !important; }

    /* ── 全体的なdiv背景の白抑制 ── */
    section[data-testid="stSidebar"] > div {
        background: #000000 !important;
    }

    footer { visibility: hidden; display: none; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# AWS 接続
# ─────────────────────────────────────────────

@st.cache_resource
def get_dynamodb():
    session = boto3.Session(
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
        region_name=st.secrets["AWS_REGION"]
    )
    return session.resource('dynamodb')

GMAIL_ADDRESS  = st.secrets.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASS = st.secrets.get("GMAIL_APP_PASSWORD", "")

def tbl_rooms(): return get_dynamodb().Table('StudyConnect_Rooms')
def tbl_users(): return get_dynamodb().Table('StudyConnect_Users')
def tbl_otp():   return get_dynamodb().Table('StudyConnect_OTP')


# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────

def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()
def valid_email(e):   return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e))
def norm_email(e):    return e.lower().strip()


# ─────────────────────────────────────────────
# OTP
# ─────────────────────────────────────────────

OTP_EXPIRE_MINUTES = 10

def generate_otp(): return ''.join(random.choices(string.digits, k=6))

def save_otp(email, code):
    exp = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    tbl_otp().put_item(Item={
        'email': email, 'code': code,
        'expires_at': exp.isoformat(), 'expires_at_ttl': int(exp.timestamp()),
    })

def verify_otp(email, input_code):
    try:
        item = tbl_otp().get_item(Key={'email': email}).get('Item')
        if not item or item['code'] != input_code.strip(): return False
        if datetime.utcnow() > datetime.fromisoformat(item['expires_at']): return False
        tbl_otp().delete_item(Key={'email': email})
        return True
    except: return False

def send_otp_email(email, code, purpose="メール確認"):
    subject = f"【StudyConnect】{purpose}コード"
    body_html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:2rem;">
  <h2 style="color:#1a1a2e;">📚 StudyConnect</h2>
  <p>{purpose}のためのコードをお送りします。</p>
  <div style="background:#f0f7ff;border-radius:12px;padding:1.5rem;text-align:center;margin:1.5rem 0;">
    <span style="font-size:2.5rem;font-weight:700;letter-spacing:0.3rem;color:#2563eb;">{code}</span>
  </div>
  <p style="color:#666;font-size:0.9rem;">このコードは<strong>{OTP_EXPIRE_MINUTES}分間</strong>有効です。</p>
</div>"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject; msg["From"] = GMAIL_ADDRESS; msg["To"] = email
        msg.attach(MIMEText(f"{purpose}コード: {code}", "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
            smtp.sendmail(GMAIL_ADDRESS, email, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        st.error("Gmail認証エラー"); return False
    except Exception as e:
        st.error(f"メール送信エラー: {e}"); return False


# ─────────────────────────────────────────────
# ユーザー CRUD
# ─────────────────────────────────────────────

def db_get_user(email):
    try: return tbl_users().get_item(Key={'email': email}).get('Item')
    except: return None

def db_create_user(email, password, display_name, is_admin=False):
    if db_get_user(email): return False
    try:
        tbl_users().put_item(Item={
            'email': email, 'password_hash': hash_password(password),
            'display_name': display_name, 'is_admin': is_admin,
            'verified': True, 'created_at': datetime.now().isoformat(),
        }); return True
    except: return False

def db_delete_user(email):
    try: tbl_users().delete_item(Key={'email': email}); return True
    except: return False

def db_list_users():
    try:
        return [{'email': u['email'], 'display_name': u.get('display_name', u['email']),
                 'is_admin': u.get('is_admin', False), 'created_at': u.get('created_at', '')}
                for u in tbl_users().scan().get('Items', [])]
    except: return []

def db_update_password(email, new_password):
    try:
        tbl_users().update_item(Key={'email': email},
            UpdateExpression='SET password_hash = :h',
            ExpressionAttributeValues={':h': hash_password(new_password)}); return True
    except: return False

def db_update_display_name(email, display_name):
    try:
        tbl_users().update_item(Key={'email': email},
            UpdateExpression='SET display_name = :n',
            ExpressionAttributeValues={':n': display_name}); return True
    except: return False

def authenticate(email, password):
    user = db_get_user(email)
    if user and user.get('password_hash') == hash_password(password):
        return {'email': user['email'], 'display_name': user.get('display_name', email),
                'is_admin': user.get('is_admin', False)}
    return None


# ─────────────────────────────────────────────
# ログイン / 新規登録 画面
# ─────────────────────────────────────────────

def show_auth_page():
    st.markdown("""
    <div style="text-align:center;padding:3rem 0 1.5rem 0;">
        <div style="font-size:3.5rem;margin-bottom:0.6rem;">📚</div>
        <div class="login-title">StudyConnect</div>
        <div class="login-subtitle">仲間と繋がる学習ルーム共有</div>
    </div>""", unsafe_allow_html=True)

    _, col_form, _ = st.columns([1, 1.4, 1])
    with col_form:
        tab_login, tab_reg = st.tabs(["🔐 ログイン", "✉️ 新規登録"])

        with tab_login:
            with st.container(border=True):
                email    = st.text_input("メールアドレス", placeholder="you@example.com", key="li_email")
                password = st.text_input("パスワード", type="password", placeholder="••••••••", key="li_pass")
                if st.button("ログイン", type="primary", use_container_width=True, key="li_btn"):
                    if not email or not password:
                        st.error("メールアドレスとパスワードを入力してください")
                    elif not valid_email(email):
                        st.error("有効なメールアドレスを入力してください")
                    else:
                        with st.spinner("認証中..."):
                            user = authenticate(norm_email(email), password)
                        if user:
                            st.session_state.update(authenticated=True, current_user=user, my_name=user['display_name'])
                            st.success(f"ようこそ、{user['display_name']} さん！")
                            time.sleep(0.5); st.rerun()
                        else:
                            st.error("メールアドレスまたはパスワードが正しくありません")

        with tab_reg:
            step = st.session_state.get("reg_step", 1)

            if step == 1:
                with st.container(border=True):
                    st.markdown('<span class="step-badge">STEP 1 / 3　メール確認</span>', unsafe_allow_html=True)
                    st.markdown("#### メールアドレスを入力")
                    reg_email = st.text_input("メールアドレス", placeholder="you@example.com", key="reg_email_input")
                    if st.button("確認コードを送信", type="primary", use_container_width=True, key="reg_send"):
                        e = norm_email(reg_email)
                        if not reg_email: st.error("メールアドレスを入力してください")
                        elif not valid_email(e): st.error("有効なメールアドレスを入力してください")
                        elif db_get_user(e): st.error("このメールアドレスはすでに登録されています")
                        else:
                            code = generate_otp(); save_otp(e, code)
                            with st.spinner("送信中..."):
                                ok = send_otp_email(e, code, "メール確認")
                            if ok:
                                st.session_state.reg_step = 2
                                st.session_state.reg_email = e
                                st.rerun()

            elif step == 2:
                reg_email = st.session_state.reg_email
                with st.container(border=True):
                    st.markdown('<span class="step-badge">STEP 2 / 3　コード確認</span>', unsafe_allow_html=True)
                    st.markdown(f'<div class="otp-hint">📨 <strong>{reg_email}</strong> に確認コードを送信しました。<br>{OTP_EXPIRE_MINUTES}分以内に入力してください。</div>', unsafe_allow_html=True)
                    code_input = st.text_input("確認コード（6桁）", placeholder="123456", max_chars=6, key="reg_code")
                    col_ok, col_back = st.columns([2, 1])
                    with col_ok:
                        if st.button("コードを確認", type="primary", use_container_width=True, key="reg_verify"):
                            if not code_input: st.error("確認コードを入力してください")
                            elif verify_otp(reg_email, code_input):
                                st.session_state.reg_step = 3; st.rerun()
                            else: st.error("コードが正しくないか、有効期限切れです")
                    with col_back:
                        if st.button("← 戻る", use_container_width=True, key="reg_back2"):
                            st.session_state.reg_step = 1; st.rerun()
                    if st.button("コードを再送信", use_container_width=True, key="reg_resend"):
                        code = generate_otp(); save_otp(reg_email, code)
                        with st.spinner("再送信中..."): send_otp_email(reg_email, code, "メール確認")
                        st.success("新しいコードを送信しました")

            elif step == 3:
                reg_email = st.session_state.get("reg_email")
                if not reg_email: st.session_state.reg_step = 1; st.rerun()
                with st.container(border=True):
                    st.markdown('<span class="step-badge">STEP 3 / 3　アカウント設定</span>', unsafe_allow_html=True)
                    st.markdown("#### プロフィールとパスワードを設定")
                    st.success(f"✅ {reg_email} の確認が完了しました")
                    display_name = st.text_input("表示名", placeholder="山田 太郎", key="reg_name")
                    new_pass  = st.text_input("パスワード（6文字以上）", type="password", key="reg_pass1")
                    new_pass2 = st.text_input("パスワード（確認）", type="password", key="reg_pass2")
                    if st.button("登録を完了する", type="primary", use_container_width=True, key="reg_finish"):
                        if not display_name: st.error("表示名を入力してください")
                        elif len(new_pass) < 6: st.error("パスワードは6文字以上で設定してください")
                        elif new_pass != new_pass2: st.error("パスワードが一致しません")
                        else:
                            if db_create_user(reg_email, new_pass, display_name):
                                st.session_state.update(
                                    authenticated=True, my_name=display_name,
                                    current_user={'email': reg_email, 'display_name': display_name, 'is_admin': False},
                                )
                                st.session_state.pop("reg_email", None)
                                st.session_state.reg_step = 1
                                st.success("登録が完了しました！ようこそ！")
                                time.sleep(0.6); st.rerun()
                            else:
                                st.error("登録に失敗しました。このメールアドレスはすでに使用されている可能性があります。")


# ─────────────────────────────────────────────
# 管理者：ユーザー管理パネル
# ─────────────────────────────────────────────

def show_user_management_panel():
    st.markdown("### 👥 ユーザー管理")
    with st.expander("📋 ユーザー一覧", expanded=True):
        users = db_list_users()
        if not users:
            st.info("登録ユーザーがいません")
        else:
            for u in sorted(users, key=lambda x: x['created_at']):
                is_self = u['email'] == st.session_state.current_user['email']
                admin_tag = '<span class="user-row-admin">👑 管理者</span>' if u['is_admin'] else ""
                name = u['display_name']
                email = u['email']
                date = u['created_at'][:10]
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    html = (
                        '<div class="user-row-card">'
                        f'<span class="user-row-name">{name}</span>'
                        f'<span class="user-row-email">{email}</span>'
                        '<span class="user-row-meta">'
                        + admin_tag +
                        f'<span class="user-row-date">登録: {date}</span>'
                        '</span>'
                        '</div>'
                    )
                    st.markdown(html, unsafe_allow_html=True)
                with col_del:
                    st.markdown("<div style='margin-top:0.5rem'></div>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"del_{email}", disabled=is_self,
                                 help="自分自身は削除できません" if is_self else "このユーザーを削除"):
                        if db_delete_user(email): st.success(f"{name} を削除しました"); st.rerun()
                        else: st.error("削除に失敗しました")

    with st.expander("🔑 パスワードをリセット"):
        users_list = db_list_users()
        if users_list:
            options = {f"{u['display_name']} ({u['email']})": u['email'] for u in users_list}
            tgt = options[st.selectbox("対象ユーザー", list(options.keys()), key="pw_target")]
            pw1 = st.text_input("新しいパスワード", type="password", key="new_pw1")
            pw2 = st.text_input("確認（再入力）", type="password", key="new_pw2")
            if st.button("パスワードをリセット", use_container_width=True):
                if not pw1: st.error("パスワードを入力してください")
                elif pw1 != pw2: st.error("パスワードが一致しません")
                elif len(pw1) < 6: st.error("6文字以上で設定してください")
                elif db_update_password(tgt, pw1): st.success("パスワードをリセットしました")
                else: st.error("リセットに失敗しました")

    with st.expander("✏️ 表示名を変更"):
        users_list2 = db_list_users()
        if users_list2:
            opts2 = {f"{u['display_name']} ({u['email']})": u['email'] for u in users_list2}
            tgt2 = opts2[st.selectbox("対象ユーザー", list(opts2.keys()), key="rename_target")]
            new_name = st.text_input("新しい表示名", key="new_display_name")
            if st.button("変更する", use_container_width=True):
                if not new_name: st.error("表示名を入力してください")
                elif db_update_display_name(tgt2, new_name): st.success("表示名を変更しました")
                else: st.error("変更に失敗しました")


# ─────────────────────────────────────────────
# AIツールランチャー（サイドバー）
# ─────────────────────────────────────────────

def show_ai_launcher():
    tools = [
        ("🤝", "RelationAI",    "人間関係サポート",  "https://relationai-one.vercel.app/"),
        ("🍳", "冷蔵庫レシピ生成", "AIレシピ自動作成",  "https://recipe-rust-six.vercel.app/"),
        ("🧠", "AIクイズアプリ",  "知識を試そう！",    "https://ai-quiz-app1.vercel.app/"),
    ]
    html = '<span class="launcher-label">🚀 AIツール</span>'
    for emoji, title, sub, url in tools:
        html += f"""
        <a class="ai-card" href="{url}" target="_blank" rel="noopener">
            <span class="ai-card-emoji">{emoji}</span>
            <span class="ai-card-body">
                <span class="ai-card-title">{title}</span>
                <span class="ai-card-sub">{sub}</span>
            </span>
            <span class="ai-card-arrow">↗</span>
        </a>"""
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ルーム関数
# ─────────────────────────────────────────────

def load_from_aws():
    try:
        table = tbl_rooms()
        resp = table.get_item(Key={'item_id': 'config_master'})
        if 'Item' in resp:
            st.session_state.admin_urls = resp['Item'].get('admin_urls', st.session_state.admin_urls)
            st.session_state.custom_exams = resp['Item'].get('custom_exams', {})
        new_rooms = {}
        for item in table.scan().get('Items', []):
            if item['item_id'].startswith('room_'):
                exam_name = item['item_id'].split('_')[1]
                new_rooms.setdefault(exam_name, []).append({
                    "id": item['item_id'], "url": item['url'],
                    "created_at": datetime.fromisoformat(item['created_at']),
                    "host": item.get('host', '匿名')
                })
        st.session_state.rooms = new_rooms
    except: pass

def save_config_to_aws():
    try:
        tbl_rooms().put_item(Item={
            'item_id': 'config_master',
            'admin_urls': st.session_state.admin_urls,
            'custom_exams': st.session_state.custom_exams
        })
    except: pass

def create_new_room(exam_name, url, user_name):
    try:
        tbl_rooms().put_item(Item={
            'item_id': f"room_{exam_name}_{int(time.time())}",
            'url': url, 'created_at': datetime.now().isoformat(),
            'host': user_name or "匿名"
        })
    except: pass

def is_url_valid(url):
    return url.startswith("http://") or url.startswith("https://")


# ─────────────────────────────────────────────
# 初期化
# ─────────────────────────────────────────────

EXAMS_DEFAULT = {
    "G検定":  {"icon": "🤖", "description": "AIの基礎知識・理論"},
    "E資格":  {"icon": "⚡", "description": "ディープラーニング実装"},
    "AWS資格": {"icon": "☁️", "description": "AWSクラウド設計・運用"},
}

def init_state():
    for k, v in {
        "authenticated": False, "current_user": None,
        "reg_step": 1, "reg_email": None, "rooms": {},
        "my_name": "", "custom_exams": {},
        "admin_urls": {k: "" for k in EXAMS_DEFAULT},
        "last_refresh": datetime.now(),
    }.items():
        if k not in st.session_state: st.session_state[k] = v
    if "db_loaded" not in st.session_state:
        load_from_aws(); st.session_state.db_loaded = True

def get_all_exams():
    return {**EXAMS_DEFAULT, **st.session_state.custom_exams}


# ─────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────
init_state()

if not st.session_state.authenticated:
    show_auth_page()
    st.stop()

# ─────────────────────────────────────────────
# メイン画面
# ─────────────────────────────────────────────
current_user = st.session_state.current_user
is_admin = current_user.get('is_admin', False)

# ── サイドバー ──
with st.sidebar:
    admin_pill = '<br><span class="admin-pill">👑 管理者</span>' if is_admin else ""
    st.markdown(f"""
    <div class="user-section">
        <div class="user-avatar">👤</div>
        <div class="user-name">{current_user['display_name']}</div>
        <div class="user-email">{current_user['email']}</div>
        {admin_pill}
    </div>""", unsafe_allow_html=True)

    if st.button("🚪 ログアウト", use_container_width=True):
        for k in ["authenticated","current_user","db_loaded","rooms",
                  "custom_exams","admin_urls","last_refresh","my_name","reg_step","reg_email"]:
            st.session_state.pop(k, None)
        st.rerun()

    st.divider()
    show_ai_launcher()
    st.divider()

    st.markdown("### ➕ 検定を追加")
    with st.expander("カスタム検定を追加"):
        new_exam_name = st.text_input("検定名")
        new_exam_icon = st.selectbox("アイコン", ["📊","💻","📝","🔬","💡","🎯","🏆","📐"])
        if st.button("追加する", type="primary", use_container_width=True):
            if new_exam_name:
                st.session_state.custom_exams[new_exam_name] = {"icon": new_exam_icon, "description": "カスタム検定"}
                st.session_state.admin_urls.setdefault(new_exam_name, "")
                save_config_to_aws(); st.rerun()

    if is_admin:
        st.divider()
        st.markdown("### ⚙️ 設定")
        with st.expander("デフォルトURLを設定"):
            all_exams_sb = get_all_exams()
            for ename in all_exams_sb:
                st.text_input(f"{all_exams_sb[ename]['icon']} {ename}",
                              value=st.session_state.admin_urls.get(ename, ""),
                              key=f"input_admin_{ename}")
            if st.button("設定を保存", use_container_width=True):
                for ename in all_exams_sb:
                    st.session_state.admin_urls[ename] = st.session_state[f"input_admin_{ename}"]
                save_config_to_aws(); st.success("AWSに保存しました！"); st.rerun()

    st.divider()
    auto_refresh = st.toggle("🔄 自動更新（30秒）", value=False)
    if auto_refresh:
        if (datetime.now() - st.session_state.last_refresh).seconds >= 30:
            st.session_state.last_refresh = datetime.now(); st.rerun()
        time.sleep(1); st.rerun()

# ── メインコンテンツ ──
st.markdown("""
<div class="main-header">
    <h1>📚 StudyConnect</h1>
    <p>仲間と繋がる学習ルーム共有プラットフォーム</p>
</div>""", unsafe_allow_html=True)

load_from_aws()
all_exams  = get_all_exams()
exam_names = list(all_exams.keys())

if is_admin:
    all_tabs  = st.tabs([f"{all_exams[n]['icon']} {n}" for n in exam_names] + ["🛡️ ユーザー管理"])
    exam_tabs = all_tabs[:-1]; admin_tab = all_tabs[-1]
else:
    exam_tabs = st.tabs([f"{all_exams[n]['icon']} {n}" for n in exam_names])
    admin_tab = None

for idx, exam_name in enumerate(exam_names):
    with exam_tabs[idx]:
        rooms_list = st.session_state.rooms.get(exam_name, [])
        col_left, col_right = st.columns([2, 1], gap="large")

        with col_left:
            st.markdown(f'<div class="section-title">🟢 {exam_name} のルーム一覧</div>', unsafe_allow_html=True)
            if not rooms_list:
                st.markdown("""
                <div class="empty-state">
                    <div class="empty-state-icon">🏠</div>
                    <div class="empty-state-title">まだルームがありません</div>
                    <div class="empty-state-sub">右側のフォームから新しいルームを追加してみましょう</div>
                </div>""", unsafe_allow_html=True)
            else:
                for room in rooms_list:
                    st.markdown(f"""
                    <div class="room-card">
                        <div class="room-card-host">👋 {room['host']} のルーム</div>
                        <div class="room-url-box">
                            <a href="{room['url']}" target="_blank">{room['url']}</a>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    st.link_button("🚀 通話に参加する", room['url'], type="primary", use_container_width=True)

        with col_right:
            st.markdown('<div class="add-panel-wrap">', unsafe_allow_html=True)
            st.markdown('<div class="add-room-title">🏰 ルームを追加</div>', unsafe_allow_html=True)
            st.markdown('<div class="add-room-sub">通話URLを貼り付けて公開しよう</div>', unsafe_allow_html=True)
            url_input = st.text_input("URL", value="", placeholder="https://zoom.us/j/...",
                                      key=f"url_{exam_name}", label_visibility="collapsed")
            if st.button("✅ ルームを公開", key=f"create_{exam_name}", type="primary", use_container_width=True):
                if is_url_valid(url_input):
                    create_new_room(exam_name, url_input, st.session_state.my_name)
                    st.balloons(); st.rerun()
                else:
                    st.error("有効なURLを入力してください（http / https）")
            st.markdown('</div>', unsafe_allow_html=True)

if admin_tab:
    with admin_tab:
        show_user_management_panel()

st.markdown('<div style="text-align:center;color:#71767b;font-size:0.8rem;padding:2rem 0 1rem;">📚 StudyConnect — 閲覧者が自由にルームを追加・共有できます</div>', unsafe_allow_html=True)
