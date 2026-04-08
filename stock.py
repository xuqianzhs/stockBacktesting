import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

def run_backtest():
    # 1. 從輸入框讀取使用者設定的參數
    ticker = entry_ticker.get().strip()
    period = combo_period.get().strip()
    
    try:
        hold_days = int(entry_hold.get().strip())
        k_threshold = float(entry_k.get().strip())
    except ValueError:
        messagebox.showerror("錯誤", "持有天數必須是整數，K值門檻必須是數字！")
        return

    # 清空下方的報告文字框
    text_report.delete(1.0, tk.END)
    text_report.insert(tk.END, f"⏳ 正在下載 {ticker} 歷史資料並開始回測...\n")
    window.update() # 強制更新視窗畫面

    start_time = time.time()

    # 2. 獲取歷史資料
    df = yf.download(ticker, period=period, progress=False)

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    if df.empty:
        text_report.insert(tk.END, f"❌ 找不到資料，請確認股票代號是否正確。\n")
        return

    # 3. 計算 KD 指標
    low_9 = df['Low'].rolling(window=9).min()
    high_9 = df['High'].rolling(window=9).max()
    df['RSV'] = 100 * (df['Close'] - low_9) / (high_9 - low_9)

    K_list, D_list = [], []
    k, d = 50, 50 
    rsv_values = df['RSV'].values
    
    for rsv in rsv_values:
        if np.isnan(rsv):
            K_list.append(50)
            D_list.append(50)
        else:
            k = (2/3) * k + (1/3) * float(rsv)
            d = (2/3) * d + (1/3) * k
            K_list.append(k)
            D_list.append(d)

    df['K'] = K_list
    df['D'] = D_list

    # 4. 定義進場訊號
    df['Signal'] = (df['K'] < k_threshold) & (df['K'].shift(1) >= k_threshold)

    # 5. 計算未來 N 天的報酬統計
    df['Buy_Price'] = df['Open'].shift(-1)
    df['Sell_Price_Nd'] = df['Close'].shift(-(1 + hold_days))
    df['Max_High_Nd'] = df['High'].rolling(window=hold_days).max().shift(-(1 + hold_days))

    df['Return_Nd'] = (df['Sell_Price_Nd'] - df['Buy_Price']) / df['Buy_Price']
    df['Max_Potential_Nd'] = (df['Max_High_Nd'] - df['Buy_Price']) / df['Buy_Price']

    # 6. 萃取有交易訊號的紀錄
    trades = df[df['Signal']].copy()
    end_time = time.time()

    # 7. 將結果輸出到視窗的文字框中
    text_report.delete(1.0, tk.END) # 清除剛剛的讀取中文字
    report_str = "="*50 + "\n"
    report_str += f"📊 策略回測結果報告：【{ticker}】\n"
    report_str += f"📝 條件：K值跌破 {k_threshold} 買進，無腦持有 {hold_days} 天\n"
    report_str += "="*50 + "\n"

    if len(trades) > 0:
        win_rate = (trades['Return_Nd'] > 0).mean() * 100
        avg_return = trades['Return_Nd'].mean() * 100
        avg_max_potential = trades['Max_Potential_Nd'].mean() * 100
        
        report_str += f"🔹 總交易次數： {len(trades)} 次\n"
        report_str += f"🔹 策略勝率：   {win_rate:.2f}% (結算賺錢機率)\n"
        report_str += f"🔹 平均實際報酬： {avg_return:.2f}%\n"
        report_str += f"🔹 期間最大潛力： {avg_max_potential:.2f}%\n"
        report_str += f"⏱️ 運算時間：     {end_time - start_time:.3f} 秒\n"
        report_str += "-" * 50 + "\n"
        report_str += f"💡 歷史前五次交易明細：\n"
        
        display_trades = trades[['Close', 'K', 'Return_Nd', 'Max_Potential_Nd']].tail(5)
        for index, row in display_trades.iterrows():
            date_str = index.strftime('%Y-%m-%d')
            k_val = float(row['K'])
            ret = float(row['Return_Nd'])
            max_pot = float(row['Max_Potential_Nd'])
            report_str += f"日期: {date_str} | K值: {k_val:>4.1f} | 實際報酬: {ret*100:>6.2f}% | 最大漲幅: {max_pot*100:>6.2f}%\n"
    else:
        report_str += f"在過去 {period} 內，沒有出現符合 K < {k_threshold} 的訊號。\n"
        
    text_report.insert(tk.END, report_str)

    # 8. 繪製圖表
    if len(trades) > 0:
        plt.style.use('dark_background')
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)
        
        ax1.set_title(f"{ticker} Price & Buy Signals (K < {k_threshold})", fontsize=14, fontweight='bold', color='white')
        ax1.plot(df.index, df['Close'], color='cyan', linewidth=1.5, label='Close Price')
        ax1.scatter(trades.index, trades['Close'], marker='^', color='red', s=100, zorder=5, label='Buy Signal')
        ax1.legend(loc='upper left')
        ax1.grid(True, color='gray', linestyle='--', alpha=0.3)
        ax1.set_ylabel("Price")

        ax2.plot(df.index, df['K'], color='yellow', linewidth=1, label='K (Fast)')
        ax2.plot(df.index, df['D'], color='magenta', linewidth=1, label='D (Slow)')
        ax2.axhline(k_threshold, color='red', linestyle='--', linewidth=1.5, label=f'Oversold ({k_threshold})')
        ax2.legend(loc='upper left')
        ax2.grid(True, color='gray', linestyle='--', alpha=0.3)
        ax2.set_ylabel("KD Value")
        ax2.set_ylim(0, 100)

        plt.tight_layout()
        plt.show()

