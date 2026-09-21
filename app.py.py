# app.py
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ──────────────────────────────────────────────
# 1. 데이터 로드 (BOM + 탭 + 따옴표 처리 포함)
# ──────────────────────────────────────────────
@st.cache_data
def load_data(filepath: str = "seoul_temperature.csv") -> pd.DataFrame:
    df = pd.read_csv(
        filepath,
        encoding="utf-8-sig",
        dtype={"날짜": str},
    )

    df["날짜"] = (
        df["날짜"]
        .str.replace('"', "", regex=False)
        .str.strip()
    )
    df["날짜"] = pd.to_datetime(df["날짜"], errors="coerce")
    df["연도"] = df["날짜"].dt.year
    df["월"] = df["날짜"].dt.month

    for col in ["평균기온(℃)", "최저기온(℃)", "최고기온(℃)"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # 일교차 컬럼
    df["일교차(℃)"] = df["최고기온(℃)"] - df["최저기온(℃)"]

    return df.dropna(subset=["날짜", "연도"])


# ──────────────────────────────────────────────
# 2. 앱 UI
# ──────────────────────────────────────────────
st.set_page_config(page_title="서울 기온 분석", layout="wide")
st.title("🌡️ 서울 연도별 평균기온 (1907–현재)")

df = load_data()
if df.empty:
    st.error("데이터 파일을 읽을 수 없습니다. seoul_temperature.csv를 확인하세요.")
    st.stop()

min_year = int(df["연도"].min())
max_year = int(df["연도"].max())

# ── 사이드바: 연도 범위 슬라이더 ──
c1, c2 = st.sidebar.columns(2)
with c1:
    시작연도 = st.slider("시작 연도", min_year, max_year, min_year, step=1)
with c2:
    종료연도 = st.slider("종료 연도", min_year, max_year, max_year, step=1)

if 시작연도 > 종료연도:
    시작연도, 종료연도 = 종료연도, 시작연도

df_sel = df[(df["연도"] >= 시작연도) & (df["연도"] <= 종료연도)].copy()

if df_sel.empty:
    st.warning(f"{시작연도}–{종료연도} 구간에 데이터가 없습니다.")
    st.stop()

# ── 연도별 평균기온 집계 + 5년 이동평균 ──
yearly = (
    df_sel.groupby("연도")["평균기온(℃)"]
    .mean()
    .reset_index()
    .rename(columns={"평균기온(℃)": "연평균기온"})
    .sort_values("연도")
)
yearly["이동평균_5년"] = yearly["연평균기온"].rolling(window=5, min_periods=1).mean()

# ── 구간 통계지표 ──
avg_t = df_sel["평균기온(℃)"].mean()
max_t = df_sel["최고기온(℃)"].max()
min_t = df_sel["최저기온(℃)"].min()

m1, m2, m3 = st.columns(3)
m1.metric(f"{시작연도}–{종료연도} 평균기온", f"{avg_t:.2f}℃")
m2.metric(f"{시작연도}–{종료연도} 최고기온", f"{max_t:.2f}℃")
m3.metric(f"{시작연도}–{종료연도} 최저기온", f"{min_t:.2f}℃")

st.divider()

# ── Plotly 그래프: 연평균기온 + 5년 이동평균 ──
fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=yearly["연도"],
        y=yearly["연평균기온"],
        mode="lines+markers",
        name="연평균기온",
        line=dict(color="#3b82f6", width=2),
        marker=dict(size=5),
    )
)
fig.add_trace(
    go.Scatter(
        x=yearly["연도"],
        y=yearly["이동평균_5년"],
        mode="lines",
        name="5년 이동평균",
        line=dict(color="#f97316", width=3, dash="dot"),
    )
)

