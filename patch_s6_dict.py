import sys

filename = 'master_backtest.py'

with open(filename, 'r') as f:
    lines = f.readlines()

# Find the S6 definition block after daily download
for i, line in enumerate(lines):
    if line.strip().startswith('# --- S6: SMA 5/20 crossover signal (daily) ---'):
        # Replace the next few lines until blank line before regime block
        # We'll replace lines i+1 through maybe i+6
        new_block = [
            '# --- S6: SMA 5/20 crossover signal (daily) ---\n',
            'close_q = daily["QQQ"]["Close"].squeeze()\n',
            'ma_fast = close_q.rolling(5).mean()\n',
            'ma_slow = close_q.rolling(20).mean()\n',
            'sig_raw = (ma_fast > ma_slow).astype(int)*2 - 1  # 1 for long, -1 for short\n',
            's6_sig = {d.date(): v for d, v in sig_raw.shift(1).fillna(0).items()}  # lagged signal\n',
            's6_open = {d.date(): v for d, v in daily["QQQ"]["Open"].squeeze().items()}\n',
            's6_close = {d.date(): v for d, v in daily["QQQ"]["Close"].squeeze().items()}\n',
            '\n'
        ]
        # Delete old lines up to the line before the regime comment (which starts with '# ── REGIME')
        j = i+1
        while j < len(lines) and not lines[j].strip().startswith('# ── REGIME & FILTER MAPS'):
            j += 1
        # Replace lines[i+1:j] with new_block (excluding the comment line itself)
        lines[i+1:j] = new_block
        break

with open(filename, 'w') as f:
    f.writelines(lines)