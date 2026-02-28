"""
学習ルーム共有アプリ - StudyConnect
エラー修正・完全統合版
"""

import streamlit as st
import time
from datetime import datetime
import boto3
from streamlit_google_auth import Authenticate

# ─────────────────────────────────────────────
# 0. ページ設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="StudyConnect - 一緒に勉強しよう",
    page_icon="📚",
    layout="wide"
)

# ─────────────────────────────────────────────
# 1. Google 認証設定 (Secretsの[google_auth]を直接使用)
# ─────────────────────────────────────────────
# Secretsから一括取得
google_conf = st.secrets["google_auth"]

# Authenticateのインスタンス化
# キー名は環境に合わせてフォールバックするように設定
authenticate = Authenticate(
    client_id=google_conf["client_id"],
    client_secret=google_conf["client_secret"],
    redirect_uri=google_conf["redirect_uris"][0], # リストの1番目を使用
    cookie_name='study_connect_cookie',
    cookie_key='study_connect_secret_key_2024',
    cookie_expiry_days=30,
)

# 認証メソッドの実行 (綴りの違いを吸収)
try:
    authenticate.check_authentification()
except:
    if hasattr(authenticate, 'check_authenticity'):
        authenticate.check_authenticity()

# ログインチェック
if not st.session_state.get('connected'):
    st.markdown('<div style="text-align:center; padding:2rem;"><h1>📚 StudyConnect</h1><p>ログインして学習を開始しましょう</p></div>', unsafe_allow_html=True)
    authenticate.login()
    st.stop()

# ユーザー情報の取得
user_info = st.session_state.get('user_info', {})
login_user_name = user_info.get('name', '匿名')

# ─────────────────────────────────────────────
# 2. AWS / DynamoDB 設定
# ─────────────────────────────────────────────
@st.cache_resource
def get_db_table():
    try:
        session = boto3.Session(
            aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
            region_name=st.secrets["AWS_REGION"]
        )
        return session.resource('dynamodb').Table('StudyConnect_Rooms')
    except:
        return None

table = get_db_table()

# ─────────────────────────────────────────────
# 3. メインUIロジック
# ─────────────────────────────────────────────
# サイドバー
with st.sidebar:
    if user_info.get('picture'):
        st.image(user_info['picture'], width=70)
    st.write(f"👋 こんにちは、{login_user_name} さん")
    if st.button("ログアウト", use_container_width=True):
        authenticate.logout()

st.title("📚 StudyConnect")
st.divider()

# ルーム一覧取得 (簡易化)
def load_rooms():
    if table is None: return {}
    try:
        items = table.scan().get('Items', [])
        rooms_dict = {}
        for item in items:
            iid = item.get('item_id', '')
            if iid.startswith('room_'):
                # room_検定名_timestamp から検定名を抽出
                exam = iid.split('_')[1]
                if exam not in rooms_dict: rooms_dict[exam] = []
                rooms_dict[exam].append(item)
        return rooms_dict
    except:
        return {}

all_rooms = load_rooms()
exams = {"G検定": "🤖", "E資格": "⚡", "AWS資格": "☁️"}
tabs = st.tabs([f"{v} {k}" for k, v in exams.items()])

for idx, (exam_name, icon) in enumerate(exams.items()):
    with tabs[idx]:
        rooms = all_rooms.get(exam_name, [])
        col_l, col_r = st.columns([2, 1])
        
        with col_l:
            st.subheader(f"{icon} {exam_name} 一覧")
            if not rooms:
                st.info("現在アクティブなルームはありません。")
            for r in rooms:
                with st.container(border=True):
                    st.write(f"🏠 **{r.get('host', '匿名')}** さんのルーム")
                    st.link_button("参加する🚀", r.get('url', '#'), key=f"btn_{r['item_id']}", use_container_width=True)
        
        with col_r:
            st.subheader("🏰 ルームを公開")
            u_in = st.text_input("通話URLを入力", key=f"in_{exam_name}")
            if st.button("公開する✅", key=f"pub_{exam_name}", type="primary", use_container_width=True):
                if u_in.startswith("http"):
                    rid = f"room_{exam_name}_{int(time.time())}"
                    table.put_item(Item={
                        'item_id': rid, 'url': u_in, 
                        'created_at': datetime.now().isoformat(), 'host': login_user_name
                    })
                    st.success("公開しました！")
                    time.sleep(1)
                    st.rerun()
