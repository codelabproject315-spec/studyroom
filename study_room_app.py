"""
StudyConnect - メール確認付き登録 + パスワードログイン版（UI全面刷新・サイドバー修正版）
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

    /* ── ブラウザUIツールバー類を非表示（サイドバーボタンは残す） ── */
    #MainMenu { display: none !important; }
    .stDeployButton { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    footer { visibility: hidden !important; display: none !important; }
    ._profileContainer_gzau3_53 { display: none !important; }
    .viewerBadge_container__r5tak { display: none !important; }
    .viewerBadge_link__qRIco { display: none !important; }
    button[title="View fullscreen"] { display: none !important; }
    button[title="Share"] { display: none !important; }
    button[aria-label="Share"] { display: none !important; }
    [data-testid="manage-app-button"] { display: none !important; }

    /* サイドバーを開くボタンが含まれるヘッダーを透明化してボタンだけ残す */
    header[data-testid="stHeader"] { 
        background-color: rgba(0,0,0,0) !important; 
        color: #e7e9ea !important;
    }
    
    [data-testid="baseButton-headerNoPadding"] { display: flex !important; } /* ボタンを表示 */
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
    [data-testid="stExpander"] *,
    [data-testid="stExpander"] details,
    [data-testid="stExpanderDetails"] {
        background-color: #16181c !important;
        color: #e7e9ea !important;
    }

    /* サイドバー内 expander */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: #0d0d0d !important;
        border: 1px solid #2f3336 !important;
        border-radius: 12px !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] * {
        background-color: #0d0d0d !important;
        color: #e8e8f0 !important;
    }

    /* ── テキスト入力（全域ダーク）── */
    input, textarea {
        background: #000000 !important;
        color: #e7e9ea !important;
        border-color: #2f3336 !important;
    }
    .stTextInput input, [data-testid="stTextInput"] input {
        background: #000000 !important;
        border: 1px solid #2f3336 !important;
        color: #e7e9ea !important;
        border-radius: 8px !important;
    }

    /* ── ログイン ── */
    .login-title { text-align: center; font-size: 1.8rem; font-weight: 900; color: #e7e9ea; margin-bottom: 0.3rem; }
    .login-subtitle { text-align: center; color: #71767b; font-size: 0.9rem; }

    /* ── タブ ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #16181c; border-radius: 12px; padding: 4px; gap: 2px;
        border: 1px solid #2f3336;
    }
    .stTabs [aria-selected="true"] {
        background: #e7e9ea !important; color: #000000 !important;
    }

    /* ── ボタン ── */
    .stButton > button[kind="primary"] {
        background: #e7e9ea !important; color: #000000 !important;
        border: none !important; border-radius: 10px !important; font-weight: 700 !important;
    }
    .stButton > button:not([kind="primary"]) {
        background: #16181c !important; color: #e7e9ea !important;
        border: 1px solid #2f3336 !important; border-radius: 10px !important;
    }

    .stMarkdown p, .stMarkdown li, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
        color: #e7e9ea !important;
    }
    label { color: #e7e9ea !important; }
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
    except: return False


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
                    else:
                        with st.spinner("認証中..."):
                            user = authenticate(norm_email(email), password)
                        if user:
                            st.session_state.update(authenticated=True, current_user=user, my_name=user['display_name'])
                            st.rerun()
                        else:
                            st.error("認証に失敗しました")

        with tab_reg:
            step = st.session_state.get("reg_step", 1)
            if step == 1:
                with st.container(border=True):
                    st.markdown("#### メールアドレスを入力")
                    reg_email = st.text_input("メールアドレス", placeholder="you@example.com", key="reg_email_input")
                    if st.button("確認コードを送信", type="primary", use_container_width=True):
                        e = norm_email(reg_email)
                        if valid_email(e) and not db_get_user(e):
                            code = generate_otp(); save_otp(e, code)
                            if send_otp_email(e, code):
                                st.session_state.reg_step = 2; st.session_state.reg_email = e
                                st.rerun()

            elif step == 2:
                with st.container(border=True):
                    st.markdown(f"**{st.session_state.reg_email}** にコードを送信しました")
                    code_input = st.text_input("確認コード（6桁）", max_chars=6)
                    if st.button("コードを確認", type="primary", use_container_width=True):
                        if verify_otp(st.session_state.reg_email, code_input):
                            st.session_state.reg_step = 3; st.rerun()

            elif step == 3:
                with st.container(border=True):
                    st.markdown("#### アカウント設定")
                    display_name = st.text_input("表示名")
                    new_pass = st.text_input("パスワード", type="password")
                    if st.button("登録完了", type="primary", use_container_width=True):
                        if db_create_user(st.session_state.reg_email, new_pass, display_name):
                            user = {'email': st.session_state.reg_email, 'display_name': display_name, 'is_admin': False}
                            st.session_state.update(authenticated=True, current_user=user, my_name=display_name)
                            st.rerun()


# ─────────────────────────────────────────────
# 管理者：ユーザー管理パネル
# ─────────────────────────────────────────────

def show_user_management_panel():
    st.markdown("### 👥 ユーザー管理")
    users = db_list_users()
    for u in users:
        with st.container(border=True):
            st.write(f"**{u['display_name']}** ({u['email']})")
            if u['email'] != st.session_state.current_user['email']:
                if st.button("削除", key=f"del_{u['email']}"):
                    db_delete_user(u['email']); st.rerun()


# ─────────────────────────────────────────────
# AIツールランチャー
# ─────────────────────────────────────────────

def show_ai_launcher():
    tools = [
        ("🤝", "RelationAI", "人間関係サポート", "https://relationai-one.vercel.app/"),
        ("🍳", "冷蔵庫レシピ生成", "AIレシピ作成", "https://recipe-rust-six.vercel.app/"),
        ("🧠", "AIクイズアプリ", "知識を試そう！", "https://ai-quiz-app1.vercel.app/"),
    ]
    st.markdown('<span class="launcher-label">🚀 AIツール</span>', unsafe_allow_html=True)
    for emoji, title, sub, url in tools:
        st.markdown(f"""
        <a class="ai-card" href="{url}" target="_blank">
            <span class="ai-card-emoji">{emoji}</span>
            <span class="ai-card-body">
                <span class="ai-card-title">{title}</span>
                <span class="ai-card-sub">{sub}</span>
            </span>
            <span class="ai-card-arrow">↗</span>
        </a>""", unsafe_allow_html=True)


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

def delete_room(room_id):
    try: tbl_rooms().delete_item(Key={"item_id": room_id}); return True
    except: return False

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.admin_urls = {"G検定": "", "E資格": "", "AWS資格": ""}
    st.session_state.custom_exams = {}
    st.session_state.rooms = {}
    st.session_state.last_refresh = datetime.now()

if not st.session_state.authenticated:
    show_auth_page()
    st.stop()

# ── ログイン後の画面 ──
is_admin = st.session_state.current_user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"""
    <div class="user-section">
        <div class="user-avatar">👤</div>
        <div class="user-name">{st.session_state.current_user['display_name']}</div>
        <div class="user-email">{st.session_state.current_user['email']}</div>
    </div>""", unsafe_allow_html=True)
    if st.button("🚪 ログアウト", use_container_width=True):
        st.session_state.authenticated = False; st.rerun()
    st.divider()
    show_ai_launcher()

st.markdown("""
<div class="main-header">
    <h1>📚 StudyConnect</h1>
    <p>仲間と繋がる学習ルーム共有プラットフォーム</p>
</div>""", unsafe_allow_html=True)

load_from_aws()
exams = {**{"G検定": {"icon": "🤖"}, "E資格": {"icon": "⚡"}, "AWS資格": {"icon": "☁️"}}, **st.session_state.custom_exams}
tabs = st.tabs([f"{v['icon']} {k}" for k, v in exams.items()] + (["🛡️ 管理"] if is_admin else []))

for i, (name, info) in enumerate(exams.items()):
    with tabs[i]:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown(f"#### {name} のルーム")
            for r in st.session_state.rooms.get(name, []):
                with st.container(border=True):
                    st.write(f"👋 {r['host']}")
                    st.link_button("🚀 参加する", r['url'], use_container_width=True)
                    if is_admin and st.button("削除", key=f"del_r_{r['id']}"):
                        delete_room(r['id']); st.rerun()
        with col2:
            st.markdown("#### ルームを追加")
            u_input = st.text_input("URL", key=f"add_{name}")
            if st.button("公開する", key=f"btn_{name}", type="primary"):
                if u_input.startswith("http"):
                    create_new_room(name, u_input, st.session_state.my_name); st.rerun()

if is_admin:
    with tabs[-1]:
        show_user_management_panel()
