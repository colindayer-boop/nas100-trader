import sys

filename = 'master_backtest.py'

with open(filename, 'r') as f:
    lines = f.readlines()

# Find the line after the table printing loop (after the for label, *_ in variants block)
for i, line in enumerate(lines):
    if line.strip().startswith('# ── DETAILED STATS: FULL SYSTEM'):
        # Insert before this line
        indent = len(line) - len(line.lstrip())
        lines.insert(i, ' ' * indent + 'print("DEBUG: after table")\n')
        break

with open(filename, 'w') as f:
    f.writelines(lines)