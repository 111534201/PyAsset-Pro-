import streamlit as st
import data_manager as dm
import api_handler as ah
import chart_plotter as cp
import concurrent.futures
import time
import datetime
import pandas as pd

# --- 頁面配置 ---
st.set_page_config(
    page_title="PyAsset Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS 優化 (緊湊排版 + 無邊框按鈕) ---
st.markdown("""
<style>
    /* 1. 指標卡片樣式 */
    .stMetric {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #464b5c;
    }
    [data-testid="stMetricValue"] {
        font-size: 26px;
        font-weight: bold;
        font-family: 'Segoe UI', sans-serif;
    }

    /* 2. 列表按鈕優化 (移除邊框、背景，靠左對齊) */
    div.stButton > button:first-child {
        text-align: left;
        padding: 4px 10px;
        width: 100%;
        border: none;
        background-color: transparent;
        color: #FAFAFA;
        border-radius: 5px;
        transition: background-color 0.3s;
    }

    div.stButton > button:first-child:hover {
        background-color: #383b45;
        color: #FFFFFF;
        border: none;
    }

    /* 3. 強制縮減行距 */
    div[data-testid="column"] {
        display: flex;
        align-items: center;
    }

    div[data-testid="column"] p {
        margin-bottom: 0px !important;
        font-size: 16px;
    }

    /* 4. 分隔線緊湊化 */
    hr {
        margin-top: 5px !important;
        margin-bottom: 5px !important;
    }

    /* 5. 優化 Checkbox 排版 */
    [data-testid="stCheckbox"] {
        margin-top: -15px;
    }
    [data-testid="stCheckbox"] label {
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)


# --- 核心資料抓取 ---
@st.cache_data(ttl=600)
def fetch_all_data():
    global g_usd_rates, g_twd_rates, g_asset_prices

    portfolio = dm.load_portfolio()
    g_usd_rates = {}
    g_twd_rates = {}
    g_asset_prices = {}

    unique_stocks = set(s['symbol'] for s in portfolio['stocks'])
    unique_cryptos = set(c['id'] for c in portfolio['crypto'])

    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_usd_rates = executor.submit(ah.get_exchange_rates_usd_base)
        future_twd_rates = executor.submit(ah.get_exchange_rates)

        asset_futures = {}
        for symbol in unique_stocks:
            asset_futures[symbol] = executor.submit(ah.get_stock_price, symbol)

        for crypto_id in unique_cryptos:
            time.sleep(0.1)
            asset_futures[crypto_id] = executor.submit(ah.get_crypto_price, crypto_id)

        try:
            g_usd_rates = future_usd_rates.result() or {"TWD": 30.5}
        except:
            g_usd_rates = {"TWD": 30.5}

        try:
            g_twd_rates = future_twd_rates.result() or {"USD": 0.032}
        except:
            g_twd_rates = {"USD": 0.032}

        for key, future in asset_futures.items():
            try:
                price = future.result()
                g_asset_prices[key] = price
            except:
                g_asset_prices[key] = 0.0

    transactions = dm.load_transactions()
    realized_pnl = dm.load_realized_pnl()
    return g_usd_rates, g_twd_rates, g_asset_prices, portfolio, transactions, realized_pnl


# --- 輔助函式 ---
def calculate_new_avg_cost(old_shares, old_avg_unit_cost, new_shares, new_total_cost):
    total_shares = old_shares + new_shares
    if total_shares == 0: return 0.0
    total_cost_value = (old_shares * old_avg_unit_cost) + new_total_cost
    return total_cost_value / total_shares


def format_currency(value, currency):
    if currency == "TWD":
        return f"NT$ {value:,.0f}"
    else:
        return f"US$ {value:,.2f}"


def format_qty_display(qty, asset_type, currency):
    if asset_type == "Stock" and currency == "TWD":
        sheets = int(qty // 1000)
        odd = int(qty % 1000)
        if sheets > 0:
            return f"{sheets} 張 {odd} 股" if odd > 0 else f"{sheets} 張"
        else:
            return f"{qty:,.0f} 股"
    else:
        return f"{qty:,.6f}" if asset_type == "Crypto" else f"{qty:,.0f} 股"


# --- 主程式 ---
st.title("📈 PyAsset Pro 投資管家")

if 'filters' not in st.session_state:
    st.session_state.filters = {'month': '-- 全部 --', 'category': '-- 全部 --'}

if 'selected_asset_idx' not in st.session_state:
    st.session_state.selected_asset_idx = None

with st.spinner("正在同步數據..."):
    usd_rates, twd_rates, asset_prices, portfolio, transactions, realized_pnl_data = fetch_all_data()

usd_to_twd_rate = usd_rates.get("TWD", 30.5)

# --- 資料運算 ---
all_assets_data = []
total_stock_value_twd = 0.0
total_crypto_value_twd = 0.0
total_invested_twd_display = 0.0

# 1. 股票
for stock in portfolio['stocks']:
    raw_price = asset_prices.get(stock['symbol'], 0.0)
    avg_cost_unit = stock.get('avg_cost', 0.0)
    is_tw_stock = ".TW" in stock['symbol'] or stock.get('currency') == 'TWD'

    if is_tw_stock:
        curr_code = "TWD"
        market_val_native = raw_price * stock['shares']
        cost_total_native = avg_cost_unit * stock['shares']
        total_stock_value_twd += market_val_native
        total_invested_twd_display += cost_total_native
        pnl_val_native = market_val_native - cost_total_native
    else:
        curr_code = "USD"
        market_val_native = raw_price * stock['shares']
        cost_total_native = avg_cost_unit * stock['shares']
        total_stock_value_twd += (market_val_native * usd_to_twd_rate)
        total_invested_twd_display += (cost_total_native * usd_to_twd_rate)
        pnl_val_native = market_val_native - cost_total_native

    pnl_pct = (pnl_val_native / cost_total_native * 100) if cost_total_native > 0 else 0.0

    all_assets_data.append({
        "Type": "Stock", "ID": stock['symbol'], "Name": stock.get('name', stock['symbol']),
        "Qty": stock['shares'], "Currency": curr_code, "Price_Native": raw_price,
        "Cost_Unit": avg_cost_unit, "Cost_Total": cost_total_native,
        "Market_Val_Native": market_val_native, "PnL_Val": pnl_val_native, "PnL_Pct": pnl_pct,
        "Market_Val_TWD": market_val_native if curr_code == "TWD" else market_val_native * usd_to_twd_rate,
        "Chart_Ticker": stock['symbol']
    })

# 2. 加密貨幣
for crypto in portfolio['crypto']:
    price_twd_raw = asset_prices.get(crypto['id'], 0.0)
    price_usd = price_twd_raw / usd_to_twd_rate
    avg_cost_unit = crypto.get('avg_cost', 0.0)

    market_val_native = price_usd * crypto['amount']
    cost_total_native = avg_cost_unit * crypto['amount']
    market_val_twd = market_val_native * usd_to_twd_rate

    total_crypto_value_twd += market_val_twd
    total_invested_twd_display += (cost_total_native * usd_to_twd_rate)

    pnl_val_native = market_val_native - cost_total_native
    pnl_pct = (pnl_val_native / cost_total_native * 100) if cost_total_native > 0 else 0.0

    chart_ticker = f"{crypto.get('symbol', '').upper()}-USD" if crypto.get('symbol') else None

    all_assets_data.append({
        "Type": "Crypto", "ID": crypto['id'], "Name": crypto.get('name', crypto['id']).title(),
        "Qty": crypto['amount'], "Currency": "USD", "Price_Native": price_usd,
        "Cost_Unit": avg_cost_unit, "Cost_Total": cost_total_native,
        "Market_Val_Native": market_val_native, "PnL_Val": pnl_val_native,
        "PnL_Pct": pnl_pct, "Market_Val_TWD": market_val_twd,
        "Chart_Ticker": chart_ticker
    })

total_net_worth = total_stock_value_twd + total_crypto_value_twd
unrealized_pnl_twd = total_net_worth - total_invested_twd_display
total_roi = (unrealized_pnl_twd / total_invested_twd_display * 100) if total_invested_twd_display > 0 else 0.0

realized_pnl_total_twd = 0.0
for r in realized_pnl_data:
    pnl = r.get('pnl', 0.0)
    c = r.get('currency', 'USD')
    if c == 'TWD':
        realized_pnl_total_twd += pnl
    else:
        realized_pnl_total_twd += pnl * usd_to_twd_rate

dm.update_history(total_net_worth)

# --------------------------
# 前端介面
# --------------------------
c1, c2, c3, c4 = st.columns(4)
with c1: st.metric("總投入本金 (TWD)", f"NT$ {total_invested_twd_display:,.0f}")
with c2: st.metric("庫存現值 (TWD)", f"NT$ {total_net_worth:,.0f}")
with c3: st.metric("未實現損益 (TWD)", f"NT$ {unrealized_pnl_twd:,.0f}", delta=f"{total_roi:.2f}%")
with c4: st.metric("已實現損益 (TWD)", f"NT$ {realized_pnl_total_twd:,.0f}", delta="落袋為安")

st.divider()

tabs = st.tabs(["🚀 庫存與走勢", "📈 資產歷史", "💰 已實現損益", "📊 分布與記帳"])

# --- Tab 1: 庫存列表 (緊湊版) ---
with tabs[0]:
    if not all_assets_data:
        st.info("尚無庫存資產，請從左側新增。")
    else:
        st.caption("👇 **點選資產名稱以查看走勢圖**")

        h1, h2, h3, h4 = st.columns([3, 1, 2, 2])
        h1.markdown("**資產名稱**")
        h2.markdown("**幣別**")
        h3.markdown("**現值 (約台幣)**")
        h4.markdown("**報酬率 %**")
        st.markdown("<hr>", unsafe_allow_html=True)

        for i, asset in enumerate(all_assets_data):
            r1, r2, r3, r4 = st.columns([3, 1, 2, 2])

            if r1.button(f"{asset['Name']}", key=f"list_btn_{i}", help="點擊展開詳情"):
                st.session_state.selected_asset_idx = i

            r2.markdown(f"{asset['Currency']}")
            r3.markdown(f"NT$ {asset['Market_Val_TWD']:,.0f}")

            roi_color = "green" if asset['PnL_Pct'] >= 0 else "red"
            r4.markdown(f":{roi_color}[{asset['PnL_Pct']:.2f}%]")

            st.markdown("<hr style='margin: 0px; opacity: 0.2;'>", unsafe_allow_html=True)

        # 詳細資訊
        if st.session_state.selected_asset_idx is not None:
            if st.session_state.selected_asset_idx < len(all_assets_data):
                idx = st.session_state.selected_asset_idx
                asset = all_assets_data[idx]
                cc = asset['Currency']

                st.markdown(" ")
                st.subheader(f"📌 {asset['Name']} 持倉分析")

                with st.container(border=True):
                    row1_a, row1_b, row1_c = st.columns(3)
                    with row1_a: st.metric("個人報酬率", f"{asset['PnL_Pct']:.2f}%")
                    with row1_b: st.metric(f"未實現損益 ({cc})", format_currency(asset['PnL_Val'], cc))
                    with row1_c: st.metric(f"總投入成本 ({cc})", format_currency(asset['Cost_Total'], cc))
                    st.divider()
                    row2_d, row2_e, row2_f, row2_g = st.columns(4)
                    with row2_d:
                        st.write("**持有數量**");
                        st.markdown(f"#### {format_qty_display(asset['Qty'], asset['Type'], cc)}")
                    with row2_e:
                        st.write(f"**平均單價 ({cc})**");
                        st.markdown(f"#### {format_currency(asset['Cost_Unit'], cc)}")
                    with row2_f:
                        st.write(f"**目前市價 ({cc})**");
                        st.markdown(f"#### {format_currency(asset['Price_Native'], cc)}")
                    with row2_g:
                        st.write("**庫存現值 (折合台幣)**");
                        st.markdown(f"#### NT$ {asset['Market_Val_TWD']:,.0f}")

                st.markdown("### 📉 歷史股價走勢")
                c_ma1, c_ma2, c_ma3, c_range = st.columns([1, 1, 1, 4])
                with c_ma1:
                    show_ma5 = st.checkbox("MA5 (週)", value=True, key=f"ma5_{idx}")
                with c_ma2:
                    show_ma20 = st.checkbox("MA20 (月)", value=False, key=f"ma20_{idx}")
                with c_ma3:
                    show_ma60 = st.checkbox("MA60 (季)", value=False, key=f"ma60_{idx}")
                with c_range:
                    range_opts = ['1D', '1W', '1M', '1Y', 'All']
                    selected_range = st.radio("選擇區間", range_opts, index=2, horizontal=True, key=f"range_sel_{idx}",
                                              label_visibility="collapsed")

                if asset['Chart_Ticker']:
                    with st.spinner(f"正在載入 {selected_range} 走勢圖..."):
                        df_hist = ah.get_historical_data(asset['Chart_Ticker'], selected_range)
                        if df_hist is not None:
                            fig_price = cp.plot_price_history(df_hist, f"{asset['Name']} ({selected_range})", show_ma5,
                                                              show_ma20, show_ma60)
                            st.plotly_chart(fig_price, use_container_width=True)
                        else:
                            st.warning("⚠️ 無法取得此資產的歷史數據")
                else:
                    st.info("此資產暫不支援走勢圖功能")
            else:
                st.session_state.selected_asset_idx = None

with tabs[1]:
    history_data = dm.load_history()
    fig_hist = cp.plot_net_worth_history(history_data)
    st.plotly_chart(fig_hist, use_container_width=True)

with tabs[2]:
    if not realized_pnl_data:
        st.info("尚無賣出紀錄。")
    else:
        df_real = pd.DataFrame(realized_pnl_data)
        st.dataframe(df_real, use_container_width=True, column_config={
            "date": "日期", "name": "名稱", "type": "類型", "currency": "幣別",
            "sell_price": st.column_config.NumberColumn("賣出價", format="%.2f"),
            "buy_cost": st.column_config.NumberColumn("成本價", format="%.2f"),
            "pnl": st.column_config.NumberColumn("獲利金額", format="%.2f"),
            "roi": st.column_config.NumberColumn("報酬率", format="%.2f%%")
        })

with tabs[3]:
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("資產配置")
        st.plotly_chart(cp.plot_asset_allocation_pie(total_stock_value_twd, total_crypto_value_twd),
                        use_container_width=True)
    with c2:
        st.subheader("支出分析")
        tx_filtered = [tx for tx in transactions if (
                    st.session_state.filters['month'] == '-- 全部 --' or tx.get('date', '').startswith(
                st.session_state.filters['month']))]
        exp_rates = {"TWD": 1.0}
        for c, r in twd_rates.items():
            if r > 0:
                exp_rates[c] = 1 / r
        st.plotly_chart(cp.plot_expense_pie(tx_filtered, exp_rates), use_container_width=True)
    st.divider()
    st.dataframe(pd.DataFrame(transactions), use_container_width=True)

# ==========================================
# 側邊欄 (Sidebar)
# ==========================================
st.sidebar.header("資產管理")
if st.sidebar.button("🔄 強制刷新"): st.cache_data.clear(); st.rerun()

action_mode = st.sidebar.radio("模式", ["新增資產 (買入)", "賣出資產 (獲利結算)"], horizontal=True)

if action_mode == "新增資產 (買入)":
    with st.sidebar.expander("📈 股票管理", expanded=True):
        stock_market = st.radio("市場", ["TW (台股)", "US (美股)"], horizontal=True)
        stock_unit = "股";
        multiplier = 1
        if "TW" in stock_market:
            if "張" in st.radio("單位", ["張", "股"], horizontal=True): stock_unit = "張"; multiplier = 1000
        cost_curr = "TWD" if "TW" in stock_market else "USD"

        with st.form("add_stock"):
            s_id = st.text_input("代號 (如: 2330, AAPL)")
            s_qty = st.number_input(f"數量 ({stock_unit})", min_value=0, step=1)
            s_price = st.number_input(f"成交單價 ({cost_curr})", min_value=0.0, format="%.2f")
            if s_qty > 0 and s_price > 0: st.caption(
                f"💰 試算總成本: {format_currency(s_qty * multiplier * s_price, cost_curr)}")

            if st.form_submit_button("確認買入"):
                if s_id and s_qty > 0:
                    final_ticker = s_id.upper().strip()
                    if "TW" in stock_market and not final_ticker.endswith(".TW"): final_ticker += ".TW"
                    with st.spinner("驗證中..."):
                        info = ah.validate_stock_symbol(final_ticker)
                    if info:
                        shares = int(s_qty * multiplier)
                        total_cost = shares * s_price
                        portfolio = dm.load_portfolio()
                        exist = next((s for s in portfolio['stocks'] if s['symbol'] == info['symbol']), None)
                        if exist:
                            new_avg = calculate_new_avg_cost(exist['shares'], exist.get('avg_cost', 0), shares,
                                                             total_cost)
                            exist['shares'] += shares
                            exist['avg_cost'] = new_avg
                        else:
                            portfolio['stocks'].append(
                                {"symbol": info['symbol'], "name": info['name'], "currency": cost_curr,
                                 "shares": shares, "avg_cost": s_price})
                        dm.save_portfolio(portfolio)
                        st.cache_data.clear();
                        st.success(f"已買入 {info['name']}");
                        time.sleep(1);
                        st.rerun()
                    else:
                        st.error("無效代號")

    with st.sidebar.expander("₿ 加密貨幣管理", expanded=False):
        with st.form("add_crypto"):
            c_id = st.text_input("代號 (如 btc)")
            c_qty = st.number_input("數量", min_value=0.0, format="%.6f")
            c_price = st.number_input("成交單價 (USD)", min_value=0.0, format="%.6f")
            if c_qty > 0 and c_price > 0: st.caption(f"💰 試算總成本: US$ {c_qty * c_price:,.2f}")

            if st.form_submit_button("確認買入"):
                if c_id and c_qty > 0:
                    with st.spinner("搜尋..."):
                        info = ah.validate_crypto_id(c_id.lower().strip())
                    if info:
                        portfolio = dm.load_portfolio()
                        exist = next((c for c in portfolio['crypto'] if c['id'] == info['id']), None)
                        total_cost = c_qty * c_price
                        if exist:
                            new_avg = calculate_new_avg_cost(exist['amount'], exist.get('avg_cost', 0), c_qty,
                                                             total_cost)
                            exist['amount'] += c_qty
                            exist['avg_cost'] = new_avg
                        else:
                            portfolio['crypto'].append(
                                {"id": info['id'], "name": info['name'], "symbol": info['symbol'], "amount": c_qty,
                                 "avg_cost": c_price})
                        dm.save_portfolio(portfolio)
                        st.cache_data.clear();
                        st.success(f"已買入 {info['name']}");
                        time.sleep(1);
                        st.rerun()
                    else:
                        st.error("無效代號")

else:  # 賣出模式
    st.sidebar.warning("⚠️ 賣出後將計算已實現損益")

    with st.sidebar.expander("📉 賣出股票", expanded=True):
        stock_opts = ["(請選擇)"]
        stock_map = {}
        for i, s in enumerate(portfolio['stocks']):
            label = f"{s.get('name', s['symbol'])}"
            stock_opts.append(label);
            stock_map[label] = (i, s)

        sel_stock = st.selectbox("選擇股票", stock_opts)

        if sel_stock != "(請選擇)":
            idx, asset_data = stock_map[sel_stock]
            curr = asset_data.get('currency', 'TWD')
            max_qty = asset_data['shares']
            st.info(f"持有: {max_qty} 股 | 成本: {asset_data.get('avg_cost', 0)}")

            sell_mult = 1;
            sell_label = "股"
            if "TW" in asset_data['symbol'] or curr == "TWD":
                if "張" in st.radio("賣出單位", ["張", "股"], horizontal=True, key="sell_unit_stock"):
                    sell_mult = 1000;
                    sell_label = "張"

            with st.form("sell_stock_form"):
                sq = st.number_input(f"賣出數量 ({sell_label})", min_value=0.0, max_value=float(max_qty) / sell_mult)
                sp = st.number_input(f"賣出單價 ({curr})", min_value=0.0, format="%.2f")
                if st.form_submit_button("確認賣出"):
                    real_q = sq * sell_mult
                    if real_q > 0 and sp > 0:
                        avg = asset_data.get('avg_cost', 0)
                        pnl = (sp - avg) * real_q
                        roi = (pnl / (avg * real_q) * 100) if avg > 0 else 0
                        realized_pnl_data.append({
                            "date": datetime.date.today().strftime("%Y-%m-%d"),
                            "name": asset_data.get('name', ''), "type": "Stock", "currency": curr,
                            "sell_qty": real_q, "sell_price": sp, "buy_cost": avg, "pnl": pnl, "roi": roi
                        })
                        dm.save_realized_pnl(realized_pnl_data)
                        portfolio['stocks'][idx]['shares'] -= real_q
                        if portfolio['stocks'][idx]['shares'] <= 0: portfolio['stocks'].pop(idx)
                        dm.save_portfolio(portfolio);
                        st.cache_data.clear();
                        st.rerun()

    with st.sidebar.expander("📉 賣出加密貨幣", expanded=False):
        crypto_opts = ["(請選擇)"]
        crypto_map = {}
        for i, c in enumerate(portfolio['crypto']):
            label = f"{c.get('name', c['id'])}"
            crypto_opts.append(label);
            crypto_map[label] = (i, c)

        sel_crypto = st.selectbox("選擇幣種", crypto_opts)

        if sel_crypto != "(請選擇)":
            idx, asset_data = crypto_map[sel_crypto]
            curr = "USD"
            max_qty = asset_data['amount']
            st.info(f"持有: {max_qty} | 成本: {asset_data.get('avg_cost', 0)}")

            with st.form("sell_crypto_form"):
                cq = st.number_input("賣出數量", min_value=0.0, max_value=float(max_qty))
                cp_price = st.number_input("賣出單價 (USD)", min_value=0.0, format="%.6f")
                if st.form_submit_button("確認賣出"):
                    if cq > 0 and cp_price > 0:
                        avg = asset_data.get('avg_cost', 0)
                        pnl = (cp_price - avg) * cq
                        roi = (pnl / (avg * cq) * 100) if avg > 0 else 0
                        realized_pnl_data.append({
                            "date": datetime.date.today().strftime("%Y-%m-%d"),
                            "name": asset_data.get('name', ''), "type": "Crypto", "currency": curr,
                            "sell_qty": cq, "sell_price": cp_price, "buy_cost": avg, "pnl": pnl, "roi": roi
                        })
                        dm.save_realized_pnl(realized_pnl_data)
                        portfolio['crypto'][idx]['amount'] -= cq
                        if portfolio['crypto'][idx]['amount'] <= 0: portfolio['crypto'].pop(idx)
                        dm.save_portfolio(portfolio);
                        st.cache_data.clear();
                        st.rerun()

st.sidebar.divider()
# [新增] 記帳管理 (Tab: 新增 / 刪除)
with st.sidebar.expander("📒 記帳管理"):
    t_add, t_del = st.tabs(["➕ 新增", "➖ 刪除"])

    with t_add:
        with st.form("new_tx"):
            td = st.date_input("日期")
            ta = st.number_input("金額", min_value=0.0, format="%.2f")
            tc = st.text_input("幣別", "TWD")
            tcat = st.selectbox("類別", ['食物', '交通', '娛樂', '購物', '其他'])
            if st.form_submit_button("新增支出"):
                transactions.append({"date": str(td), "amount": ta, "currency": tc, "category": tcat})
                dm.save_transactions(transactions)
                st.cache_data.clear();
                st.rerun()

    with t_del:
        if not transactions:
            st.caption("尚無紀錄")
        else:
            opts = [f"{i}. {tx['date']} | {tx['category']} | {tx.get('currency', 'TWD')} {tx['amount']}" for i, tx in
                    enumerate(transactions)]
            sel_opt = st.selectbox("選擇要刪除的項目", opts, index=len(opts) - 1 if opts else 0)

            if st.button("❌ 確認刪除"):
                if sel_opt:
                    idx_to_del = int(sel_opt.split(".")[0])
                    if 0 <= idx_to_del < len(transactions):
                        transactions.pop(idx_to_del)
                        dm.save_transactions(transactions)
                        st.cache_data.clear()
                        st.success("已刪除！");
                        time.sleep(0.5);
                        st.rerun()