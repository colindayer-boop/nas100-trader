import sys

filename = 'master_backtest.py'

with open(filename, 'r') as f:
    lines = f.readlines()

# Find the line with the erroneous assignment
for i, line in enumerate(lines):
    if 'eff = 1.0 * combined_0 * combined_mult' in line:
        # Replace with correct line
        # Keep same indentation
        indent = len(line) - len(line.lstrip())
        lines[i] = ' ' * indent + '                eff = 1.0 * combined_mult  # full exposure scaled by vol and tsmom\n'
        break

with open(filename, 'w') as f:
    f.writelines(lines)