# ==========================================
# 建立 GUI 視窗介面
# ==========================================
window = tk.Tk()
window.title("量化交易回測系統")
window.geometry("550x550")
window.configure(padx=20, pady=20)

# 設定排版字體
font_label = ("微軟正黑體", 12)
font_entry = ("Arial", 12)

# --- 輸入區 ---
frame_input = tk.Frame(window)
frame_input.pack(fill=tk.X, pady=10)

# 股票代號
tk.Label(frame_input, text="股票代號:", font=font_label).grid(row=0, column=0, sticky="e", pady=5)
entry_ticker = tk.Entry(frame_input, font=font_entry, width=15)
entry_ticker.grid(row=0, column=1, padx=10)
entry_ticker.insert(0, "^IXIC")
tk.Label(frame_input, text="(台股請加 .TW，如 2330.TW)", font=("微軟正黑體", 10)).grid(row=0, column=2, sticky="w")

# 回測期間
tk.Label(frame_input, text="回測期間:", font=font_label).grid(row=1, column=0, sticky="e", pady=5)
combo_period = ttk.Combobox(frame_input, values=["1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "max"], font=font_entry, width=13)
combo_period.grid(row=1, column=1, padx=10)
combo_period.set("10y")

# 持有天數
tk.Label(frame_input, text="持有天數:", font=font_label).grid(row=2, column=0, sticky="e", pady=5)
entry_hold = tk.Entry(frame_input, font=font_entry, width=15)
entry_hold.grid(row=2, column=1, padx=10)
entry_hold.insert(0, "5")

# K值門檻
tk.Label(frame_input, text="K值買進門檻:", font=font_label).grid(row=3, column=0, sticky="e", pady=5)
entry_k = tk.Entry(frame_input, font=font_entry, width=15)
entry_k.grid(row=3, column=1, padx=10)
entry_k.insert(0, "10")

# --- 按鈕區 ---
btn_run = tk.Button(window, text="🚀 開始回測並產生圖表", font=("微軟正黑體", 14, "bold"), bg="#4CAF50", fg="white", command=run_backtest)
btn_run.pack(pady=15, fill=tk.X)

# --- 報告輸出區 ---
tk.Label(window, text="回測報告:", font=font_label).pack(anchor="w")
text_report = scrolledtext.ScrolledText(window, font=("Consolas", 11), height=12, bg="#1E1E1E", fg="#00FF00")
text_report.pack(fill=tk.BOTH, expand=True)
text_report.insert(tk.END, "設定好上方參數後，點擊「開始回測」即可看見結果。\n")

# 啟動視窗主迴圈
window.mainloop()