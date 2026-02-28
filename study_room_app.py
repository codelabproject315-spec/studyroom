"""
学習ルーム共有アプリ - StudyConnect
エラー修正・最新ライブラリ完全対応版
"""

import streamlit as st
import json
import time
import os
from datetime import datetime
import boto3
from streamlit_google_auth import Authenticate

# ─────────────────────────────────────────────
# 0. ページ設定（必ず最初に呼ぶ）
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="StudyConnect - 一緒に勉強しよう",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# 1. Google 認証設定 (最新の仕様に合わせて修正)
# ─────────────────────────────────────────────
# Secretsから取得
google_conf = st.secrets["google_auth"]

# 最新版の streamlit-google-auth は JSONファイルを介すのが最も安定します
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

# インスタンス化 (引数名を最新版の 'secret_credentials_path' に修正)
authenticate = Authenticate(
    secret_credentials_path=CREDENTIALS_PATH,
    cookie_name='study_connect_cookie',
    cookie_key='study_connect_secret_key_2024',
    redirect_uri=list(google_conf["redirect_uris"])[0],
    cookie_expiry_days=30,
)

# 【重要】ライブラリのメソッド名は「check_authentification」です
# (最後のログで出ていた check_authenticity ではありません)
authenticate.check_authentification()

# ログインしていない場合はログイン画面を表示して停止
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

# ログイン済み：ユーザー情報を取得
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
    footer { visibility: hidden; }
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
            rest = item['item_id'][len('room_'):]
            parts = rest.rsplit('_', 1)
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
        st.warning(f"データ読み込みエラー: {e}")

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
    "G検定":  {"icon": "🤖", "description": "AIの基礎知識・理論"},
    "E資格":  {"icon": "⚡", "description": "ディープラーニング実装"},
    "AWS資格": {"icon": "☁️", "description": "AWSクラウド設計・運用"},
}

if "rooms"        not in st.session_state: st.session_state.rooms = {}
if "custom_exams" not in st.session_state: st.session_state.custom_exams = {}
if "admin_urls"   not in st.session_state:
    st.session_state.admin_urls = {k: "" for k in EXAMS_DEFAULT.keys()}
if "db_loaded"    not in st.session_state:
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
    picture = user_info.get('picture', '')
    if picture:
        st.image(picture, width=70)
    st.success(f"ログイン中: {login_user_name} さん")

    if st.button("ログアウト", key="logout_button", use_container_width=True):
        authenticate.logout()

    st.divider()
    st.markdown("### ➕ 検定を追加")
    with st.expander("カスタム検定を追加"):
        new_exam_name = st.text_input("検定名", key="add_exam_name")
        new_exam_icon = st.selectbox("アイコン", ["📊", "💻", "📝", "🔬", "💡", "🎯", "🏆", "📐"], key="add_exam_icon")
        if st.button("追加する", key="add_exam_submit", type="primary", use_container_width=True):
            if new_exam_name:
                st.session_state.custom_exams[new_exam_name] = {"icon": new_exam_icon, "description": "カスタム検定"}
                if new_exam_name not in st.session_state.admin_urls:
                    st.session_state.admin_urls[new_exam_name] = ""
                save_config_to_aws()
                st.rerun()

    st.divider()
    st.markdown("### ⚙️ 管理者設定")
    with st.expander("デフォルトURLを設定"):
        current_exams = get_all_exams()
        for ename in current_exams:
            st.text_input(
                f"{current_exams[ename]['icon']} {ename}",
                value=st.session_state.admin_urls.get(ename, ""),
                key=f"cfg_{ename}"
            )
        if st.button("設定を保存", key="save_admin_cfg", use_container_width=True):
            for ename in current_exams:
                st.session_state.admin_urls[ename] = st.session_state[f"cfg_{ename}"]
            save_config_to_aws()
            st.success("AWSに保存しました！")
            st.rerun()

# ─────────────────────────────────────────────
# 6. メインコンテンツ
# ─────────────────────────────────────────────
st.markdown("""<div class="main-header"><h1>📚 StudyConnect</h1><p>仲間と繋がる学習ルーム共有</p></div>""",
            unsafe_allow_html=True)
st.divider()

load_from_aws()

all_exams = get_all_exams()
exam_names = list(all_exams.keys())
tabs = st.tabs([f"{all_exams[name]['icon']} {name}" for name in exam_names])

for idx, exam_name in enumerate(exam_names):
    with tabs[idx]:
        rooms_list = st.session_state.rooms.get(exam_name, [])
        col_left, col_right = st.columns([2, 1])

        with col_left:
            st.markdown(f"### 🟢 {exam_name} のルーム一覧")
            if not rooms_list:
                st.info("現在アクティブなルームはありません。右側から新しいルームを追加してください。")
            else:
                for r_idx, room in enumerate(rooms_list):
                    st.markdown(f"""
                    <div class="exam-card active">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <strong style="font-size:1.1rem;">👋 {room['host']} のルーム</strong>
                        </div>
                        <div class="room-url-box">
                            <a href="{room['url']}" target="_blank">{room['url']}</a>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    
                    # ログの TypeError 回避: link_button に key は不要
                    st.link_button("通話に参加する🚀", room['url'], type="primary", use_container_width=True)
                    st.divider()

        with col_right:
            st.markdown("#### 🏰 ルームを追加")
            with st.container(border=True):
                st.write("新しいルームを作成して共有")
                default_url = st.session_state.admin_urls.get(exam_name, "")
                url_input = st.text_input(
                    "通話ルームURLを入力",
                    value=default_url,
                    placeholder="https://...",
                    key=f"input_url_{exam_name}"
                )
                if st.button("✅ ルームを公開", key=f"btn_pub_{exam_name}", type="primary", use_container_width=True):
                    if is_url_valid(url_input):
                        create_new_room(exam_name, url_input, login_user_name)
                        st.balloons()
                        st.rerun()
                    else:
                        st.error("有効なURLを入力してください")

st.divider()
st.markdown(
    """<div style="text-align:center; color:#aaa; font-size:0.85rem; padding:1rem 0;">
    📚 StudyConnect ─ ログインユーザー名でルームを共有中</div>""",
    unsafe_allow_html=True
)
