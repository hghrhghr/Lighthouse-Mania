import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from st_gsheets_connection import GSheetsConnection

# --- ページ基本設定 ---
st.set_page_config(page_title="日本全国 灯台マップ", layout="wide")

st.title("⚓ 日本全国 灯台位置可視化アプリ")
st.caption("Googleスプレッドシート連携版：日本の灯台の位置・レンズ・訪問ステータス・スコアを自動同期します。")

# --- スプレッドシート接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    # ttl=0 で常に最新のスプレッドシートデータを読み込む
    df = conn.read(ttl=0)
    
    # 必須カラム・型変換の保護処理
    cols = ["name", "region", "pref", "lat", "lon", "height", "range_nm", "lens", "visited", "score", "desc"]
    for c in cols:
        if c not in df.columns:
            df[c] = ""
            
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce").fillna(35.0)
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce").fillna(139.0)
    df["height"] = pd.to_numeric(df["height"], errors="coerce").fillna(0).astype(int)
    df["range_nm"] = pd.to_numeric(df["range_nm"], errors="coerce").fillna(0.0)
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0).astype(int)
    df["lens"] = df["lens"].fillna("不明")
    df["visited"] = df["visited"].fillna("未訪問")
    df["desc"] = df["desc"].fillna("（解説なし）")
    return df

def save_all_data(df_to_save):
    # スプレッドシート全体を上書き更新
    conn.update(data=df_to_save)

df = load_data()

# --- サイドバー：1. 絞り込み＆ソート条件 ---
st.sidebar.header("🔍 フィルタ＆並び替え")

regions = ["すべて"] + ["北海道", "東北", "関東", "中部", "近畿", "中国", "四国", "九州", "沖縄"]
selected_region = st.sidebar.selectbox("地方を選択", regions)

status_filter = st.sidebar.radio("訪問ステータスで絞り込み", ["すべて", "訪問済み", "未訪問"], horizontal=True)

sort_option = st.sidebar.selectbox(
    "リストの並び替え",
    ["登録順", "スコアが高い順", "スコアが低い順", "訪問済み優先", "未訪問優先"]
)

search_term = st.sidebar.text_input("灯台名・都道府県・レンズで検索", "")
show_range = st.sidebar.checkbox("光達距離（照射範囲）を表示", value=False)

st.sidebar.markdown("""
**【ピンの色凡例】**
- 🟩 **緑**: 訪問済み
- 🟥 **赤**: 未訪問
""")

# --- サイドバー：2. 灯台追加フォーム ---
st.sidebar.markdown("---")
with st.sidebar.expander("➕ 新しい灯台を追加する", expanded=False):
    with st.form("add_form", clear_on_submit=True):
        new_name = st.text_input("灯台名*", placeholder="例: 神威岬灯台")
        new_region = st.selectbox("地方*", ["北海道", "東北", "関東", "中部", "近畿", "中国", "四国", "九州", "沖縄"])
        new_pref = st.text_input("都道府県*", placeholder="例: 北海道")
        
        col_lat, col_lon = st.columns(2)
        with col_lat:
            new_lat = st.number_input("緯度*", value=35.0000, format="%.4f")
        with col_lon:
            new_lon = st.number_input("経度*", value=139.0000, format="%.4f")
            
        col_h, col_r = st.columns(2)
        with col_h:
            new_height = st.number_input("塔高(m)", min_value=0, value=20)
        with col_r:
            new_range = st.number_input("光達(海里)", min_value=0.0, value=18.0, step=0.5)
            
        new_lens = st.text_input("レンズの種類", placeholder="例: 2等フレネル式レンズ")
        
        col_v, col_s = st.columns(2)
        with col_v:
            new_visited = st.radio("訪問状況*", ["未訪問", "訪問済み"])
        with col_s:
            new_score = st.number_input("スコア(0-100)", min_value=0, max_value=100, value=0)
            
        new_desc = st.text_area("解説", placeholder="例: 積丹半島の先端に立つ絶景の灯台")
        
        submitted = st.form_submit_button("登録する")
        
        if submitted:
            if not new_name or not new_pref:
                st.sidebar.error("灯台名と都道府県を入力してください。")
            else:
                new_row = pd.DataFrame([{
                    "name": new_name,
                    "region": new_region,
                    "pref": new_pref,
                    "lat": new_lat,
                    "lon": new_lon,
                    "height": int(new_height),
                    "range_nm": new_range,
                    "lens": new_lens if new_lens else "不明",
                    "visited": new_visited,
                    "score": int(new_score),
                    "desc": new_desc if new_desc else "（解説なし）"
                }])
                df_updated = pd.concat([df, new_row], ignore_index=True)
                save_all_data(df_updated)
                st.sidebar.success(f"「{new_name}」をスプレッドシートに追加しました！")
                st.rerun()

