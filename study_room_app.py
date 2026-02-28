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

    .exam-card {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 12px rgba(0,0,0,0.07);
        border: 2px solid transparent;
        transition: all 0.2s ease;
    }
    .exam-card.active {
        border-color: #00b894;
        background: linear-gradient(135deg, #f0fff8 0%, #ffffff 100%);
    }

    .room-url-box {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 12px;
        padding: 1.2rem;
        color: white;
        margin: 1rem 0;
        text-align: center;
    }
    .room-url-box a {
        color: #ffeaa7;
        font-weight: 700;
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

    footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# AWS / DynamoDB 設定
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
                    exam_name = item['item_id'].replace('room_', '')
                    new_rooms[exam_name] = {
                        "url": item['url'],
                        "participants": item['participants'],
                        "created_at": datetime.fromisoformat(item['created_at']),
                        "host": item['host']
                    }
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
# データ初期化
# ─────────────────────────────────────────────
EXAMS_DEFAULT = {
    "G検定": {"icon": "🤖", "description": "AIの基礎知識・理論"},
    "E資格": {"icon": "⚡", "description": "ディープラーニング実装"},
    "AWS資格": {"icon": "☁️", "description": "AWSクラウド設計・運用"},
}

def init_state():
    if "rooms" not in st.session_state: st.session_state.rooms = {}
    if "my_name" not in st.session_state: st.session_state.my_name = ""
    if "my_rooms" not in st.session_state: st.session_state.my_rooms = set()
    if "custom_exams" not in st.session_state: st.session_state.custom_exams = {}
    if "admin_urls" not in st.session_state:
        st.session_state.admin_urls = {k: "" for k in EXAMS_DEFAULT.keys()}
    if "last_refresh" not in st.session_state: st.session_state.last_refresh = datetime.now()
    if "db_loaded" not in st.session_state:
        load_from_aws()
        st.session_state.db_loaded = True

def get_all_exams():
    return {**EXAMS_DEFAULT, **st.session_state.custom_exams}

def create_or_join_room(exam_name, url, user_name):
    if exam_name not in st.session_state.rooms:
        st.session_state.rooms[exam_name] = {
            "url": url, "participants": [], "created_at": datetime.now(), "host": user_name
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
    if exam_name in st.session_state.rooms:
        room = st.session_state.rooms[exam_name]
        if user_name in room["participants"]: room["participants"].remove(user_name)
        if table:
            if not room["participants"]:
                table.delete_item(Key={'item_id': f'room_{exam_name}'})
                del st.session_state.rooms[exam_name]
            else:
                table.put_item(Item={
                    'item_id': f'room_{exam_name}', 'url': room['url'],
                    'participants': room["participants"], 'created_at': room["created_at"].isoformat(), 'host': room["host"]
                })
    st.session_state.my_rooms.discard(exam_name)

def is_url_valid(url):
    return url.startswith("http://") or url.startswith("https://")

# ─────────────────────────────────────────────
# メイン
# ─────────────────────────────────────────────
init_state()

st.markdown("""<div class="main-header"><h1>📚 StudyConnect</h1><p>仲間と繋がる学習ルーム共有</p></div>""", unsafe_allow_html=True)
st.divider()

with st.sidebar:
    st.markdown("### 👤 あなたの名前")
    name_input = st.text_input("ニックネーム", value=st.session_state.my_name, placeholder="例: たろう", label_visibility="collapsed")
    if name_input != st.session_state.my_name: st.session_state.my_name = name_input
    
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
        st.caption("カンマ（,）区切りで複数のURLを追加できます")
        all_exams = get_all_exams()
        for exam_name in all_exams:
            st.text_area(f"{all_exams[exam_name]['icon']} {exam_name}", value=st.session_state.admin_urls.get(exam_name, ""), key=f"input_admin_{exam_name}", help="例: https://zoom_a, https://zoom_b")
        if st.button("設定を保存", use_container_width=True):
            for exam_name in all_exams:
                st.session_state.admin_urls[exam_name] = st.session_state[f"input_admin_{exam_name}"]
            save_config_to_aws(); st.success("AWSに保存しました！"); st.rerun()

    st.divider()
    auto_refresh = st.toggle("🔄 自動更新（30秒）", value=False)
    if auto_refresh:
        elapsed = (datetime.now() - st.session_state.last_refresh).seconds
        if elapsed >= 30:
            st.session_state.last_refresh = datetime.now(); st.rerun()
        time.sleep(1); st.rerun()

# ─────────────────────────────────────────────
# コンテンツ表示（タブ形式）
# ─────────────────────────────────────────────
load_from_aws()
all_exams = get_all_exams()
exam_names = list(all_exams.keys())

tabs = st.tabs([f"{all_exams[name]['icon']} {name}" for name in exam_names])

for idx, exam_name in enumerate(exam_names):
    with tabs[idx]:
        exam = all_exams[exam_name]
        room = st.session_state.rooms.get(exam_name)
        participant_count = len(room["participants"]) if room else 0
        is_joined = exam_name in st.session_state.my_rooms

        col_left, col_right = st.columns([2, 1])
        
        with col_left:
            st.markdown(f"### {exam['icon']} {exam_name} 常設ルーム")
            st.markdown(f"""
            <div class="exam-card active">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong style="font-size:1.2rem;">🟢 現在のルーム状況</strong>
                    <span class="participants-badge">👥 {participant_count}人が参加中</span>
                </div>
                <div class="room-url-box">
                    <p style="margin-bottom:0.5rem; opacity:0.9; font-size:0.9rem;">🔗 通話ルームURL</p>
                    <a href="{room['url'] if room else '#'}" target="_blank">{room['url'] if room else 'ルームが未設定です。右側から追加してください。'}</a>
                </div>
            </div>""", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                if room:
                    if st.link_button("参加する🚀", room['url'], type="primary", use_container_width=True):
                        create_or_join_room(exam_name, room['url'], st.session_state.my_name)
                else:
                    st.button("参加する🚀", disabled=True, use_container_width=True)
            with c2:
                if is_joined:
                    if st.button("退出する", key=f"leave_{exam_name}", type="secondary", use_container_width=True):
                        leave_room(exam_name, st.session_state.my_name); st.rerun()

        with col_right:
            st.markdown("#### 🏰 ルームを管理")
            with st.container(border=True):
                st.write("別のURLで反映・作成")
                
                # 管理者設定のURLをリスト化（追加可能にするロジック）
                raw_urls = st.session_state.admin_urls.get(exam_name, "")
                admin_url_list = [u.strip() for u in raw_urls.split(",") if u.strip()]
                
                # 選択肢の作成
                options = admin_url_list + ["＋ 新しいURLを手動入力"]
                selected_url = st.selectbox("登録済みURLから選択", options, key=f"select_{exam_name}")
                
                if selected_url == "＋ 新しいURLを手動入力":
                    final_url = st.text_input("通話ルームURLを入力", placeholder="https://...", key=f"manual_{exam_name}")
                else:
                    final_url = selected_url
                
                if st.button(f"✅ 設定を反映", key=f"create_{exam_name}", type="primary", use_container_width=True):
                    if is_url_valid(final_url):
                        create_or_join_room(exam_name, final_url, st.session_state.my_name); st.rerun()
                    else:
                        st.error("有効なURLを選択または入力してください")

        if room and room["participants"]:
            st.divider()
            st.caption(f"👋 学習中のメンバー: {', '.join(room['participants'])}")

st.divider()
st.markdown("""<div style="text-align:center; color:#aaa; font-size:0.85rem; padding:1rem 0;">📚 StudyConnect ─ カテゴリーを切り替えて仲間を探そう</div>""", unsafe_allow_html=True)
