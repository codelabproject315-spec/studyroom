"""
学習ルーム共有アプリ - StudyConnect
TypeError解消・Secrets完全統合版
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
# Secretsの [google_auth] セクションから安全に取得
try:
    # 画像の通り、Secretsの直下または [google_auth] 内にある情報を取得
    google_conf = st.secrets.get("google_auth", st.secrets)
    
    # 必要な情報を抽出
    cid = google_conf["client_id"]
    csecret = google_conf["client_secret"]
    # redirect_uris はリスト形式なので最初の1つを取得
    ruri = google_conf["redirect_uris"]
    if isinstance(ruri, list):
        ruri = ruri[0]

except Exception as e:
    st.error(f"Secretsの設定を確認してください: {e}")
    st.stop()

# 【修正ポイント】引数名を 'secret_key' に修正し、TypeErrorを回避します
authenticate = Authenticate(
    client_id=cid,
    client_secret=csecret,
    redirect_uri=ruri,
    cookie_name='study_connect_cookie',
    secret_key='study_connect_secret_key_2024', # 'key' から 'secret_key' に変更
    cookie_expiry_days=30,
)

# 認証メソッドの実行 (綴りの揺れを吸収)
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

# ルーム取得
def load_rooms():
    if table is None: return {}
    try:
        items = table.scan().get('Items', [])
        rooms_dict = {}
        for item in items:
            iid = item.get('item_id', '')
            if iid.startswith('room_'):
                # room_検定名_timestamp
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
                st.info("ルームはありません")
            for r in rooms:
                with st.container(border=True):
                    st.write(f"👋 **{r.get('host', '匿名')}** さんのルーム")
                    st.link_button("参加🚀", r.get('url', '#'), key=f"btn_{r['item_id']}", use_container_width=True)
        
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
