"""
StudyConnect - メール確認付き登録 + パスワードログイン版

認証フロー:
  【登録】メールアドレス入力 → OTP送信 → コード確認 → パスワード設定 → 登録完了
  【ログイン】メールアドレス + パスワード → 認証完了

DynamoDB テーブル:
  StudyConnect_Rooms  (既存) PK: item_id
  StudyConnect_Users  (既存 or 新規) PK: email
    Attributes: password_hash, display_name, is_admin, created_at, verified
  StudyConnect_OTP    (新規) PK: email
    Attributes: code, expires_at, expires_at_ttl
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
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }

    .main-header { text-align: center; padding: 2rem 0 1rem 0; }
    .main-header h1 { font-size: 2.5rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.3rem; }

    .login-title { text-align: center; font-size: 1.8rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.3rem; }
    .login-subtitle { text-align: center; color: #888; font-size: 0.95rem; }

    .otp-hint {
        background: #f0f7ff; border: 1px solid #c8e0ff; border-radius: 10px;
        padding: 0.8rem 1rem; margin-bottom: 1rem; font-size: 0.9rem; color: #2563eb;
    }
    .step-badge {
        display: inline-block; background: #667eea; color: white;
        border-radius: 20px; padding: 0.15rem 0.7rem; font-size: 0.75rem;
        font-weight: 600; margin-bottom: 0.5rem;
    }

    .exam-card {
        background: white; border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07); border: 2px solid transparent;
    }
    .exam-card.active { border-color: #00b894; background: linear-gradient(135deg, #f0fff8 0%, #fff 100%); }

    .room-url-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px; padding: 1.2rem; color: white; margin: 1rem 0; text-align: center;
    }
    .room-url-box a { color: #ffeaa7; font-weight: 700; word-break: break-all; }

    .user-badge {
        display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; border-radius: 20px; padding: 0.3rem 1rem; font-size: 0.85rem; font-weight: 600;
    }
    .admin-badge {
        display: inline-block; background: linear-gradient(135deg, #f39c12 0%, #e74c3c 100%);
        color: white; border-radius: 20px; padding: 0.2rem 0.7rem;
        font-size: 0.75rem; font-weight: 600; margin-left: 0.4rem; vertical-align: middle;
    }
    footer { visibility: hidden; }
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


def tbl_rooms():
    return get_dynamodb().Table('StudyConnect_Rooms')

def tbl_users():
    return get_dynamodb().Table('StudyConnect_Users')

def tbl_otp():
    return get_dynamodb().Table('StudyConnect_OTP')


# ─────────────────────────────────────────────
# ユーティリティ
# ─────────────────────────────────────────────

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def valid_email(email: str) -> bool:
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))

def norm_email(email: str) -> str:
    return email.lower().strip()


# ─────────────────────────────────────────────
# OTP
# ─────────────────────────────────────────────

OTP_EXPIRE_MINUTES = 10


def generate_otp() -> str:
    return ''.join(random.choices(string.digits, k=6))


def save_otp(email: str, code: str):
    expires = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    tbl_otp().put_item(Item={
        'email': email,
        'code': code,
        'expires_at': expires.isoformat(),
        'expires_at_ttl': int(expires.timestamp()),  # DynamoDB TTL用
    })


def verify_otp(email: str, input_code: str) -> bool:
    try:
        resp = tbl_otp().get_item(Key={'email': email})
        item = resp.get('Item')
        if not item:
            return False
        if item['code'] != input_code.strip():
            return False
        if datetime.utcnow() > datetime.fromisoformat(item['expires_at']):
            return False
        tbl_otp().delete_item(Key={'email': email})  # 使い捨て
        return True
    except Exception:
        return False


def send_otp_email(email: str, code: str, purpose: str = "メール確認") -> bool:
    """GmailのSMTPでOTPメールを送信する。"""
    subject = f"【StudyConnect】{purpose}コード"
    body_html = f"""
