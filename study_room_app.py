"""
学習ルーム共有アプリ - StudyConnect
同じ検定を目指す人がリアルタイムで繋がれるStreamlitアプリ
"""

import streamlit as st
from datetime import datetime, timedelta
import time
import boto3
from boto3.dynamodb.conditions import Key

# ─────────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="StudyConnect - 一緒に勉強しよう",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# カスタムCSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Noto Sans JP', sans-serif;
    }

    .main-header {
        text-align: center;
        padding: 2rem 0 1rem 0;
    }
    .main-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.3rem;
    }
    .main-header p {
        color: #666;
        font-size: 1.05rem;
    }

    .exam-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        border: 2px solid transparent;
        transition: all 0.2s ease;
    }
    .exam-card:hover {
        border-color: #6c63ff;
        box-shadow: 0 4px 20px rgba(108,99,255,0.15);
        transform: translateY(-2px);
    }
    .exam-card.active {
        border-color: #00b894;
        background: linear-gradient(135deg, #f0fff8 0%, #ffffff 100%);
    }

    .room-url-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 1.5rem;
        color: white;
        margin: 1rem 0;
        text-align: center;
    }
    .room-url-box a {
        color: #ffeaa7;
        font-weight: 700;
        font-size: 1.1rem;
        word-break: break-all;
    }

    .participants-badge {
        display: inline-block;
        background: #00b894;
        color: white;
        border-radius: 20px;
        padding: 0.2rem 0.8rem;
        font-size: 0.85rem;
        font-weight: 700;
    }
    .participants-badge.empty {
        background: #b2bec3;
    }

    .join-btn {
        width: 100%;
    }

    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# AWS / DynamoDB 設定
# ─────────────────────────────────────────────
def get_db_table():
    """DynamoDBテーブルリソースを取得"""
    try:
        session = boto3.Session(
            aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
            region_name=st.secrets["AWS_REGION"]
        )
        dynamodb = session.resource('dynamodb')
        return dynamodb.Table('StudyConnect_Rooms')
    except Exception as e:
        st.error(f"AWS接続に失敗しました。Secretsを確認してください。: {e}")
        return None

table = get_db_table()

# ─────────────────────────────────────────────
# データ管理
# ─────────────────────────────────────────────
EXAMS_DEFAULT = {
    "G検定": {"icon": "🤖", "description": "AIの基礎知識・ディープラーニングの理論", "color": "#6c63ff", "admin_url": ""},
    "E資格": {"icon": "⚡", "description": "ディープラーニングのエンジニアリング実装", "color": "#e17055", "admin_url": ""},
    "AWS資格": {"icon": "☁️", "description": "AWSクラウドサービスの設計・運用", "color": "#fd9644", "admin_url": ""},
}

def load_from_aws():
    """AWSから管理者URL、カスタム検定、ルーム情報をロード"""
    if not table:
        return
    
    try:
        # 1. マスター設定のロード
        response = table.get_item(Key={'item_id': 'config_master'})
        if 'Item' in response:
            st.session_state.admin_urls = response['Item'].get('admin_urls', st.session_state.admin_urls)
            st.session_state.custom_exams = response['Item'].get('custom_exams', {})
        
        # 2. アクティブルームのロード
        rooms_response = table.scan()
        new_rooms = {}
        for item in rooms_response.get('Items', []):
            if item['item_id'].startswith('room_'):
                exam_name = item['item_id'].replace('room_', '')
                new_rooms[exam_name] = {
                    "url": item['url'],
                    "participants": item['participants'],
                    "created_at": datetime.fromisoformat(item['created_at']),
                    "host": item['host']
                }
        st.session_state.rooms = new_rooms
    except Exception as e:
        st.error(f"データ同期エラー: {e}")

def init_state():
    """セッション状態の初期化"""
    if "rooms" not in st.session_state:
        st.session_state.rooms = {}
    if "my_name" not in st.session_state:
        st.session_state.my_name = ""
    if "my_rooms" not in st.session_state:
        st.session_state.my_rooms = set()
    if "custom_exams" not in st.session_state:
        st.session_state.custom_exams = {}
    if "admin_urls" not in st.session_state:
        st.session_state.admin_urls = {k: v["admin_url"] for k, v in EXAMS_DEFAULT.items()}
    if "last_refresh" not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    
    # 起動時に一度だけAWSから読み込み
    if "data_loaded" not in st.session_state:
        load_from_aws()
        st.session_state.data_loaded = True

def save_config_to_aws():
    """管理者設定とカスタム検定をAWSに保存"""
    if table:
        table.put_item(Item={
            'item_id': 'config_master',
            'admin_urls': st.session_state.admin_urls,
            'custom_exams': st.session_state.custom_exams
        })

def get_all_exams():
    return {**EXAMS_DEFAULT, **st.session_state.custom_exams}

