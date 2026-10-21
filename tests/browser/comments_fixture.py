from pathlib import Path
import sys,json,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from research_ui import build_research_model,render_research_page
from research_comments import prepare
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
portal=json.loads(subprocess.check_output(['git','show','origin/gh-pages:portal-data.json']))
model=build_research_model(portal);state=prepare(model['cases'])
(root/'portal-data.json').write_text(json.dumps(portal,ensure_ascii=False),encoding='utf-8')
(root/'research.html').write_text(render_research_page(model,comments=state),encoding='utf-8')
