import sys

filename = 'master_backtest.py'

with open(filename, 'r') as f:
    lines = f.readlines()

# Fix line with 'eff = 1.0 * combined_0 * combined_mult'
for i, line in enumerate(lines):
    if 'eff = 1.0 * combined_0 * combined_mult' in line:
        lines[i] = line.replace('eff = 1.0 * combined_0 * combined_mult', 'eff = 1.0 * combined_mult')
        break

# Ensure s6_close is defined after s6_open
for i, line in enumerate(lines):
    if 's6_open = daily["QQQ"]["Open"].squeeze()' in line:
        # Insert after this line
        lines.insert(i+1, 's6_close = daily["QQQ"]["Close"].squeeze()\n')
        break

with open(filename, 'w') as f:
    f.writelines(lines)