def create_or_join_room(exam_name, url, user_name):
    """ルームに参加/作成し、AWSに保存"""
    if exam_name not in st.session_state.rooms:
        st.session_state.rooms[exam_name] = {
            "url": url,
            "participants": [],
            "created_at": datetime.now(),
            "host": user_name
        }
    
    room = st.session_state.rooms[exam_name]
    if user_name and user_name not in room["participants"]:
        room["participants"].append(user_name)
    
    if table:
        table.put_item(Item={
            'item_id': f'room_{exam_name}',
            'url': url,
            'participants': room["participants"],
            'created_at': room["created_at"].isoformat(),
            'host': room["host"]
        })
    st.session_state.my_rooms.add(exam_name)

def leave_room(exam_name, user_name):
    """ルームを退出"""
    if exam_name in st.session_state.rooms:
        room = st.session_state.rooms[exam_name]
        if user_name in room["participants"]:
            room["participants"].remove(user_name)
        
        if table:
            if not room["participants"]:
                table.delete_item(Key={'item_id': f'room_{exam_name}'})
                del st.session_state.rooms[exam_name]
            else:
                table.put_item(Item={
                    'item_id': f'room_{exam_name}',
                    'url': room['url'],
                    'participants': room["participants"],
                    'created_at': room["created_at"].isoformat(),
                    'host': room["host"]
                })
    st.session_state.my_rooms.discard(exam_name)

def is_url_valid(url):
    return url.startswith("http://") or url.startswith("https://")

# ─────────────────────────────────────────────
# メインアプリ実行
# ─────────────────────────────────────────────
init_state()

# ヘッダー
st.markdown("""<div class="main-header"><h1>📚 StudyConnect</h1><p>仲間と繋がる学習ルーム共有</p></div>""", unsafe_allow_html=True)
st.divider()

# サイドバー
with st.sidebar:
    st.markdown("### 👤 あなたの名前")
    st.session_state.my_name = st.text_input("ニックネーム", value=st.session_state.my_name, label_visibility="collapsed")

    st.divider()
    
    # カスタム検定追加
    st.markdown("### ➕ 検定を追加")
    with st.expander("カスタム検定を追加"):
        new_name = st.text_input("検定名")
        new_icon = st.selectbox("アイコン", ["📊", "💻", "📝", "🔬", "💡", "🎯"])
        if st.button("追加する", type="primary", use_container_width=True):
            if new_name:
                st.session_state.custom_exams[new_name] = {"icon": new_icon, "description": "カスタム検定", "color": "#a29bfe", "admin_url": ""}
                save_config_to_aws()
                st.success("追加しました！")
                st.rerun()

    st.divider()

    # ★管理者設定（修正箇所）★
    st.markdown("### ⚙️ 管理者設定")
    with st.expander("デフォルトURLを設定"):
        all_exams = get_all_exams()
        for exam_name in all_exams:
            # keyを指定して、入力を一時キーに保持
            st.text_input(
                f"{all_exams[exam_name]['icon']} {exam_name}",
                value=st.session_state.admin_urls.get(exam_name, ""),
                key=f"input_admin_{exam_name}"
            )
        
        if st.button("設定を保存", use_container_width=True):
            # 1. 一時キーからsession_state辞書に反映
            for exam_name in all_exams:
                st.session_state.admin_urls[exam_name] = st.session_state[f"input_admin_{exam_name}"]
            # 2. AWSに永久保存
            save_config_to_aws()
            st.success("AWSに保存完了！")
            st.rerun()

    st.divider()
    if st.button("🔄 データを最新に更新", use_container_width=True):
        load_from_aws()
        st.rerun()

# メインコンテンツ
all_exams = get_all_exams()
active_rooms = [(n, st.session_state.rooms[n]) for n in all_exams if n in st.session_state.rooms]

if active_rooms:
    st.markdown("### 🟢 アクティブなルーム")
    for exam_name, room in active_rooms:
        exam = all_exams[exam_name]
        st.markdown(f"""<div class="exam-card active"><strong>{exam['icon']} {exam_name}</strong><div class="room-url-box"><a href="{room['url']}" target="_blank">{room['url']}</a></div></div>""", unsafe_allow_html=True)
        if st.button("退出する", key=f"leave_{exam_name}"):
            leave_room(exam_name, st.session_state.my_name)
            st.rerun()

st.divider()
st.markdown("### 📋 検定一覧")
cols = st.columns(2)
for i, (exam_name, exam) in enumerate(all_exams.items()):
    with cols[i % 2]:
        is_active = exam_name in st.session_state.rooms
        st.markdown(f"""<div class="exam-card"><strong>{exam['icon']} {exam_name}</strong><br><small>{exam['description']}</small></div>""", unsafe_allow_html=True)
        
        if not is_active:
            with st.expander("📢 ルームを作成"):
                default_url = st.session_state.admin_urls.get(exam_name, "")
                if default_url:
                    st.info(f"デフォルトURL: {default_url}")
                    use_def = st.checkbox("このURLを使う", value=True, key=f"def_{exam_name}")
                    url = default_url if use_def else st.text_input("別URL", key=f"custom_{exam_name}")
                else:
                    url = st.text_input("URLを入力", key=f"new_url_{exam_name}")
                
                if st.button("作成", key=f"btn_{exam_name}"):
                    if is_url_valid(url):
                        create_or_join_room(exam_name, url, st.session_state.my_name)
                        st.rerun()
                    else:
                        st.error("有効なURLを入力してください")
