"""Create a source-only ZIP; never include runtime data, secrets, or old scaffolding."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parent.parent
out=root/'outputs'/'attendance-source.zip'
out.parent.mkdir(exist_ok=True)
directories=['attendance','config','deploy','docs','scripts','static','templates','.github']
files=['README.md','manage.py','manage.sh','Dockerfile','compose.yml','requirements.txt','requirements.lock','.gitignore','.gitattributes','.dockerignore']
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
    for name in files:
        archive.write(root/name,name)
    for name in directories:
        for path in (root/name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pyo'):
                archive.write(path,path.relative_to(root).as_posix())
print(out)
