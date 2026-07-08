# Prop Firm Challenge Playbook

This playbook provides practical guidance for using the system in **Challenge Mode** to maximize your chances of passing a proprietary trading firm evaluation (e.g., FTMO, FundedNext, MyForexFunds, etc.) while adhering strictly to their rules.

## Core Principles

1. **Capital Preservation Over Profit Maximization**: The goal is to pass, not to make as much money as possible.
2. **Consistency is Key**: Many firms require trading on a minimum number of days and consistent profitability.
3. **Avoid Forced Trades**: Only take high-quality setups that match your edge.
4. **Protect the Downside**: Use the built-in risk controls to prevent catastrophic losses.
5. **Know the Rules**: This playbook assumes a typical challenge structure, but you MUST read your specific firm's rulebook.

## Typical Challenge Rules (Verify Yours!)

| Rule Type            | Common Value          | What It Means                                                                 |
|----------------------|-----------------------|-------------------------------------------------------------------------------|
| **Profit Target**    | 8% - 10%              | You must achieve this profit to pass.                                         |
| **Max Daily Loss**   | 5%                    | If your account drops 5% from the start of the day, you fail (often intraday).|
| **Max Drawdown**     | 10%                   | If your equity drops 10% from the peak, you fail (may be trailing or fixed).  |
| **Consistency Rule** | e.g., 4 days          | You must be profitable on at least X out of the last Y days.                  |
| **Max Trades/Day**   | Often implied by rules| Some firms limit trades per day (e.g., 5) to prevent scalping.                |
| **News Trading**     | Often prohibited      | Avoid trading during high-impact news events.                                 |
| **Weekend Holding**  | Varies                | Some forbid holding positions over the weekend.                               |

> **Note**: Always check your challenge's specific rules. The above are common but not universal.

## How This System Helps You Comply

### 1. **Position Sizing (Risk Per Trade)**
- **Challenge Mode Setting**: `risk_multiplier = 0.5`
- **Effect**: Your position size is halved compared to the "live" setting.
- **Benefit**: 
  - Reduces the impact of any single loss.
  - Makes it much harder to hit the daily loss limit or max drawdown from a few bad trades.
  - Allows you to take more trades without overexposing the account.

### 2. **Daily Trade Limit**
- **Challenge Mode Setting**: `max_daily_trades = 15`
- **Effect**: The system will not allow new trades after 15 have been taken in a day.
- **Benefit**:
  - Prevents overtrading and revenge trading.
  - Encourages you to wait for the best setups.
  - Complies with any implicit or explicit trade count limits.

### 3. **Consecutive Loss Handling**
- **Challenge Mode Setting**: `max_consecutive_losses = 2`, `consecutive_loss_reduction = 0.5`
- **Effect**: 
  - After 2 losses in a row, the risk per trade is halved (applied on top of the 0.5 multiplier).
  - After 4 losses in a row, it would be halved again (0.5 * 0.5 = 0.25 of base risk).
- **Benefit**:
  - Automatically reduces risk during a losing streak.
  - Helps prevent a drawdown from accelerating.
  - Protects your capital when your strategy is temporarily out of sync.

### 4. **Daily Profit Lock**
- **Challenge Mode Setting**: `daily_profit_lock_threshold = 0.01` (1%), `daily_profit_lock_multiplier = 0.5`
- **Effect**:
  - Once you are up 1% for the day, the risk per trade is halved for the rest of the day.
  - If you are up 2%, it would be halved again (if the logic were cumulative, but it's not; it's a one-time adjustment once the threshold is crossed).
- **Benefit**:
  - Locks in daily profits, reducing the chance of giving back gains.
  - Helps achieve positive days consistently (important for consistency rules).
  - Reduces aggression after a good start, protecting the day's P&L.

### 5. **Strategy Selection**
- **Challenge Mode Setting**: `allowed_strategies = ["S1", "S2", "S3"]`
- **Effect**: The system will only take signals from the Asian (S1), London open (S2), and New York open (S3) sessions.
- **Benefit**:
  - These sessions are historically the most reliable for the strategies in this system.
  - Avoids the quieter, choppier periods (e.g., Friday afternoon, lunch times) where false signals are more common.
  - Focuses on the times when institutional liquidity is highest.

### 6. **Emergency Stop**
- **Challenge Mode Setting**: `emergency_drawdown_threshold = 0.10` (10%)
- **Effect**: If your current drawdown reaches 10% from peak equity, the system will not allow new trades.
- **Benefit**:
  - Acts as a final line of defense against breaching the challenge's max drawdown rule.
  - Note: The existing daily and monthly kill-switches (from `config.ini`) still operate independently and may trigger earlier.

### 7. **Broker-side SL/TP (Non-Negotiable)**
- **Setting**: `broker_side_sl_tp_required = true` (in all profiles)
- **Effect**: Every order sent by the system includes a stop-loss and take-profit price.
- **Benefit**:
  - Ensures your risk is defined and limited at the point of entry.
  - Protects you if your VPS or connection fails (the broker will still honor the SL/TP).
  - This is a requirement of most prop firms and a core tenet of risk management.

## Step-by-Step Guide to Running a Challenge

### Pre-Launch Checklist
1. **Read Your Rulebook**: Know your profit target, daily loss limit, max drawdown, consistency rules, and any other restrictions.
2. **Set the Mode**: 
   - Export `RISK_MODE=challenge` **OR** set `risk_mode = challenge` in the `[risk]` section of `config.ini`.
