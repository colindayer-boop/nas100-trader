import sys

def main():
    filename = 'master_backtest.py'
    with open(filename, 'r') as f:
        lines = f.readlines()

    # 1. Ensure S6 calculation block exists after daily download (should already be there from our earlier edit)
    # We'll just ensure it's present; if not, we could add but assume it's there.

    # 2. Add s6 state initialization after st4 initialization
    for i, line in enumerate(lines):
        if line.strip().startswith('st4 = {s: blank() for s in S4_SYMS}'):
            # Insert after this line
            indent = len(line) - len(line.lstrip())  # should be 4 spaces
            insertion = ' ' * indent + 's6 = dict(active=False, dir=0, entry=0., shares=0.)\n'
            lines.insert(i+1, insertion)
            break

    # 3. Add S6 entry logic at is_first after S5 ORB block
    # Find the line with '# ── S5 ORB at first bar of day ─────────────────────'
    for i, line in enumerate(lines):
        if line.strip().startswith('# ── S5 ORB at first bar of day'):
            # Find the end of that block (look for next line that starts with '# ── S3 entries at first block')
            # We'll insert after the S5 block ends (just before the S3 block comment)
            # Let's find the line where S3 block starts
            for j in range(i+1, len(lines)):
                if lines[j].strip().startswith('# ── S3 entries at first bar'):
                    # Insert before line j
                    indent = '    '  # 4 spaces (inside the for loop)
                    insert_lines = [
                        '        # ── S6: SMA crossover at first bar of day ─────────────────────\n',
                        '        if is_first and s6_sig.get(bar_date, 0) != 0 and s14_ok and can_enter:\n',
                        '            direction = int(s6_sig[bar_date])\n',
                        '            o = s6_open.get(bar_date)\n',
                        '            if pd.notna(o) and o > 0:\n',
                        '                eff = 1.0 * combined_0 * combined_mult  # full exposure scaled by vol and tsmom\n',
                        '                shrs = (capital * eff) / o\n',
                        '                s6.update(active=True, dir=direction, entry=o, shares=shrs)\n',
                        '\n'
                    ]
                    # Insert each line
                    for k, ins in enumerate(insert_lines):
                        lines.insert(j + k, ins)
                    break
            break

    # 4. Add S6 exit logic at is_last after S3 EOD exits block but before ENTRIES section
    # Find the line with '# ── S3 EOD exits + next-day signal queue ──────────────────────────'
    for i, line in enumerate(lines):
        if line.strip().startswith('# ── S3 EOD exits + next-day signal queue'):
            # Find the end of that block: look for the line that starts with '# ── ENTRIES'
            for j in range(i+1, len(lines)):
                if lines[j].strip().startswith('# ── ENTRIES'):
                    # Insert before line j
                    indent = '    '  # 4 spaces
                    insert_lines = [
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
                    for k, ins in enumerate(insert_lines):
                        lines.insert(j + k, ins)
                    break
            break

    # Write back
    with open(filename, 'w') as f:
        f.writelines(lines)

if __name__ == '__main__':
    main()