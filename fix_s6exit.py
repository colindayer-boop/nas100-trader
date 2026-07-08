import sys

filename = 'master_backtest.py'

with open(filename, 'r') as f:
    lines = f.readlines()

# Find start and end indices of the S6 EOD exit block
start = None
end = None
for i, line in enumerate(lines):
    if line.strip().startswith('# ── S6 EOD exit (close at day\'s close)'):
        start = i
    if line.strip().startswith('# ── ENTRIES ───────────────────────────────────────────────────────'):
        end = i
        break

if start is not None and end is not None:
    # Replace lines[start:end] with new block
    indent = '    '  # 4 spaces (assuming same as surrounding)
    new_block = [
        '        # ── S6 EOD exit (close at day\'s close) ─────────────────────\n',
        '        if is_last and s6["active"]:\n',
        '            c = s6_close.get(bar_date)\n',
        '            if pd.notna(c):\n',
        '                pnl = s6["shares"] * (c - s6["entry"]) * s6["dir"]\n',
        '                capital += pnl\n',
        '                tlog.append(dict(strategy="S6", sym="QQQ", year=ts.year,\n',
        '                                 month=ts.month, pnl=pnl, entry_dt=ts))\n',
        '            s6.update(active=False, dir=0, entry=0., shares=0.)\n',
        '\n'
    ]
    # Replace
    lines[start:end] = new_block
    # Note: we removed the original blank line after the block; we added our own newline at end.

with open(filename, 'w') as f:
    f.writelines(lines)