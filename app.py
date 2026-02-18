import re
from pathlib import Path
import pandas as pd
import streamlit as st

# =========================================================
# 경로 설정: app.py가 있는 폴더 기준
# =========================================================
BASE_DIR = Path(__file__).resolve().parent
CSV_DIR = BASE_DIR / "out_csv"  # C:\문제풀이폴더\out_csv

st.set_page_config(page_title="소방설비기사 CBT(통합/채점)", layout="centered")
st.title("🔥 소방설비기사(기계) CBT ")

# =========================================================
# 파일명에서 라벨(날짜) 만들기
# =========================================================
def make_label(file_path: Path) -> str:
    stem = file_path.stem
    m = re.search(r"(20\d{6})", stem)
    if m:
        ymd = m.group(1)
        return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
    return stem

@st.cache_data
def load_all_exams():
    if not CSV_DIR.exists():
        return [], {}

    files = sorted(CSV_DIR.glob("*_문항분리_정답포함.csv"))
    labels = []
    exam_map = {}

    need_cols = {"번호", "문제", "보기1", "보기2", "보기3", "보기4", "정답"}

    for f in files:
        try:
            df = pd.read_csv(f, encoding="utf-8-sig")
        except Exception:
            continue

        if not need_cols.issubset(set(df.columns)):
            continue

        df["번호"] = pd.to_numeric(df["번호"], errors="coerce").fillna(0).astype(int)
        df["정답"] = pd.to_numeric(df["정답"], errors="coerce").fillna(0).astype(int)
        df = df[df["번호"].between(1, 200)].copy()
        df = df.sort_values("번호").reset_index(drop=True)

        label = make_label(f)
        if label in exam_map:
            label = f"{label} ({f.name})"

        exam_map[label] = df
        labels.append(label)

    return labels, exam_map

labels, exam_map = load_all_exams()

if not labels:
    st.error(
        "정답 포함 CSV를 찾지 못했습니다.\n\n"
        "✅ C:\\문제풀이폴더\\out_csv 폴더에 '*_문항분리_정답포함.csv' 파일이 있는지 확인하세요."
    )
    st.stop()

# =========================================================
# 회차 선택
# =========================================================
selected = st.selectbox("회차(파일)를 선택하세요", labels, index=0)
df = exam_map[selected]
total = len(df)

st.caption(f"📌 선택된 회차: **{selected}** | 문항 수: **{total}**")

# 옵션
require_correct = st.toggle("정답을 맞혀야 다음 문제로 이동", value=True)
auto_next = st.toggle("정답이면 자동으로 다음 문제로 이동", value=False)

# =========================================================
# 회차별 상태 저장
# =========================================================
state_key = f"state_{selected}"

if state_key not in st.session_state:
    st.session_state[state_key] = {
        "idx": 0,
        "picked": {},       # qnum -> 1~4 (현재 선택)
        "wrong": 0,         # 오답 시도 횟수(클릭 누적)
    }

state = st.session_state[state_key]
idx = state["idx"]

# =========================================================
# 완료 화면
# =========================================================
def calc_correct_count():
    correct_count = 0
    for _, r in df.iterrows():
        q = int(r["번호"])
        ans = int(r["정답"])
        pick = state["picked"].get(q)
        if pick is not None and int(pick) == ans:
            correct_count += 1
    return correct_count

if idx >= total:
    st.success("🎉 이 회차 완료!")
    st.write(f"맞춘 문항(현재 선택 기준): **{calc_correct_count()}** / {total}")
    st.write(f"오답 시도(클릭 누적): **{state['wrong']}**")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("처음부터 다시"):
            st.session_state[state_key] = {"idx": 0, "picked": {}, "wrong": 0}
            st.rerun()
    with c2:
        if st.button("처음으로(기록 유지)"):
            state["idx"] = 0
            st.rerun()
    st.stop()

# =========================================================
# 현재 문제
# =========================================================
row = df.iloc[idx]
qnum = int(row["번호"])
question = str(row["문제"]).strip()
opts = [str(row[f"보기{i}"]).strip() for i in range(1, 5)]
answer = int(row["정답"])  # 1~4

circle = ["①", "②", "③", "④"]
display = []
for i in range(4):
    opt = opts[i]
    if (not opt) or (str(opt).lower() == "nan"):
        opt = "(보기 없음)"
    display.append(f"{circle[i]} {opt}")

st.caption(f"{selected} | 문제 {idx+1}/{total} | 문항 {qnum}번")
st.subheader(f"{qnum}. {question}")

feedback = st.empty()

# ✅ 이전 선택이 없으면 None(아무 것도 선택 안된 상태)로 시작
prev_pick = state["picked"].get(qnum)
radio_index = (int(prev_pick) - 1) if isinstance(prev_pick, int) and 1 <= int(prev_pick) <= 4 else None

def grade_now():
    """선택 즉시 채점. '현재 선택'을 기준으로 피드백을 갱신."""
    picked = st.session_state.get(f"pick_{selected}_{qnum}", None)
    if picked is None:
        return

    picked = int(picked)
    state["picked"][qnum] = picked  # 현재 선택 저장

    if picked == answer:
        feedback.success("✅ 정답!")
        if auto_next:
            state["idx"] = idx + 1
            st.rerun()
    else:
        state["wrong"] += 1
        feedback.error("❌ 오답! 다시 선택하세요.")

picked_num = st.radio(
    "정답 선택 (선택 즉시 채점)",
    options=[1, 2, 3, 4],
    index=radio_index,  # ✅ None이면 선택 없음
    key=f"pick_{selected}_{qnum}",
    format_func=lambda n: display[n - 1],
    on_change=grade_now
)

# 라디오 선택값 저장(선택 안 했으면 picked_num이 None일 수 있음)
if picked_num is not None:
    state["picked"][qnum] = int(picked_num)

# ✅ 이동/새로고침 후에도 현재 선택 기준으로 피드백 표시
current_pick = state["picked"].get(qnum)

if current_pick is None:
    feedback.empty()
elif int(current_pick) == answer:
    feedback.success("✅ 정답!")
else:
    feedback.error("❌ 오답! 다시 선택하세요.")

st.divider()

# =========================================================
# 다음 버튼 잠금 여부 (현재 선택 기준)
# =========================================================
is_correct_now = (current_pick is not None and int(current_pick) == answer)

c1, c2, c3 = st.columns([1, 1, 2])

with c1:
    if st.button("◀ 이전"):
        state["idx"] = max(0, idx - 1)
        st.rerun()

with c2:
    next_disabled = (require_correct and not is_correct_now)
    if st.button("다음 ▶", disabled=next_disabled):
        state["idx"] = idx + 1
        st.rerun()

with c3:
    jump = st.number_input("문항 번호로 이동", min_value=1, max_value=total, value=idx + 1, step=1)
    if st.button("이동"):
        state["idx"] = int(jump) - 1
        st.rerun()

st.write(f"맞춘 문항(현재 선택 기준): **{calc_correct_count()}** / {total}   |   오답 시도(클릭 누적): **{state['wrong']}**")
