"""
学習ルーム共有アプリ - StudyConnect
Google認証・Secrets完全統合版
"""

import streamlit as st
from streamlit_google_auth import Authenticate
from datetime import datetime
import time
import boto3
from boto3.dynamodb.conditions import Key

# ─────────────────────────────────────────────
# 1. Google 認証設定 (Secretsの[google_auth]を使用)
# ─────────────────────────────────────────────
# TypeError回避のため、ファイルを介さずSecretsの値を直接個別の引数に割り当てます
google_conf = st.secrets["google_auth"]

authenticate = Authenticate(
    client_id=google_conf['client_id'],
    client_secret=google_conf['client_secret'],
    redirect_uri=google_conf['redirect_uris'][0],
    cookie_name='study_connect_cookie',
    key='some_signature_key',
    cookie_expiry_days=30
)

# 認証チェック
authenticate.check_authenticity()

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
user_info = st.session_state['user_info']
login_user_name = user_info.get('name', '匿名')

# ─────────────────────────────────────────────
# 2. ページ設定・CSS
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
    .main-header { text-align: center; padding: 1rem 0; }
    .main-header h1 { font-size: 2.5rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.3rem; }
    .exam-card { background: white; border-radius: 16px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 2px 12px rgba(0,0,0,0.07); border: 2px solid transparent; }
    .exam-card.active { border-color: #00b894; background: linear-gradient(135deg, #f0fff8 0%, #ffffff 100%); }
    .room-url-box { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 1.2rem; color: white; margin: 1rem 0; text-align: center; }
    .room-url-box a { color: #ffeaa7; font-weight: 700; word-break: break-all; }
    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 3. AWS / DynamoDB 関数
# ─────────────────────────────────────────────
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
    if table:
        try:
            resp = table.get_item(Key={'item_id': 'config_master'})
            if 'Item' in resp:
                st.session_state.admin_urls = resp['Item'].get('admin_urls', st.session_state.admin_urls)
                st.session_state.custom_exams = resp['Item'].get('custom_exams', {})
            
            items = table.scan().get('Items', [])
            new_rooms = {}
            for item in items:
                if item['item_id'].startswith('room_'):
                    parts = item['item_id'].split('_')
                    exam_name = parts[1]
                    if exam_name not in new_rooms: new_rooms[exam_name] = []
                    new_rooms[exam_name].append({
                        "id": item['item_id'],
                        "url": item['url'],
                        "created_at": datetime.fromisoformat(item['created_at']),
                        "host": item.get('host', '匿名')
                    })
            st.session_state.rooms = new_rooms
        except: pass

def save_config_to_aws():
    if table:
        table.put_item(Item={
            'item_id': 'config_master',
            'admin_urls': st.session_state.admin_urls,
            'custom_exams': st.session_state.custom_exams
        })

# ─────────────────────────────────────────────
# 4. ロジック・初期化
# ─────────────────────────────────────────────
EXAMS_DEFAULT = {
    "G検定": {"icon": "🤖", "description": "AIの基礎知識・理論"},
    "E資格": {"icon": "⚡", "description": "ディープラーニング実装"},
    "AWS資格": {"icon": "☁️", "description": "AWSクラウド設計・運用"},
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
    """ルーム作成時にログインユーザー名を使用"""
    room_id = f"room_{exam_name}_{int(time.time())}"
    if table:
        table.put_item(Item={
            'item_id': room_id,
            'url': url,
            'created_at': datetime.now().isoformat(),
            'host': host_name
        })

def is_url_valid(url):
    return url.startswith("http://") or url.startswith("https://")

# ─────────────────────────────────────────────
# 5. サイドバー
# ─────────────────────────────────────────────
with st.sidebar:
    # Googleのプロフィール画像を表示
    st.image(user_info.get('picture', ''), width=70)
    st.success(f"ログイン中: {login_user_name} さん")
    
    if st.button("ログアウト", use_container_width=True):
        authenticate.logout()
    
    st.divider()
    st.markdown("### ➕ 検定を追加")
    with st.expander("カスタム検定を追加"):
        new_exam_name = st.text_input("検定名")
        new_exam_icon = st.selectbox("アイコン", ["📊", "💻", "📝", "🔬", "💡", "🎯", "🏆", "📐"])
        if st.button("追加する", type="primary", use_container_width=True):
            if new_exam_name:
                st.session_state.custom_exams[new_exam_name] = {"icon": new_exam_icon, "description": "カスタム検定"}
                if new_exam_name not in st.session_state.admin_urls:
                    st.session_state.admin_urls[new_exam_name] = ""
                save_config_to_aws(); st.rerun()

    st.divider()
    st.markdown("### ⚙️ 管理者設定")
    with st.expander("デフォルトURLを設定"):
        all_exams = get_all_exams()
        for exam_name in all_exams:
            st.text_input(f"{all_exams[exam_name]['icon']} {exam_name}", value=st.session_state.admin_urls.get(exam_name, ""), key=f"input_admin_{exam_name}")
        if st.button("設定を保存", use_container_width=True):
            for exam_name in all_exams:
                st.session_state.admin_urls[exam_name] = st.session_state[f"input_admin_{exam_name}"]
            save_config_to_aws(); st.success("AWSに保存しました！"); st.rerun()

# ─────────────────────────────────────────────
# 6. メインコンテンツ
# ─────────────────────────────────────────────
st.markdown("""<div class="main-header"><h1>📚 StudyConnect</h1><p>仲間と繋がる学習ルーム共有</p></div>""", unsafe_allow_html=True)
st.divider()

load_from_aws()
all_exams = get_all_exams()
exam_names = list(all_exams.keys())
tabs = st.tabs([f"{all_exams[name]['icon']} {name}" for name in exam_names])

for idx, exam_name in enumerate(exam_names):
    with tabs[idx]:
        exam = all_exams[exam_name]
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
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <strong style="font-size:1.1rem;">👋 {room['host']} のルーム</strong>
                        </div>
                        <div class="room-url-box">
                            <a href="{room['url']}" target="_blank">{room['url']}</a>
                        </div>
                    </div>""", unsafe_allow_html=True)
                    # key引数を削除してTypeErrorを防止
                    st.link_button("通話に参加する🚀", room['url'], type="primary", use_container_width=True)
                    st.divider()

        with col_right:
            st.markdown("#### 🏰 ルームを追加")
            with st.container(border=True):
                st.write("新しいルームを作成して共有")
                url_input = st.text_input("通話ルームURLを入力", value="", placeholder="https://...", key=f"url_{exam_name}")
                if st.button(f"✅ ルームを公開", key=f"create_{exam_name}", type="primary", use_container_width=True):
                    if is_url_valid(url_input):
                        # ニックネーム入力欄を廃止し、ログイン中の名前をホストとして保存
                        create_new_room(exam_name, url_input, login_user_name)
                        st.balloons(); st.rerun()
                    else:
                        st.error("有効なURLを入力してください")

st.divider()
st.markdown("""<div style="text-align:center; color:#aaa; font-size:0.85rem; padding:1rem 0;">📚 StudyConnect ─ ログインユーザー名でルームを共有中</div>""", unsafe_allow_html=True)