3. **Verify Risk Settings**: 
   - Open `config/risk_profiles.yaml` and confirm the `challenge` profile matches your risk tolerance (you can adjust the values if needed, but the defaults are a good starting point).
   - Ensure your `config.ini` has appropriate `daily_loss_limit` and `target_drawdown` (these are used by the existing kill-switch and DD-throttle; they should be set to values slightly *better* than your challenge limits to provide a buffer).
4. **Check Your Broker Connection**: 
   - Ensure your API keys are correct and you can connect to your demo/pro account.
   - Run a dry-run first: `python live_trader.py --dry-run`
5. **Start Fresh**: 
   - Begin the challenge with a clean account (no open positions from previous tests).
   - Note the starting equity; this is what the daily loss limit is usually based on.

### During the Challenge
1. **Monitor Daily P&L**: 
   - The system logs the daily P&L percentage. Keep an eye on it relative to your daily loss limit.
   - If you hit your daily loss limit, the existing kill-switch will halt new trading for the day.
2. **Watch Drawdown**:
   - The DD-throttle will automatically reduce size as you approach your `target_drawdown` (set this in `config.ini` to, e.g., 0.06 if your challenge limit is 0.10, to start reducing early).
   - If you hit the 10% emergency stop (from the challenge profile), no new trades will be allowed.
3. **Respect the Trade Limit**:
   - If you see the system not taking trades after a certain point, check the log for "MAX DAILY TRADES REACHED" (or similar). This is the `max_daily_trades` safety net.
4. **Let Winners Run (But Not Too Far)**:
   - The profit-lock will kick in after you are up 1% for the day, reducing size. This helps you keep the day green.
   - Avoid the urge to override this; remember, consistency beats greed.
5. **After a Loss**:
   - If you take two losses in a row, the system will automatically reduce size. Do not fight it; let the risk management work.
   - If you take three losses, the size will be reduced again (if you haven't already had a winning trade in between to reset the streak).
6. **End of Day Routine**:
   - Note whether you were profitable for the day (important for consistency rules).
   - Do not revenge-trade if you had a losing day; stick to the plan tomorrow.

### Post-Trade Analysis (Weekly)
1. **Review Trades**: 
   - Did you take any trades outside the allowed sessions (S1, S2, S3)? The system should have blocked them, but double-check.
   - Were any trades taken without SL/TP? The system attaches them, but verify in your broker's trade history.
2. **Check Risk Metrics**:
   - How many days did you hit the daily trade limit?
   - How often did the profit-lock or consecutive-loss reduction activate?
   - Did you ever approach the daily loss limit or drawdown limits?
3. **Adjust if Necessary** (Only Between Challenges!):
   - If you found yourself constantly hitting the trade limit and missing opportunities, you *might* consider increasing `max_daily_trades` slightly for the next attempt (but only after proving you can be disciplined).
   - If you were stopped out too frequently by the daily loss limit, you might need to improve your entry timing or consider a more conservative `risk_multiplier` (though 0.5 is already quite conservative).
   - **Never change settings during an active challenge**. Only adjust between attempts.

## Common Pitfalls & How to Avoid Them

| Pitfall                          | How the System Helps                          | What You Must Do                                                                 |
|----------------------------------|-----------------------------------------------|----------------------------------------------------------------------------------|
| **Overtrading**                  | `max_daily_trades` limit                      | Respect the limit; don't try to "game" it by closing trades early to reset count. |
| **Revenge Trading**              | Profit-lock and consecutive-loss reduction    | After a loss, take a break; let the system reduce size automatically.            |
| **Holding Losers Too Long**      | Pre-defined SL/TP (broker-enforced)           | Do not move your stop-loss; trust the validation.                                |
| **Overwinning and Giving Back**  | Daily profit-lock                             | Let the system reduce size after you are up for the day.                         |
| **Ignoring the Consistency Rule**| Daily P&L logging                             | Manually track your profitable days; ensure you meet the requirement.            |
| **Breaching Daily Loss Limit**   | Existing kill-switch + challenge mode settings| Monitor your daily P&L; stop trading for the day if you are close to the limit.  |
| **Exceeding Max Drawdown**       | Drawdown throttle + emergency stop            | Monitor equity curve; if drawdown is growing, consider pausing manually.         |

## Mental Checklist Before Each Trade
When the system generates a signal, ask yourself:
1. **Is this within an allowed session?** (The system already filtered for S1, S2, S3, but know the times.)
2. **Do I feel pressured to take this trade because I need to make money today?** (If yes, step back; the profit-loss will come from consistency, not heroics.)
3. **Am I up for the day?** (If yes, remember the profit-loss will reduce size; this is good.)
4. **Have I taken losses recently?** (If yes, the size is already reduced; trust the process.)
5. **Is my daily P&L close to the loss limit?** (If yes, consider skipping even if the system allows it.)
6. **Is my drawdown approaching the danger zone?** (If yes, consider sitting out.)

## Final Thoughts
Passing a prop challenge is as much about discipline and risk management as it is about having a good edge. This system, when run in Challenge Mode, is designed to enforce the disciplined, risk-averse approach that maximizes your odds of success.

Remember:
- **The goal is to survive and pass, not to hit the profit target as fast as possible.**
- **A slow, steady equity curve with small wins and minimal drawdowns is far more likely to pass than a volatile one with big swings.**
- **Trust the system's risk controls; they are there to protect you from yourself.**

Good luck, and trade safely!

---
*Last Updated: 2024-06-15*
*For use with the NAS100 Trading OS system.*
