"""AI 角色对话助手 —— 可直接部署到 Streamlit Community Cloud 的版本。

相比原稿的改动：
1. API Key 支持 st.secrets（云端）与 os.environ（本地）两种读取方式；
2. 会话按浏览器隔离（每个访客一个 uuid 目录），避免公开部署后互相看到对话；
3. System Prompt 改用 str.format，昵称/性格含 % 也不会崩；
4. save_session 只在消息追加后调用，不再每敲一个字写盘；
5. 新建会话在空会话时也能生效；
6. API 调用加异常处理，失败不白屏；历史消息做上下文截断；
7. logo 缺失时自动跳过，不会启动失败。
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import streamlit as st
from openai import OpenAI

APP_DIR = Path(__file__).resolve().parent
SESSION_ROOT = APP_DIR / "session"
MAX_HISTORY = 20  # 发送给模型的历史消息条数上限

SYSTEM_PROMPT = """你叫{nick_name}，现在是用户的真实助理，请完全代入助理角色。
规则：
1. 每次只回 1 条消息
2. 禁止任何场景或状态描述性文字
3. 匹配用户的语言
4. 回复简短，像微信聊天一样
5. 有需要的话可以用 ❤️🌸 等 emoji 表情
6. 用符合助理性格的方式对话
7. 回复的内容要充分体现助理的性格特征
助理性格：
- {nature}
你必须严格遵守上述规则来回复用户。"""


def get_secret(name: str) -> str | None:
    """优先读 Streamlit secrets，其次读环境变量。"""
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def get_current_time() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def user_session_dir() -> Path:
    """每个浏览器会话一个独立目录，公开部署时互不可见。"""
    if "sid" not in st.session_state:
        st.session_state.sid = uuid.uuid4().hex[:10]
    directory = SESSION_ROOT / st.session_state.sid
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def save_session() -> None:
    if not (st.session_state.current_time and st.session_state.messages):
        return
    data = {
        "current_time": st.session_state.current_time,
        "nick_name": st.session_state.nick_name,
        "nature": st.session_state.nature,
        "messages": st.session_state.messages,
    }
    path = user_session_dir() / f"{st.session_state.current_time}.json"
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except OSError as exc:
        st.warning(f"会话保存失败：{exc}")


def load_sessions() -> list[str]:
    try:
        return sorted(
            (p.stem for p in user_session_dir().glob("*.json")), reverse=True
        )
    except OSError:
        return []


def load_session(session_name: str) -> None:
    path = user_session_dir() / f"{session_name}.json"
    if not path.exists():
        st.error("会话不存在或已被删除")
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        st.session_state.current_time = session_name
        st.session_state.nick_name = data.get("nick_name", "包菜")
        st.session_state.nature = data.get("nature", "活泼开朗的南方姑娘")
        st.session_state.messages = data.get("messages", [])
    except (OSError, ValueError) as exc:
        st.error(f"加载会话失败：{exc}")


def delete_session(session_name: str) -> None:
    path = user_session_dir() / f"{session_name}.json"
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        st.error(f"删除会话失败：{exc}")
        return
    if session_name == st.session_state.current_time:
        st.session_state.messages = []
        st.session_state.current_time = get_current_time()
        st.session_state.nick_name = "包菜"
        st.session_state.nature = "活泼开朗的南方姑娘"
    st.success("删除会话成功")


def reset_conversation() -> None:
    st.session_state.messages = []
    st.session_state.nick_name = "包菜"
    st.session_state.nature = "活泼开朗的南方姑娘"
    st.session_state.current_time = get_current_time()


# ---------------- 页面与状态 ----------------
st.set_page_config(
    page_title="AI 角色对话助手",
    page_icon="🥬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.session_state.setdefault("messages", [])
st.session_state.setdefault("nick_name", "包菜")
st.session_state.setdefault("nature", "活泼开朗的南方姑娘")
st.session_state.setdefault("current_time", get_current_time())

logo_path = APP_DIR / "resource" / "logo.png"
if logo_path.exists():
    st.sidebar.image(str(logo_path))

st.title("AI 角色对话助手")
st.caption("自定义人设（昵称 + 性格）后开始对话；会话仅保存在当前浏览器，刷新页面即回到初始状态。")

with st.sidebar:
    st.subheader("人设配置")
    nick = st.text_input("昵称", value=st.session_state.nick_name)
    if nick:
        st.session_state.nick_name = nick
    nature = st.text_area("性格", value=st.session_state.nature, height=100)
    if nature:
        st.session_state.nature = nature

    st.divider()
    st.subheader("会话")
    if st.button("新建会话", width="stretch", icon="✏️"):
        save_session()
        reset_conversation()
        st.rerun()

    for session_name in load_sessions():
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.button(
                session_name,
                width="stretch",
                icon="🏷️",
                key=f"load_{session_name}",
                type="primary" if session_name == st.session_state.current_time else "secondary",
            ):
                load_session(session_name)
                st.rerun()
        with col2:
            if st.button("", width="stretch", icon="❌", key=f"delete_{session_name}"):
                delete_session(session_name)
                st.rerun()

st.text(f"当前会话：{st.session_state.current_time}")

for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])

prompt = st.chat_input("请输入你想问的问题")
if prompt:
    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    api_key = get_secret("DEEPSEEK_API_KEY")
    if not api_key:
        st.error("未配置 DEEPSEEK_API_KEY，请在 .streamlit/secrets.toml 或环境变量中设置。")
        st.stop()

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    system = SYSTEM_PROMPT.format(
        nick_name=st.session_state.nick_name, nature=st.session_state.nature
    )
    history = st.session_state.messages[-MAX_HISTORY:]

    placeholder = st.empty()
    full_response = ""
    try:
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system}, *history],
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                full_response += delta
                placeholder.chat_message("assistant").write(full_response)
    except Exception as exc:  # 网络、额度、限流都走这里
        st.error(f"模型调用失败，请稍后重试：{exc}")
        st.stop()

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    save_session()
    st.rerun()
