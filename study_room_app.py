"""
学習ルーム共有アプリ - StudyConnect
エラー修正・最新ライブラリ完全対応版（メソッド名修正済）
"""

import streamlit as st
import json
import time
import os
from datetime import datetime
import boto3
from streamlit_google_auth import Authenticate

# ─────────────────────────────────────────────
# 0. ページ設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="StudyConnect - 一緒に勉強しよう",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# 1. Google 認証設定
# ─────────────────────────────────────────────
google_conf = st.secrets["google_auth"]

# 一時的な認証用JSONファイルの作成
CREDENTIALS_PATH = "/tmp/google_credentials.json"
credentials_dict = {
    "web": {
        "client_id": google_conf["client_id"],
        "client_secret": google_conf["client_secret"],
        "redirect_uris": list(google_conf["redirect_uris"]),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

with open(CREDENTIALS_PATH, "w") as f:
    json.dump(credentials_dict, f)

# インスタンス化（最新の引数名を使用）
authenticate = Authenticate(
    secret_credentials_path=CREDENTIALS_PATH,
    cookie_name='study_connect_cookie',
    cookie_key='study_connect_secret_key_2024',
    redirect_uri=list(google_conf["redirect_uris"])[0],
    cookie_expiry_days=30,
)

# 【修正箇所】メソッド名を正しい綴りに変更
# ログでエラーになっていた check_authenticity() から変更しました
authenticate.check_authentification()

# ログインチェック
if not st.session_state.get('connected'):
    st.markdown("""
        <style>
            .main-header { text-align: center; padding: 2rem 0; }
            .main-header h1 { font-size: 2.5rem; color: #1a1a2e; }
        </style>
        <div class="main-header">
            <h1>📚 StudyConnect</h1>
            <p>ログインして学習を始めよう</p>
        </div>
    """, unsafe_allow_html=True)
    authenticate.login()
    st.stop()

# ログイン済みユーザー情報の取得
user_info = st.session_state.get('user_info', {})
login_user_name = user_info.get('name', '匿名')

# ─────────────────────────────────────────────
# 2. CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans JP', sans-serif; }
    .main-header { text-align: center; padding: 1rem 0; }
    .main-header h1 { font-size: 2.5rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.3rem; }
    .exam-card { background: white; border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem;
                 box-shadow: 0 2px 12px rgba(0,0,0,0.07); border: 2px solid transparent; }
    .exam-card.active { border-color: #00b894; background: linear-gradient(135deg, #f0fff8 0%, #ffffff 100%); }
    .room-url-box { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    border-radius: 12px; padding: 1.2rem; color: white; margin: 1rem 0; text-align: center; }
    .room-url-box a { color: #ffeaa7; font-weight: 700; word-break: break-all; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. AWS / DynamoDB 関数
# ─────────────────────────────────────────────
@st.cache_resource
def get_db_table():
    try:
        session = boto3.Session(
            aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
            region_name=st.secrets["AWS_REGION"]
        )
        dynamodb = session.resource('dynamodb')
        return dynamodb.Table('StudyConnect_Rooms')
    except Exception as e:
        st.error(f"AWS接続エラー: {e}")
        return None

table = get_db_table()

def load_from_aws():
    if table is None: return
    try:
        resp = table.get_item(Key={'item_id': 'config_master'})
        if 'Item' in resp:
            st.session_state.admin_urls = resp['Item'].get('admin_urls', st.session_state.get('admin_urls', {}))
            st.session_state.custom_exams = resp['Item'].get('custom_exams', {})

        items = table.scan().get('Items', [])
        new_rooms = {}
        for item in items:
            if not item['item_id'].startswith('room_'): continue
            parts = item['item_id'][len('room_'):].rsplit('_', 1)
            if len(parts) != 2: continue
            exam_name = parts[0]
            if exam_name not in new_rooms: new_rooms[exam_name] = []
            new_rooms[exam_name].append({
                "id": item['item_id'],
                "url": item['url'],
                "created_at": datetime.fromisoformat(item['created_at']),
                "host": item.get('host', '匿名')
            })
        st.session_state.rooms = new_rooms
    except Exception as e:
        st.warning(f"データ読込エラー: {e}")

def save_config_to_aws():
    if table:
        try:
            table.put_item(Item={
                'item_id': 'config_master',
                'admin_urls': st.session_state.admin_urls,
                'custom_exams': st.session_state.custom_exams
            })
        except Exception as e:
            st.error(f"設定保存エラー: {e}")

# ─────────────────────────────────────────────
# 4. ロジック・初期化
# ─────────────────────────────────────────────
EXAMS_DEFAULT = {
    "G検定":  {"icon": "🤖", "description": "AIの基礎"},
    "E資格":  {"icon": "⚡", "description": "ディープラーニング"},
    "AWS資格": {"icon": "☁️", "description": "AWS設計"},
}

if "rooms" not in st.session_state: st.session_state.rooms = {}
if "custom_exams" not in st.session_state: st.session_state.custom_exams = {}
if "admin_urls" not in st.session_state:
    st.session_state.admin_urls = {k: "" for k in EXAMS_DEFAULT.keys()}
if "db_loaded" not in st.session_state:
    load_from_aws()
    st.session_state.db_loaded = True

def get_all_exams():
    return {**EXAMS_DEFAULT, **st.session_state.custom_exams}

def create_new_room(exam_name, url, host_name):
    room_id = f"room_{exam_name}_{int(time.time())}"
    if table:
        try:
            table.put_item(Item={
                'item_id': room_id,
                'url': url,
                'created_at': datetime.now().isoformat(),
                'host': host_name
            })
        except Exception as e:
            st.error(f"ルーム作成エラー: {e}")

def is_url_valid(url):
    return url.startswith("http://") or url.startswith("https://")

# ─────────────────────────────────────────────
# 5. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    if user_info.get('picture'):
        st.image(user_info['picture'], width=70)
    st.success(f"Hi, {login_user_name}")

    if st.button("ログアウト", key="logout_btn", use_container_width=True):
        authenticate.logout()

    st.divider()
    with st.expander("➕ 検定を追加"):
        nx_name = st.text_input("検定名", key="new_ex_name")
        nx_icon = st.selectbox("アイコン", ["📊", "💻", "📝", "💡"], key="new_ex_icon")
        if st.button("追加", key="new_ex_btn", type="primary"):
            if nx_name:
                st.session_state.custom_exams[nx_name] = {"icon": nx_icon, "description": "Custom"}
                st.session_state.admin_urls[nx_name] = ""
                save_config_to_aws()
                st.rerun()

# ─────────────────────────────────────────────
# 6. メイン
# ─────────────────────────────────────────────
st.markdown('<div class="main-header"><h1>📚 StudyConnect</h1></div>', unsafe_allow_html=True)
st.divider()

load_from_aws()
all_exams = get_all_exams()
tabs = st.tabs([f"{v['icon']} {k}" for k, v in all_exams.items()])

for idx, (exam_name, info) in enumerate(all_exams.items()):
    with tabs[idx]:
        rooms_list = st.session_state.rooms.get(exam_name, [])
        col_l, col_r = st.columns([2, 1])

        with col_l:
            st.markdown(f"### 🟢 {exam_name} のルーム一覧")
            if not rooms_list:
                st.info("アクティブなルームはありません。")
            else:
                for r_idx, room in enumerate(rooms_list):
                    st.markdown(f"""
                    <div class="exam-card active">
                        <strong>👋 {room['host']} のルーム</strong>
                        <div class="room-url-box"><a href="{room['url']}" target="_blank">{room['url']}</a></div>
                    </div>""", unsafe_allow_html=True)
                    st.link_button("通話に参加する🚀", room['url'], use_container_width=True)
                    st.divider()

        with col_r:
            st.markdown("#### 🏰 ルームを追加")
            with st.container(border=True):
                d_url = st.session_state.admin_urls.get(exam_name, "")
                u_in = st.text_input("URLを入力", value=d_url, key=f"in_{exam_name}")
                if st.button("✅ 公開", key=f"pub_{exam_name}", type="primary", use_container_width=True):
                    if is_url_valid(u_in):
                        create_new_room(exam_name, u_in, login_user_name)
                        st.balloons()
                        st.rerun()