fig.update_layout(
    title=f"서울 연도별 평균기온 ({시작연도}–{종료연도})",
    xaxis_title="연도",
    yaxis_title="평균기온 (℃)",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    template="plotly_white",
    margin=dict(l=50, r=20, t=50, b=40),
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

# ──────────────────────────────────────────────
# 3. 월별 히트맵
# ──────────────────────────────────────────────
st.subheader("📊 월별 평균기온 히트맵")

heatmap_data = (
    df_sel.groupby(["연도", "월"])["평균기온(℃)"]
    .mean()
    .reset_index()
    .rename(columns={"평균기온(℃)": "평균기온"})
)

pivot = heatmap_data.pivot(index="연도", columns="월", values="평균기온")

fig_heat = px.imshow(
    pivot,
    aspect="auto",
    color_continuous_scale="RdYlBu_r",
    labels=dict(x="월", y="연도", color="평균기온(℃)"),
    title=f"월별 평균기온 히트맵 ({시작연도}–{종료연도})",
)
fig_heat.update_layout(
    margin=dict(l=50, r=20, t=50, b=40),
    coloraxis_colorbar=dict(title="℃", thickness=15, len=0.75),
)
fig_heat.update_xaxes(tickmode="linear", tick0=1, dtick=1)
st.plotly_chart(fig_heat, use_container_width=True)

st.divider()

# ──────────────────────────────────────────────
# 4. 최고기온 상위 10일 / 최저기온 하위 10일
# ──────────────────────────────────────────────
col_high, col_low = st.columns(2)

with col_high:
    st.subheader("🔥 최고기온 상위 10일")
    top_high = (
        df_sel.sort_values("최고기온(℃)", ascending=False)
        .head(10)[["날짜", "지점", "최고기온(℃)", "평균기온(℃)", "최저기온(℃)"]]
        .reset_index(drop=True)
    )
    top_high["날짜"] = top_high["날짜"].dt.strftime("%Y-%m-%d")
    top_high.columns = ["날짜", "지점", "최고기온(℃)", "평균기온(℃)", "최저기온(℃)"]
    st.dataframe(top_high, use_container_width=True, hide_index=True)

with col_low:
    st.subheader("❄️ 최저기온 하위 10일")
    bottom_low = (
        df_sel.sort_values("최저기온(℃)", ascending=True)
        .head(10)[["날짜", "지점", "최고기온(℃)", "평균기온(℃)", "최저기온(℃)"]]
        .reset_index(drop=True)
    )
    bottom_low["날짜"] = bottom_low["날짜"].dt.strftime("%Y-%m-%d")
    bottom_low.columns = ["날짜", "지점", "최고기온(℃)", "평균기온(℃)", "최저기온(℃)"]
    st.dataframe(bottom_low, use_container_width=True, hide_index=True)

st.divider()

# ──────────────────────────────────────────────
# 5. 연도별 평균 일교차 그래프
# ──────────────────────────────────────────────
st.subheader("🌡️ 연도별 평균 일교차")

daily_range_yearly = (
    df_sel.groupby("연도")["일교차(℃)"]
    .mean()
    .reset_index()
    .rename(columns={"일교차(℃)": "평균일교차"})
    .sort_values("연도")
)
daily_range_yearly["이동평균_5년"] = daily_range_yearly["평균일교차"].rolling(window=5, min_periods=1).mean()

fig_range = go.Figure()

fig_range.add_trace(
    go.Scatter(
        x=daily_range_yearly["연도"],
        y=daily_range_yearly["평균일교차"],
        mode="lines+markers",
        name="평균 일교차",
        line=dict(color="#8b5cf6", width=2),
        marker=dict(size=5),
    )
)
fig_range.add_trace(
    go.Scatter(
        x=daily_range_yearly["연도"],
        y=daily_range_yearly["이동평균_5년"],
        mode="lines",
        name="5년 이동평균",
        line=dict(color="#ec4899", width=3, dash="dot"),
    )
)

fig_range.update_layout(
    title=f"서울 연도별 평균 일교차 ({시작연도}–{종료연도})",
    xaxis_title="연도",
    yaxis_title="일교차 (℃)",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    template="plotly_white",
    margin=dict(l=50, r=20, t=50, b=40),
)

st.plotly_chart(fig_range, use_container_width=True)

st.divider()

# ── 원본 데이터 미리보기 ──
with st.expander("원본 데이터 미리보기 (최대 100행)"):
    preview = df_sel.copy()
    preview["날짜"] = preview["날짜"].dt.strftime("%Y-%m-%d")
    st.dataframe(preview.head(100), use_container_width=True, height=350)