<div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:2rem;">
  <h2 style="color:#1a1a2e;">📚 StudyConnect</h2>
  <p>{purpose}のためのコードをお送りします。</p>
  <div style="background:#f0f7ff;border-radius:12px;padding:1.5rem;text-align:center;margin:1.5rem 0;">
    <span style="font-size:2.5rem;font-weight:700;letter-spacing:0.3rem;color:#2563eb;">{code}</span>
  </div>
  <p style="color:#666;font-size:0.9rem;">このコードは <strong>{OTP_EXPIRE_MINUTES}分間</strong> 有効です。<br>
  身に覚えのない場合は無視してください。</p>
</div>"""
    body_text = f"{purpose}コード: {code}\n{OTP_EXPIRE_MINUTES}分以内に入力してください。"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = email
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html",  "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASS)
            smtp.sendmail(GMAIL_ADDRESS, email, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        st.error("Gmail認証エラー: アプリパスワードを確認してください")
        return False
    except Exception as e:
        st.error(f"メール送信エラー: {e}")
        return False


# ─────────────────────────────────────────────
# ユーザー CRUD
# ─────────────────────────────────────────────

def db_get_user(email: str):
    try:
        return tbl_users().get_item(Key={'email': email}).get('Item')
    except Exception:
        return None


def db_create_user(email: str, password: str, display_name: str, is_admin: bool = False) -> bool:
    if db_get_user(email):
        return False
    try:
        tbl_users().put_item(Item={
            'email': email,
            'password_hash': hash_password(password),
            'display_name': display_name,
            'is_admin': is_admin,
            'verified': True,
            'created_at': datetime.now().isoformat(),
        })
        return True
    except Exception:
        return False


def db_delete_user(email: str) -> bool:
    try:
        tbl_users().delete_item(Key={'email': email})
        return True
    except Exception:
        return False


def db_list_users() -> list:
    try:
        items = tbl_users().scan().get('Items', [])
        return [
            {
                'email': u['email'],
                'display_name': u.get('display_name', u['email']),
                'is_admin': u.get('is_admin', False),
                'created_at': u.get('created_at', ''),
            }
            for u in items
        ]
    except Exception:
        return []


def db_update_password(email: str, new_password: str) -> bool:
    try:
        tbl_users().update_item(
            Key={'email': email},
            UpdateExpression='SET password_hash = :h',
            ExpressionAttributeValues={':h': hash_password(new_password)}
        )
        return True
    except Exception:
        return False


def db_update_display_name(email: str, display_name: str) -> bool:
    try:
        tbl_users().update_item(
            Key={'email': email},
            UpdateExpression='SET display_name = :n',
            ExpressionAttributeValues={':n': display_name}
        )
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# 認証
# ─────────────────────────────────────────────

def authenticate(email: str, password: str):
    user = db_get_user(email)
    if user and user.get('password_hash') == hash_password(password):
        return {
            'email': user['email'],
            'display_name': user.get('display_name', email),
            'is_admin': user.get('is_admin', False),
        }
    return None


# ─────────────────────────────────────────────
# ログイン / 新規登録 画面
# ─────────────────────────────────────────────

def show_auth_page():
    st.markdown("""
    <div style="text-align:center; padding: 3rem 0 1rem 0;">
        <div style="font-size:3.5rem; margin-bottom:0.5rem;">📚</div>
        <div class="login-title">StudyConnect</div>
        <div class="login-subtitle">仲間と繋がる学習ルーム共有</div>
    </div>
    """, unsafe_allow_html=True)

    col_l, col_form, col_r = st.columns([1, 1.4, 1])
    with col_form:
        # ログイン / 新規登録 タブ切り替え
        tab_login, tab_register = st.tabs(["🔐 ログイン", "✉️ 新規登録"])

        # ──── ログインタブ ────
        with tab_login:
            with st.container(border=True):
                email = st.text_input("メールアドレス", placeholder="you@example.com", key="li_email")
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
                            st.session_state.authenticated = True
                            st.session_state.current_user = user
                            st.session_state.my_name = user['display_name']
                            st.success(f"ようこそ、{user['display_name']} さん！")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error("メールアドレスまたはパスワードが正しくありません")

        # ──── 新規登録タブ ────
        with tab_register:
            reg_step = st.session_state.get("reg_step", 1)

            # STEP 1: メールアドレス入力
            if reg_step == 1:
                with st.container(border=True):
                    st.markdown('<span class="step-badge">STEP 1 / 3　メール確認</span>', unsafe_allow_html=True)
                    st.markdown("#### メールアドレスを入力")
                    reg_email = st.text_input("メールアドレス", placeholder="you@example.com", key="reg_email_input")

                    if st.button("確認コードを送信", type="primary", use_container_width=True, key="reg_send"):
                        e = norm_email(reg_email)
                        if not reg_email:
                            st.error("メールアドレスを入力してください")
                        elif not valid_email(e):
                            st.error("有効なメールアドレスを入力してください")
                        elif db_get_user(e):
                            st.error("このメールアドレスはすでに登録されています")
                        else:
                            code = generate_otp()
                            save_otp(e, code)
                            with st.spinner("送信中..."):
                                ok = send_otp_email(e, code, "メール確認")
                            if ok:
                                st.session_state.reg_step = 2
                                st.session_state.reg_email = e
                                st.rerun()

            # STEP 2: OTPコード確認
            elif reg_step == 2:
                reg_email = st.session_state.reg_email
                with st.container(border=True):
                    st.markdown('<span class="step-badge">STEP 2 / 3　コード確認</span>', unsafe_allow_html=True)
                    st.markdown(f"""
                    <div class="otp-hint">
                        📨 <strong>{reg_email}</strong> に確認コードを送信しました。<br>
                        {OTP_EXPIRE_MINUTES}分以内に入力してください。
                    </div>
                    """, unsafe_allow_html=True)

                    code_input = st.text_input("確認コード（6桁）", placeholder="123456",
                                               max_chars=6, key="reg_code")

                    col_ok, col_back = st.columns([2, 1])
                    with col_ok:
                        if st.button("コードを確認", type="primary", use_container_width=True, key="reg_verify"):
                            if not code_input:
                                st.error("確認コードを入力してください")
                            elif verify_otp(reg_email, code_input):
                                st.session_state.reg_step = 3
                                st.rerun()
                            else:
                                st.error("コードが正しくないか、有効期限切れです")
                    with col_back:
                        if st.button("← 戻る", use_container_width=True, key="reg_back2"):
                            st.session_state.reg_step = 1
                            st.rerun()

                    if st.button("コードを再送信", use_container_width=True, key="reg_resend"):
                        code = generate_otp()
                        save_otp(reg_email, code)
                        with st.spinner("再送信中..."):
                            send_otp_email(reg_email, code, "メール確認")
                        st.success("新しいコードを送信しました")

            # STEP 3: プロフィール & パスワード設定
            elif reg_step == 3:
                reg_email = st.session_state.get("reg_email")
                if not reg_email:
                    # reg_email が消えていたら STEP1 に戻す
                    st.session_state.reg_step = 1
                    st.rerun()
                with st.container(border=True):
                    st.markdown('<span class="step-badge">STEP 3 / 3　アカウント設定</span>', unsafe_allow_html=True)
                    st.markdown("#### プロフィールとパスワードを設定")
                    st.success(f"✅ {reg_email} の確認が完了しました")

                    display_name = st.text_input("表示名", placeholder="山田 太郎", key="reg_name")
                    new_pass = st.text_input("パスワード（6文字以上）", type="password", key="reg_pass1")
                    new_pass2 = st.text_input("パスワード（確認）", type="password", key="reg_pass2")

                    if st.button("登録を完了する", type="primary", use_container_width=True, key="reg_finish"):
                        if not display_name:
                            st.error("表示名を入力してください")
                        elif len(new_pass) < 6:
                            st.error("パスワードは6文字以上で設定してください")
                        elif new_pass != new_pass2:
                            st.error("パスワードが一致しません")
                        else:
                            ok = db_create_user(reg_email, new_pass, display_name)
                            if ok:
                                # 登録完了 → そのままログイン状態へ
                                st.session_state.authenticated = True
                                st.session_state.current_user = {
                                    'email': reg_email,
                                    'display_name': display_name,
                                    'is_admin': False,
                                }
                                st.session_state.my_name = display_name
                                # reg_email を先にクリアしてから step をリセット
                                st.session_state.pop("reg_email", None)
                                st.session_state.reg_step = 1
                                st.success("登録が完了しました！ようこそ！")
                                time.sleep(0.6)
                                st.rerun()
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
                col_info, col_del = st.columns([4, 1])
                with col_info:
                    admin_tag = "　🔴 管理者" if u['is_admin'] else ""
                    st.markdown(
                        f"**{u['display_name']}** `{u['email']}`{admin_tag}  \n"
                        f"<span style='color:#aaa;font-size:0.8rem;'>登録: {u['created_at'][:10]}</span>",
                        unsafe_allow_html=True
                    )
                with col_del:
                    is_self = u['email'] == st.session_state.current_user['email']
                    if st.button("削除", key=f"del_{u['email']}", disabled=is_self,
                                 help="自分自身は削除できません" if is_self else "削除"):
                        if db_delete_user(u['email']):
                            st.success(f"{u['display_name']} を削除しました")
                            st.rerun()
                        else:
                            st.error("削除に失敗しました")
                st.divider()

    with st.expander("🔑 パスワードをリセット"):
        st.caption("ユーザーが自分でパスワードを変更できない場合に管理者が対応します。")
        users_list = db_list_users()
        if users_list:
            options = {f"{u['display_name']} ({u['email']})": u['email'] for u in users_list}
            target_label = st.selectbox("対象ユーザー", list(options.keys()), key="pw_target")
            target_email = options[target_label]
            new_pw1 = st.text_input("新しいパスワード", type="password", key="new_pw1")
            new_pw2 = st.text_input("確認（再入力）", type="password", key="new_pw2")
            if st.button("パスワードをリセット", use_container_width=True):
                if not new_pw1:
                    st.error("パスワードを入力してください")
                elif new_pw1 != new_pw2:
                    st.error("パスワードが一致しません")
                elif len(new_pw1) < 6:
                    st.error("6文字以上で設定してください")
                elif db_update_password(target_email, new_pw1):
                    st.success("パスワードをリセットしました")
                else:
                    st.error("リセットに失敗しました")

    with st.expander("✏️ 表示名を変更"):
        users_list2 = db_list_users()
        if users_list2:
            options2 = {f"{u['display_name']} ({u['email']})": u['email'] for u in users_list2}
            tgt2 = st.selectbox("対象ユーザー", list(options2.keys()), key="rename_target")
            new_name = st.text_input("新しい表示名", key="new_display_name")
            if st.button("変更する", use_container_width=True):
                if not new_name:
                    st.error("表示名を入力してください")
                elif db_update_display_name(options2[tgt2], new_name):
                    st.success("表示名を変更しました")
                else:
                    st.error("変更に失敗しました")


# ─────────────────────────────────────────────
# ルーム関数（既存ロジック）
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
                    "id": item['item_id'],
                    "url": item['url'],
                    "created_at": datetime.fromisoformat(item['created_at']),
                    "host": item.get('host', '匿名')
                })
        st.session_state.rooms = new_rooms
    except Exception:
        pass


def save_config_to_aws():
    try:
        tbl_rooms().put_item(Item={
            'item_id': 'config_master',
            'admin_urls': st.session_state.admin_urls,
            'custom_exams': st.session_state.custom_exams
        })
    except Exception:
        pass


def create_new_room(exam_name, url, user_name):
    try:
        tbl_rooms().put_item(Item={
            'item_id': f"room_{exam_name}_{int(time.time())}",
            'url': url,
            'created_at': datetime.now().isoformat(),
            'host': user_name or "匿名"
        })
    except Exception:
        pass


def is_url_valid(url):
    return url.startswith("http://") or url.startswith("https://")


# ─────────────────────────────────────────────
# 初期化
# ─────────────────────────────────────────────
EXAMS_DEFAULT = {
    "G検定": {"icon": "🤖", "description": "AIの基礎知識・理論"},
    "E資格": {"icon": "⚡", "description": "ディープラーニング実装"},
    "AWS資格": {"icon": "☁️", "description": "AWSクラウド設計・運用"},
}


def init_state():
    defaults = {
        "authenticated": False,
        "current_user": None,
        "reg_step": 1,
        "reg_email": None,
        "rooms": {},
        "my_name": "",
        "custom_exams": {},
        "admin_urls": {k: "" for k in EXAMS_DEFAULT},
        "last_refresh": datetime.now(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if "db_loaded" not in st.session_state:
        load_from_aws()
        st.session_state.db_loaded = True


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
st.markdown("""<div class="main-header"><h1>📚 StudyConnect</h1><p>仲間と繋がる学習ルーム共有</p></div>""",
            unsafe_allow_html=True)
st.divider()

current_user = st.session_state.current_user
is_admin = current_user.get('is_admin', False)

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding:0.5rem 0 0.1rem 0;">
        <span class="user-badge">👤 {current_user['display_name']}</span>
    </div>
    <div style="text-align:center; color:#aaa; font-size:0.75rem; padding:0.3rem 0 0.5rem 0;">
        {current_user['email']}
    </div>
    """, unsafe_allow_html=True)

    if st.button("🚪 ログアウト", use_container_width=True):
        for k in ["authenticated", "current_user", "db_loaded", "rooms",
                  "custom_exams", "admin_urls", "last_refresh", "my_name",
                  "reg_step", "reg_email"]:
            st.session_state.pop(k, None)
        st.rerun()

    st.divider()
    st.markdown("### ➕ 検定を追加")
    with st.expander("カスタム検定を追加"):
        new_exam_name = st.text_input("検定名")
        new_exam_icon = st.selectbox("アイコン", ["📊", "💻", "📝", "🔬", "💡", "🎯", "🏆", "📐"])
        if st.button("追加する", type="primary", use_container_width=True):
            if new_exam_name:
                st.session_state.custom_exams[new_exam_name] = {"icon": new_exam_icon, "description": "カスタム検定"}
                st.session_state.admin_urls.setdefault(new_exam_name, "")
                save_config_to_aws()
                st.rerun()

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
                save_config_to_aws()
                st.success("AWSに保存しました！")
                st.rerun()

    st.divider()
    auto_refresh = st.toggle("🔄 自動更新（30秒）", value=False)
    if auto_refresh:
        elapsed = (datetime.now() - st.session_state.last_refresh).seconds
        if elapsed >= 30:
            st.session_state.last_refresh = datetime.now()
            st.rerun()
        time.sleep(1)
        st.rerun()

