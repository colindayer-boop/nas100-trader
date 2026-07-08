import sys

filename = 'master_backtest.py'

with open(filename, 'r') as f:
    lines = f.readlines()

# 1. Update strats list near the detailed stats section
for i, line in enumerate(lines):
    if line.strip().startswith('strats  = ["S1","S2","S3","S4","S5"]'):
        lines[i] = 'strats  = ["S1","S2","S3","S4","S5","S6"]\n'
        break

# 2. Replace color definitions and usage
# Find the line where colors5 is defined in the chart section
for i, line in enumerate(lines):
    if line.strip().startswith('colors5 = {"S1":"#4c78a8","S2":"#f58518","S3":"#54a24b","S4":"#e45756","S5":"#9467bd"}'):
        # Replace with a dict that includes S6
        lines[i] = 'colors = {"S1":"#4c78a8","S2":"#f58518","S3":"#54a24b","S4":"#e45756","S5":"#9467bd","S6":"#8c564b"}\n'
        # Now we need to replace all occurrences of colors5[s] with colors[s] in the following lines
        # We'll do a second pass later
        break

# Replace occurrences of colors5[ in the chart section
for i, line in enumerate(lines):
    if 'colors5[' in line:
        lines[i] = line.replace('colors5[', 'colors[')

# Also need to replace any reference to colors5 as variable name (if used elsewhere)
# In the chart section they also use colors5 in the loop: for s in strats: ... color=colors5[s]
# Already handled.
# Also need to update the legend labels? They use label=s directly; fine.

# Also need to ensure that in the PER-STRATEGY BREAKDOWN and YEAR-BY-YEAR etc we still use strats (already updated)
# No further changes needed.

with open(filename, 'w') as f:
    f.writelines(lines)