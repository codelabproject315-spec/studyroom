"""
学習ルーム共有アプリ - StudyConnect
Google認証・スラッシュ不一致解消版
"""

import streamlit as st
import json
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
# 1. Google 認証設定
# ─────────────────────────────────────────────
google_conf = st.secrets["google_auth"]

# 一時的な認証用JSONの作成
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

# インスタンス化
authenticate = Authenticate(
    secret_credentials_path=CREDENTIALS_PATH,
    cookie_name='study_connect_cookie',
    cookie_key='study_connect_secret_key_2024',
    redirect_uri=list(google_conf["redirect_uris"])[0],
    cookie_expiry_days=30,
)

# 認証チェック
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

def load_from_aws():
    if table is None: return
    try:
        items = table.scan().get('Items', [])
        new_rooms = {}
        for item in items:
            iid = item.get('item_id', '')
            if iid.startswith('room_'):
                parts = iid[len('room_'):].rsplit('_', 1)
                exam_name = parts[0]
                if exam_name not in new_rooms: new_rooms[exam_name] = []
                new_rooms[exam_name].append({
                    "id": iid,
                    "url": item.get('url', ''),
                    "created_at": datetime.fromisoformat(item.get('created_at', datetime.now().isoformat())),
                    "host": item.get('host', '匿名')
                })
        st.session_state.rooms = new_rooms
    except: pass

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

load_from_aws()
exams = {"G検定": "🤖", "E資格": "⚡", "AWS資格": "☁️"}
tabs = st.tabs([f"{v} {k}" for k, v in exams.items()])

for idx, (exam_name, icon) in enumerate(exams.items()):
    with tabs[idx]:
        rooms = st.session_state.rooms.get(exam_name, [])
        col_l, col_r = st.columns([2, 1])
        
        with col_l:
            st.subheader(f"{icon} {exam_name} ルーム")
            if not rooms:
                st.info("ルームがありません")
            for r in rooms:
                with st.container(border=True):
                    st.write(f"👋 **{r['host']}** のルーム")
                    st.link_button("通話に参加🚀", r['url'], key=f"btn_{r['id']}", use_container_width=True)
        
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
