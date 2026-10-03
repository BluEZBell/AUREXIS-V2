import os
import dotenv

with open('.env.test', 'w') as f:
    f.write('MT5_PATH="C:\\Program Files\\MetaTrader 5\\terminal64.exe"\n')

dotenv.load_dotenv('.env.test')
path = os.getenv('MT5_PATH')
print(f"Path is: {repr(path)}")
