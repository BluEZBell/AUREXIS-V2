import os

files = ['src/execution/sentinel.py', 'src/strategy/alpha_harvester.py']

for file_path in files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    import_str = "import src.core.config as config"
    
    if import_str not in content:
        print(f"[{file_path}] MISSING import")
        # Find a good place to insert: after imports
        lines = content.split('\n')
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                insert_idx = i + 1
        
        lines.insert(insert_idx, import_str)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        print(f"[{file_path}] FIXED")
    else:
        print(f"[{file_path}] ALREADY HAS import")
