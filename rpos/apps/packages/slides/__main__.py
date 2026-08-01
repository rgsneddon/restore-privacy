import sys
from pathlib import Path
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from rpoffice.apps.slides import main  # type: ignore
raise SystemExit(main())