# ─────────────────────────────────────────────
# タブ表示
# ─────────────────────────────────────────────
load_from_aws()
all_exams = get_all_exams()
exam_names = list(all_exams.keys())

if is_admin:
    all_tabs = st.tabs([f"{all_exams[n]['icon']} {n}" for n in exam_names] + ["🛡️ ユーザー管理"])
    exam_tabs, admin_tab = all_tabs[:-1], all_tabs[-1]
else:
    exam_tabs = st.tabs([f"{all_exams[n]['icon']} {n}" for n in exam_names])
    admin_tab = None

for idx, exam_name in enumerate(exam_names):
    with exam_tabs[idx]:
        rooms_list = st.session_state.rooms.get(exam_name, [])
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.markdown(f"### 🟢 {exam_name} のルーム一覧")
            if not rooms_list:
                st.info("現在アクティブなルームはありません。右側から新しいルームを追加してください。")
            else:
                for room in rooms_list:
                    st.markdown(f"""
                    <div class="exam-card active">
                        <strong style="font-size:1.1rem;">👋 {room['host']} のルーム</strong>
                        <div class="room-url-box">
                            <a href="{room['url']}" target="_blank">{room['url']}</a>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    st.link_button("通話に参加する🚀", room['url'], type="primary", use_container_width=True)
                    st.divider()

        with col_right:
            st.markdown("#### 🏰 ルームを追加")
            with st.container(border=True):
                st.write("新しいルームを作成して共有")
                url_input = st.text_input("通話ルームURLを入力", value="",
                                           placeholder="https://...", key=f"url_{exam_name}")
                if st.button("✅ ルームを公開", key=f"create_{exam_name}",
                             type="primary", use_container_width=True):
                    if is_url_valid(url_input):
                        create_new_room(exam_name, url_input, st.session_state.my_name)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("有効なURLを入力してください")

if admin_tab:
    with admin_tab:
        show_user_management_panel()

st.divider()
st.markdown("""<div style="text-align:center;color:#aaa;font-size:0.85rem;padding:1rem 0;">
📚 StudyConnect ─ 閲覧者が自由にルームを追加・共有できます
</div>""", unsafe_allow_html=True)
