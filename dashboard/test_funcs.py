from pathlib import Path
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / 'logs'

def tail_file(filepath, n=100):
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
        return ''.join(lines[-n:])
    except Exception as e:
        return f'Error reading {filepath}: {e}'

print('Testing tail_file on trader.log (last 2 lines):')
print(tail_file(LOG_DIR / 'trader.log', 2))
print()
print('Testing tail_file on hunt_overnight.log (last 2 lines):')
print(tail_file(LOG_DIR / 'hunt_overnight.log', 2))
print()
import json
print('Risk state overall:')
print(json.loads((LOG_DIR / 'risk_state.json').read_text()))
print('Risk state alpaca:')
print(json.loads((LOG_DIR / 'risk_state_alpaca.json').read_text()))
print('Risk state binance:')
print(json.loads((LOG_DIR / 'risk_state_binance.json').read_text()))
