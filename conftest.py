import sys
from pathlib import Path

# افزودن ریشه پروژه به sys.path تا پوشه src قابل import باشد
sys.path.insert(0, str(Path(__file__).parent))
