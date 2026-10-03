import os

os.makedirs('src/api', exist_ok=True)
with open('src/api/__init__.py', 'w') as f:
    pass

with open('src/api/dashboard.py', 'w', encoding='utf-8') as f:
    f.write('''import os
import aiosqlite
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import datetime

app = FastAPI(title="AUREXIS Command Center")

DB_PATH = "campaign_ledger.db"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AUREXIS HUD</title>
    <style>
        body {
            background-color: #0d0d0d;
            color: #00ffcc;
            font-family: 'Courier New', Courier, monospace;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }
        .container {
            background-color: #1a1a1a;
            padding: 40px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0, 255, 204, 0.2);
            width: 450px;
            border: 1px solid #333;
        }
        h1 {
            color: #fff;
            text-align: center;
            border-bottom: 2px solid #00ffcc;
            padding-bottom: 15px;
            margin-top: 0;
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .stat {
            display: flex;
            justify-content: space-between;
            margin: 20px 0;
            font-size: 1.3em;
            border-bottom: 1px dashed #333;
            padding-bottom: 5px;
        }
        .stat-label {
            color: #888;
        }
        .stat-value {
            font-weight: bold;
            text-shadow: 0 0 5px rgba(0,255,204,0.5);
        }
        .positive { color: #00ffcc; text-shadow: 0 0 5px rgba(0,255,204,0.5); }
        .negative { color: #ff3366; text-shadow: 0 0 5px rgba(255,51,102,0.5); }
        .neutral { color: #ffcc00; text-shadow: 0 0 5px rgba(255,204,0,0.5); }
    </style>
</head>
<body>
    <div class="container">
        <h1>AUREXIS HUD</h1>
        <div class="stat"><span class="stat-label">Today\\'s PnL:</span> <span class="stat-value" id="pnl">.00</span></div>
        <div class="stat"><span class="stat-label">Win Rate:</span> <span class="stat-value neutral" id="winrate">0.0%</span></div>
        <div class="stat"><span class="stat-label">Total Cycles:</span> <span class="stat-value" id="total_cycles">0</span></div>
        <div class="stat"><span class="stat-label">Active Cycles:</span> <span class="stat-value neutral" id="active_cycles">0</span></div>
    </div>
    <script>
        async function fetchStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                
                const pnlEl = document.getElementById('pnl');
                pnlEl.innerText = (data.today_pnl < 0 ? '-' : '') + '$' + Math.abs(data.today_pnl).toFixed(2);
                pnlEl.className = 'stat-value ' + (data.today_pnl >= 0 ? 'positive' : 'negative');
                
                document.getElementById('winrate').innerText = data.win_rate.toFixed(1) + '%';
                document.getElementById('total_cycles').innerText = data.total_closed;
                document.getElementById('active_cycles').innerText = data.active_cycles;
            } catch (error) {
                console.error('Error fetching stats:', error);
            }
        }
        setInterval(fetchStats, 5000);
        fetchStats();
    </script>
</body>
</html>
"""

@app.get("/")
async def get_dashboard():
    return HTMLResponse(content=HTML_TEMPLATE, status_code=200)

@app.get("/api/stats")
async def get_stats():
    if not os.path.exists(DB_PATH):
        return {
            "today_pnl": 0.0,
            "win_rate": 0.0,
            "total_closed": 0,
            "active_cycles": 0
        }
        
    today = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_ts = int(today.timestamp())
    
    async with aiosqlite.connect(DB_PATH) as db:
        # PnL for today
        cursor = await db.execute("SELECT SUM(cycle_pnl) FROM cycles WHERE state='IDLE' AND cycle_id >= ?", (today_ts,))
        row = await cursor.fetchone()
        today_pnl = row[0] if row and row[0] else 0.0
        
        # Total closed cycles
        cursor = await db.execute("SELECT COUNT(*), SUM(CASE WHEN cycle_pnl > 0 THEN 1 ELSE 0 END) FROM cycles WHERE state='IDLE'")
        row = await cursor.fetchone()
        total_closed = row[0] if row and row[0] else 0
        wins = row[1] if row and row[1] else 0
        win_rate = (wins / total_closed * 100.0) if total_closed > 0 else 0.0
        
        # Active cycles
        cursor = await db.execute("SELECT COUNT(*) FROM cycles WHERE state != 'IDLE'")
        row = await cursor.fetchone()
        active_cycles = row[0] if row and row[0] else 0
        
    return {
        "today_pnl": today_pnl,
        "win_rate": win_rate,
        "total_closed": total_closed,
        "active_cycles": active_cycles
    }
''')
    print("? Created src/api/dashboard.py")
