import sys
from pathlib import Path
# Allow bundled rpoffice next to packages
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from rpoffice.apps.pens import main  # type: ignore
raise SystemExit(main())
