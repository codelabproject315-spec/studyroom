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

    html, body, [class*=\"css\"] {
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

    .alert-info {
        background: #d1ecf1;
        color: #0c5460;
        border: 1px solid #bee5eb;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
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
    "G検定": {"icon": "🤖", "description": "AIの基礎知識・理論", "color": "#6c63ff", "admin_url": ""},
    "E資格": {"icon": "⚡", "description": "ディープラーニング実装", "color": "#e17055", "admin_url": ""},
    "AWS資格": {"icon": "☁️", "description": "AWSクラウド設計・運用", "color": "#fd9644", "admin_url": ""},
}

def init_state():
    if "rooms" not in st.session_state: st.session_state.rooms = {}
    if "my_name" not in st.session_state: st.session_state.my_name = ""
    if "my_rooms" not in st.session_state: st.session_state.my_rooms = set()
    if "custom_exams" not in st.session_state: st.session_state.custom_exams = {}
    if "admin_urls" not in st.session_state:
        st.session_state.admin_urls = {k: v["admin_url"] for k, v in EXAMS_DEFAULT.items()}
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

st.markdown("""<div class="main-header"><h1>📚 StudyConnect</h1><p>同じ検定を目指す仲間と、今すぐ一緒に学ぼう</p></div>""", unsafe_allow_html=True)
st.divider()

with st.sidebar:
    st.markdown("### 👤 あなたの名前")
    name_input = st.text_input("ニックネーム（任意）", value=st.session_state.my_name, placeholder="例: たろう", label_visibility="collapsed")
    if name_input != st.session_state.my_name: st.session_state.my_name = name_input
    
    st.divider()
    st.markdown("### ➕ 検定を追加")
    with st.expander("カスタム検定を追加"):
        new_exam_name = st.text_input("検定名")
        new_exam_icon = st.selectbox("アイコン", ["📊", "💻", "📝", "🔬", "💡", "🎯", "🏆", "📐"])
        if st.button("追加する", type="primary", use_container_width=True):
            if new_exam_name:
                st.session_state.custom_exams[new_exam_name] = {"icon": new_exam_icon, "description": "カスタム検定", "color": "#a29bfe", "admin_url": ""}
                # 管理者設定用の辞書にも追加
                if new_exam_name not in st.session_state.admin_urls:
                    st.session_state.admin_urls[new_exam_name] = ""
                save_config_to_aws()
                st.rerun()

    st.divider()
    st.markdown("### ⚙️ 管理者設定")
    with st.expander("デフォルトURLを設定"):
        all_exams = get_all_exams()
        for exam_name in all_exams:
            st.text_input(f"{all_exams[exam_name]['icon']} {exam_name}", value=st.session_state.admin_urls.get(exam_name, ""), key=f"input_admin_{exam_name}")
        if st.button("設定を保存", use_container_width=True):
            for exam_name in all_exams:
                st.session_state.admin_urls[exam_name] = st.session_state[f"input_admin_{exam_name}"]
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
# コンテンツ表示
# ─────────────────────────────────────────────
load_from_aws()
all_exams = get_all_exams()

# アクティブなルーム表示
active_rooms = [(name, st.session_state.rooms[name]) for name in all_exams if name in st.session_state.rooms]
if active_rooms:
    st.markdown("### 🟢 現在アクティブなルーム")
    for exam_name, room in active_rooms:
        exam = all_exams[exam_name]
        participant_count = len(room["participants"])
        with st.container():
            st.markdown(f"""
            <div class="exam-card active">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.8rem;">
                    <div><span style="font-size:1.5rem;">{exam['icon']}</span><strong style="font-size:1.1rem; margin-left:0.5rem;">{exam_name}</strong></div>
                    <span class="participants-badge">👥 {participant_count}人が学習中</span>
                </div>
                <div class="room-url-box"><p style="margin-bottom:0.5rem; opacity:0.9; font-size:0.9rem;">🔗 通話ルームURL</p><a href="{room['url']}" target="_blank">{room['url']}</a></div>
            </div>""", unsafe_allow_html=True)
            cols = st.columns([3, 1])
            with cols[0]:
                st.caption(f"👋 参加中: {', '.join(room['participants'][:5])}")
            with cols[1]:
                if exam_name in st.session_state.my_rooms:
                    if st.button("退出する", key=f"leave_{exam_name}", type="secondary", use_container_width=True):
                        leave_room(exam_name, st.session_state.my_name); st.rerun()
                else:
                    if st.link_button("参加する🚀", room['url'], type="primary", use_container_width=True):
                        create_or_join_room(exam_name, room["url"], st.session_state.my_name)

st.divider()

# 検定一覧エリア
st.markdown("### 📋 検定一覧 ─ 「今からやる」ボタンでルームを作成")
cols_per_row = 2
exam_list = list(all_exams.items())
for i in range(0, len(exam_list), cols_per_row):
    row_exams = exam_list[i:i+cols_per_row]
    cols = st.columns(cols_per_row)
    for col, (exam_name, exam) in zip(cols, row_exams):
        with col:
            room = st.session_state.rooms.get(exam_name)
            is_active = room is not None
            card_class = "exam-card active" if is_active else "exam-card"
            st.markdown(f"""
            <div class="{card_class}">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:0.5rem;">
                    <div><span style="font-size:1.8rem;">{exam['icon']}</span><strong style="display:block; font-size:1.1rem; color:#1a1a2e; margin-top:0.2rem;">{exam_name}</strong><small style="color:#888;">{exam['description']}</small></div>
                    <span class="participants-badge {'empty' if not is_active else ''}">👥 {len(room['participants']) if is_active else 0}人</span>
                </div>
            </div>""", unsafe_allow_html=True)

            # 常に「ルーム作成・参加」のフォームを表示
            with st.expander(f"📢 {'ルームを管理' if is_active else '今からやる！（ルーム作成）'}"):
                # 管理者設定があればそれをデフォルトとして表示
                default_url = st.session_state.admin_urls.get(exam_name, "")
                
                if default_url:
                    st.markdown(f"<div class='alert-info'>デフォルトURLが設定されています</div>", unsafe_allow_html=True)
                    st.code(default_url, language=None)
                    use_admin = st.checkbox("このURLを使う", value=True, key=f"use_admin_{exam_name}")
                    url_to_use = default_url if use_admin else st.text_input("別のURLを入力", key=f"custom_url_{exam_name}")
                else:
                    url_to_use = st.text_input("通話ルームURL", placeholder="https://...", key=f"url_input_{exam_name}")

                if st.button(f"✅ ルームを反映", key=f"create_{exam_name}", type="primary", use_container_width=True):
                    if not url_to_use or not is_url_valid(url_to_use):
                        st.error("有効なURLを入力してください")
                    else:
                        create_or_join_room(exam_name, url_to_use, st.session_state.my_name)
                        st.balloons(); st.rerun()

st.divider()
st.markdown("""<div style=\"text-align:center; color:#aaa; font-size:0.85rem; padding:1rem 0;\">📚 StudyConnect ─ 一緒に学べば、もっと頑張れる</div>""", unsafe_allow_html=True)
