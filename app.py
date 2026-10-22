"""AI 角色对话助手 —— 部署版（含示例引导、示例角色、用量限制、页脚信息）。

部署前请确认：
1. Streamlit Secrets 中已配置 DEEPSEEK_API_KEY；
2. 仓库根目录有 requirements.txt（streamlit>=1.49、openai>=1.40）。
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
MAX_HISTORY = 20          # 送给模型的历史消息条数
MAX_MESSAGES = 40         # 单个会话最多保留的消息条数
GITHUB_URL = "https://github.com/shengtong255/ai-persona-chat"
CONTACT_MAIL = "1641417967@qq.com"

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

# 预设角色：把“人设配置”变成可一键体验的数字人角色卡
PRESETS = {
    "包菜｜活泼开朗的南方姑娘": ("包菜", "活泼开朗的南方姑娘，说话带点南方口音，爱用语气词"),
    "小美｜耐心细致的客服": ("小美", "耐心细致的电商客服，先安抚情绪再给解决方案"),
    "Alex｜严格的口语外教": ("Alex", "严格的英语口语外教，逐句纠正表达并给出更地道的说法"),
}
EXAMPLE_QUESTIONS = [
    "你今天心情怎么样？",
    "帮我把这段话改得更正式一点：明天开会别迟到",
    "用三句话介绍一下你自己",
]


def get_secret(name: str) -> str | None:
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return os.environ.get(name)


def now_key() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def user_session_dir() -> Path:
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
    try:
        with (user_session_dir() / f"{st.session_state.current_time}.json").open(
            "w", encoding="utf-8"
        ) as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except OSError as exc:
        st.warning(f"会话保存失败：{exc}")


def load_sessions() -> list[str]:
    try:
        return sorted((p.stem for p in user_session_dir().glob("*.json")), reverse=True)
    except OSError:
        return []


def load_session(name: str) -> None:
    path = user_session_dir() / f"{name}.json"
    if not path.exists():
        st.error("会话不存在或已被删除")
        return
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        st.session_state.current_time = name
        st.session_state.nick_name = data.get("nick_name", "包菜")
        st.session_state.nature = data.get("nature", "活泼开朗的南方姑娘")
        st.session_state.messages = data.get("messages", [])
    except (OSError, ValueError) as exc:
        st.error(f"加载会话失败：{exc}")


def delete_session(name: str) -> None:
    try:
        (user_session_dir() / f"{name}.json").unlink(missing_ok=True)
    except OSError as exc:
        st.error(f"删除会话失败：{exc}")
        return
    if name == st.session_state.current_time:
        reset_conversation()
    st.success("删除会话成功")


def reset_conversation() -> None:
    st.session_state.messages = []
    st.session_state.current_time = now_key()
    if "preset" in st.session_state:
        st.session_state.nick_name, st.session_state.nature = PRESETS[st.session_state.preset]


def render_sidebar() -> None:
    with st.sidebar:
        logo = APP_DIR / "resource" / "logo.png"
        if logo.exists():
            st.image(str(logo), width=120)

        st.subheader("1 · 选一个角色")
        preset = st.selectbox("预设角色", list(PRESETS), key="preset", label_visibility="collapsed")
        if st.session_state.get("_applied") != preset:
            st.session_state.nick_name, st.session_state.nature = PRESETS[preset]
            st.session_state["_applied"] = preset

        with st.expander("自定义人设", expanded=False):
            st.session_state.nick_name = st.text_input("昵称", value=st.session_state.nick_name)
            nature = st.text_area("性格", value=st.session_state.nature, height=90)
            st.session_state.nature = nature

        st.divider()
        st.subheader("2 · 开始对话")
        if st.button("新建会话", width="stretch", icon="✏️"):
            save_session()
            reset_conversation()
            st.rerun()

        sessions = load_sessions()
        if sessions:
            with st.expander(f"历史会话（{len(sessions)}）", expanded=False):
                for name in sessions[:10]:
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        if st.button(
                            name,
                            width="stretch",
                            key=f"load_{name}",
                            type="primary" if name == st.session_state.current_time else "secondary",
                        ):
                            load_session(name)
                            st.rerun()
                    with col2:
                        if st.button("", width="stretch", icon="🗑️", key=f"del_{name}"):
                            delete_session(name)
                            st.rerun()

        st.divider()
        st.caption(f"源码：[GitHub]({GITHUB_URL})　·　联系：{CONTACT_MAIL}")
        st.caption("演示环境：会话仅存于当前浏览器，请勿输入隐私信息。")


def main() -> None:
    st.set_page_config(
        page_title="AI 角色对话助手",
        page_icon="🥬",
        layout="centered",
        initial_sidebar_state="auto",
    )
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("nick_name", "包菜")
    st.session_state.setdefault("nature", "活泼开朗的南方姑娘")
    st.session_state.setdefault("current_time", now_key())
    st.session_state.setdefault("preset", list(PRESETS)[0])

    render_sidebar()

    st.title("AI 角色对话助手")
    st.caption("选一个角色 → 直接问它问题。人设（昵称 / 性格）会实时注入 System Prompt，"
               "回复风格随之改变；支持流式输出与多会话。｜首次打开可能需要 20～30 秒唤醒。")

    if not st.session_state.messages:
        st.markdown("**试试这几个问题：**")
        cols = st.columns(3)
        for col, question in zip(cols, EXAMPLE_QUESTIONS):
            if col.button(question, width="stretch"):
                st.session_state.pending = question

    for message in st.session_state.messages:
        st.chat_message(message["role"]).write(message["content"])

    prompt = st.chat_input("输入你想问的问题（示例：帮我写一句离职原因）", max_chars=300)
    if "pending" in st.session_state:
        prompt = st.session_state.pop("pending")
    if not prompt:
        return

    if len(st.session_state.messages) >= MAX_MESSAGES:
        st.warning("本会话已达演示上限，请点「新建会话」继续体验。")
        return

    api_key = get_secret("DEEPSEEK_API_KEY")
    if not api_key:
        st.error("未配置 DEEPSEEK_API_KEY，请在 Settings → Secrets 中配置后重试。")
        return

    st.chat_message("user").write(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    system = SYSTEM_PROMPT.format(
        nick_name=st.session_state.nick_name, nature=st.session_state.nature
    )
    history = st.session_state.messages[-MAX_HISTORY:]

    try:
        stream = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "system", "content": system}, *history],
            stream=True,
        )

        def chunks():
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

        full = st.write_stream(chunks())
    except Exception as exc:
        st.error(f"模型调用失败，请稍后重试：{exc}")
        return

    st.session_state.messages.append({"role": "assistant", "content": full})
    save_session()
    st.rerun()


main()