# --- データの絞り込み・並び替え処理 ---
filtered_df = df.copy()

if selected_region != "すべて":
    filtered_df = filtered_df[filtered_df["region"] == selected_region]

if status_filter != "すべて":
    filtered_df = filtered_df[filtered_df["visited"] == status_filter]

if search_term:
    filtered_df = filtered_df[
        filtered_df["name"].astype(str).str.contains(search_term) | 
        filtered_df["pref"].astype(str).str.contains(search_term) |
        filtered_df["lens"].astype(str).str.contains(search_term)
    ]

if sort_option == "スコアが高い順":
    filtered_df = filtered_df.sort_values(by="score", ascending=False)
elif sort_option == "スコアが低い順":
    filtered_df = filtered_df.sort_values(by="score", ascending=True)
elif sort_option == "訪問済み優先":
    filtered_df["v_cat"] = pd.Categorical(filtered_df["visited"], categories=["訪問済み", "未訪問"], ordered=True)
    filtered_df = filtered_df.sort_values(by="v_cat").drop(columns=["v_cat"])
elif sort_option == "未訪問優先":
    filtered_df["v_cat"] = pd.Categorical(filtered_df["visited"], categories=["未訪問", "訪問済み"], ordered=True)
    filtered_df = filtered_df.sort_values(by="v_cat").drop(columns=["v_cat"])

# --- 地図描画ロジック ---
if len(filtered_df) > 0:
    center_lat = filtered_df["lat"].mean()
    center_lon = filtered_df["lon"].mean()
    zoom = 6 if selected_region == "すべて" and not search_term else 8
else:
    center_lat, center_lon, zoom = 36.5, 138.0, 5

m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom, tiles="OpenStreetMap")

for _, row in filtered_df.iterrows():
    icon_color = "green" if row["visited"] == "訪問済み" else "red"
    score_disp = f"{row['score']}点" if row['score'] > 0 else "未評価"
    
    popup_text = f"""
    <div style="width:200px">
        <b>{row['name']}</b> ({row['visited']})<br>
        ⭐ スコア: <b>{score_disp}</b><br>
        所在地: {row['pref']}<br>
        塔高: {row['height']}m / 光達: {row['range_nm']}海里<br>
        レンズ: <b>{row['lens']}</b><br>
        <hr style="margin:5px 0;">
        <small>{row['desc']}</small>
    </div>
    """
    
    folium.Marker(
        location=[row["lat"], row["lon"]],
        popup=folium.Popup(popup_text, max_width=250),
        tooltip=f"{row['name']} [{row['visited']} / {score_disp}]",
        icon=folium.Icon(color=icon_color, icon="info-sign")
    ).add_to(m)

    if show_range:
        folium.Circle(
            location=[row["lat"], row["lon"]],
            radius=row["range_nm"] * 1852,
            color="yellow",
            fill=True,
            fill_color="gold",
            fill_opacity=0.15,
            weight=1
        ).add_to(m)

# --- 画面レイアウト ---
col1, col2 = st.columns([2.8, 1.2])

with col1:
    st.subheader(f"表示中の灯台: {len(filtered_df)} 件")
    st_folium(m, width="100%", height=600)

with col2:
    st.subheader("📋 編集・クラウド同期")
    st.caption("変更して保存すると、Googleスプレッドシートに即時反映されます。")

    edited_df = st.data_editor(
        filtered_df[["name", "visited", "score", "pref"]],
        column_config={
            "name": st.column_config.Column("灯台名", disabled=True),
            "visited": st.column_config.SelectboxColumn(
                "ステータス",
                options=["未訪問", "訪問済み"],
                required=True,
            ),
            "score": st.column_config.NumberColumn(
                "スコア",
                min_value=0,
                max_value=100,
                step=1,
                format="%d点"
            ),
            "pref": st.column_config.Column("県", disabled=True)
        },
        hide_index=True,
        use_container_width=True,
        height=480,
        key="status_score_editor"
    )

    if st.button("💾 クラウドに保存する", use_container_width=True, type="primary"):
        for idx, row in edited_df.iterrows():
            df.loc[idx, "visited"] = row["visited"]
            df.loc[idx, "score"] = int(row["score"])
        
        save_all_data(df)
        st.success("Googleスプレッドシートに保存しました！")
        st.rerun()
