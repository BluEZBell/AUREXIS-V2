import os

def fix_event_bus():
    eb_path = 'src/core/event_bus.py'
    with open(eb_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the broken f-string
    target = 'logger.error(f"Error in subscriber {cb_name} for {event_type.__name__}:\\n{tb_str}")'
    
    # Wait, in the file it's actually split across two lines.
    # Let's just fix it using string replacement.
    
    content = content.replace('logger.error(f"Error in subscriber {cb_name} for {event_type.__name__}:\\n{tb_str}")', 'logger.error(f"Error in subscriber {cb_name} for {event_type.__name__}:\\\\n{tb_str}")')
    
    # Or more robustly, find the multi-line string and replace it.
    import re
    content = re.sub(r'logger\.error\(f"Error in subscriber \{cb_name\} for \{event_type\.__name__\}:\n\{tb_str\}"\)',
                     r'logger.error(f"Error in subscriber {cb_name} for {event_type.__name__}:\\n{tb_str}")', content)

    with open(eb_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("? event_bus.py fixed")

if __name__ == '__main__':
    fix_event_bus()
