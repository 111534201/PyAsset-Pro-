import plotly.express as px
import plotly.graph_objects as go
import pandas as pd


# --- 資產配置圓餅圖 (維持不變) ---
def plot_asset_allocation_pie(stock_value, crypto_value):
    labels = ['股票 (Stocks)', '加密貨幣 (Crypto)']
    values = [stock_value, crypto_value]
    if stock_value <= 0 and crypto_value <= 0:
        values = [1, 1];
        labels = ['無資料', '無資料']

    fig = px.pie(names=labels, values=values, title='資產配置', hole=0.4,
                 color_discrete_sequence=px.colors.qualitative.Pastel)
    fig.update_traces(textinfo='percent+label')
    fig.update_layout(margin=dict(t=40, b=0, l=0, r=0))
    return fig


# --- 支出分析圓餅圖 (維持不變) ---
def plot_expense_pie(transactions_data, rates_twd_base):
    category_spending = {}
    for tx in transactions_data:
        amount = tx.get('amount', 0)
        currency = tx.get('currency', 'TWD')
        category = tx.get('category', '其他')
        rate = rates_twd_base.get(currency, 1.0) if currency != "TWD" else 1.0
        amount_twd = amount * rate
        category_spending[category] = category_spending.get(category, 0) + amount_twd

    if not category_spending:
        return px.pie(names=["無支出"], values=[1], title="尚無支出資料")

    df = pd.DataFrame(list(category_spending.items()), columns=['Category', 'Amount'])
    fig = px.pie(df, names='Category', values='Amount', title='支出類別分佈',
                 color_discrete_sequence=px.colors.qualitative.Set3)
    fig.update_traces(textinfo='percent+label')
    fig.update_layout(margin=dict(t=40, b=0, l=0, r=0))
    return fig


# --- 總資產歷史走勢圖 (維持不變) ---
def plot_net_worth_history(history_data):
    if not history_data:
        fig = go.Figure();
        fig.update_layout(title="尚無歷史資料")
        return fig
    df = pd.DataFrame(history_data)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')

    min_val = df['NetWorth'].min()
    max_val = df['NetWorth'].max()
    padding = (max_val - min_val) * 0.02 if max_val != min_val else max_val * 0.01

    fig = px.line(df, x='Date', y='NetWorth', title='資產成長走勢', markers=True)
    fig.update_layout(
        xaxis_title="日期", yaxis_title="總資產 (TWD)", hovermode="x unified",
        margin=dict(t=40, b=0, l=0, r=0),
        yaxis_range=[min_val - padding, max_val + padding]
    )
    return fig


# --- [重點修改] 個股走勢圖 (加入 MA 線功能) ---
def plot_price_history(df, title, show_ma5=False, show_ma20=False, show_ma60=False):
    """
    繪製個股歷史走勢，並疊加 MA 線
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"{title} - 暫無數據",
            xaxis={"visible": False}, yaxis={"visible": False},
            annotations=[dict(text="無法取得歷史數據", xref="paper", yref="paper", showarrow=False, font=dict(size=20))]
        )
        return fig

    # 1. 計算 MA 值 (使用 pandas rolling window)
    # 注意：如果資料筆數少於 window 大小，前面會出現 NaN，Plotly 會自動不畫，這是正常的
    if show_ma5:
        df['MA5'] = df['Close'].rolling(window=5).mean()
    if show_ma20:
        df['MA20'] = df['Close'].rolling(window=20).mean()
    if show_ma60:
        df['MA60'] = df['Close'].rolling(window=60).mean()

    # 2. 準備繪圖 (計算 Y 軸範圍)
    start_price = df['Close'].iloc[0]
    end_price = df['Close'].iloc[-1]
    line_color = "#FF5252" if end_price >= start_price else "#00C805"

    min_price = df['Close'].min()
    max_price = df['Close'].max()
    padding = (max_price - min_price) * 0.1 if max_price != min_price else max_price * 0.01
    y_range = [min_price - padding, max_price + padding]

    # 3. 建立基礎圖表 (收盤價線)
    # 這裡改用 go.Figure 比較好疊加多條線
    fig = go.Figure()

    # 加入收盤價主線
    fig.add_trace(go.Scatter(
        x=df['Datetime'], y=df['Close'],
        mode='lines', name='收盤價',
        line=dict(color=line_color, width=2)
    ))

    # 4. 疊加 MA 線 (如果使用者有勾選)
    if show_ma5:
        fig.add_trace(go.Scatter(
            x=df['Datetime'], y=df['MA5'],
            mode='lines', name='MA5 (週線)',
            line=dict(color='orange', width=1.5), opacity=0.8
        ))
    if show_ma20:
        fig.add_trace(go.Scatter(
            x=df['Datetime'], y=df['MA20'],
            mode='lines', name='MA20 (月線)',
            line=dict(color='royalblue', width=1.5), opacity=0.8
        ))
    if show_ma60:
        fig.add_trace(go.Scatter(
            x=df['Datetime'], y=df['MA60'],
            mode='lines', name='MA60 (季線)',
            line=dict(color='purple', width=1.5), opacity=0.8
        ))

    # 5. 優化圖表佈局
    fig.update_layout(
        title=f"{title}",
        xaxis_title=None,
        yaxis_title="股價",
        hovermode="x unified",
        margin=dict(t=40, b=20, l=0, r=0),
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(
            range=y_range,
            fixedrange=False, showgrid=True, gridcolor="#333"
        ),
        xaxis=dict(showgrid=False),
        legend=dict(
            orientation="h",  # 圖例水平排列
            yanchor="bottom", y=1.02,  # 放在圖表上方
            xanchor="right", x=1
        )
    )

    return fig