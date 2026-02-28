"""
学習ルーム共有アプリ - StudyConnect
KeyError解消・安定版
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
# 1. Google 認証設定 (Secretsから直接取得)
# ─────────────────────────────────────────────
# セクションの有無を問わず取得できるよう、安全な取得方法に変更
try:
    # まず [google_auth] セクションから取得を試みる
    google_conf = st.secrets.get("google_auth", st.secrets)
    
    # Secretsから値を抽出
    client_id = google_conf["client_id"]
    client_secret = google_conf["client_secret"]
    # redirect_uris がリストか単一文字列かを判別して取得
    redirect_uri = google_conf["redirect_uris"]
    if isinstance(redirect_uri, list):
        redirect_uri = redirect_uri[0]

except Exception as e:
    st.error(f"Secretsの設定が不足しています: {e}")
    st.stop()

# インスタンス化
authenticate = Authenticate(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    cookie_name='study_connect_cookie',
    key='study_connect_secret_key_2024',
    cookie_expiry_days=30,
)

# 認証チェック (綴りの揺れを吸収)
try:
    authenticate.check_authentification()
except:
    if hasattr(authenticate, 'check_authenticity'):
        authenticate.check_authenticity()

# ログインチェック
if not st.session_state.get('connected'):
    st.markdown('<div style="text-align:center; padding:2rem;"><h1>📚 StudyConnect</h1><p>ログインしてください</p></div>', unsafe_allow_html=True)
    authenticate.login()
    st.stop()

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
# 3. メインUI
# ─────────────────────────────────────────────
with st.sidebar:
    if user_info.get('picture'):
        st.image(user_info['picture'], width=70)
    st.write(f"Hi, {login_user_name}")
    if st.button("ログアウト", use_container_width=True):
        authenticate.logout()

st.title("📚 StudyConnect")
st.divider()

# ルーム取得ロジック
def load_all_rooms():
    if table is None: return {}
    try:
        items = table.scan().get('Items', [])
        rooms_by_exam = {}
        for item in items:
            iid = item.get('item_id', '')
            if iid.startswith('room_'):
                # room_検定名_timestamp
                exam = iid.split('_')[1]
                if exam not in rooms_by_exam: rooms_by_exam[exam] = []
                rooms_by_exam[exam].append(item)
        return rooms_by_exam
    except:
        return {}

current_rooms = load_all_rooms()
exams_list = {"G検定": "🤖", "E資格": "⚡", "AWS資格": "☁️"}
tabs = st.tabs([f"{v} {k}" for k, v in exams_list.items()])

for idx, (exam_name, icon) in enumerate(exams_list.items()):
    with tabs[idx]:
        rooms = current_rooms.get(exam_name, [])
        col_l, col_r = st.columns([2, 1])
        
        with col_l:
            st.subheader(f"{icon} {exam_name} 一覧")
            if not rooms:
                st.info("アクティブなルームはありません")
            for r in rooms:
                with st.container(border=True):
                    st.write(f"👋 **{r.get('host', '匿名')}** のルーム")
                    st.link_button("参加する🚀", r.get('url', '#'), key=f"btn_{r['item_id']}", use_container_width=True)
        
        with col_r:
            st.subheader("🏰 ルーム公開")
            u_in = st.text_input("URLを入力", key=f"in_{exam_name}")
            if st.button("公開✅", key=f"pub_{exam_name}", type="primary", use_container_width=True):
                if u_in.startswith("http"):
                    rid = f"room_{exam_name}_{int(time.time())}"
                    table.put_item(Item={
                        'item_id': rid, 'url': u_in, 
                        'created_at': datetime.now().isoformat(), 'host': login_user_name
                    })
                    st.rerun()
