"""Inspect/extract local backup archives without trusting member paths or links."""
import json
import pathlib
import sys
import tarfile

def extract(source, destination):
    root=pathlib.Path(destination).resolve()
    with tarfile.open(source,'r:gz') as archive:
        for member in archive.getmembers():
            name=pathlib.PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe archive member')
            target=(root/pathlib.Path(*name.parts)).resolve()
            if target!=root and root not in target.parents:
                raise ValueError('Unsafe archive path')
            if member.isdir():
                target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as src,target.open('wb') as dst:
                    import shutil
                    shutil.copyfileobj(src,dst)
                target.chmod(0o600)
    for name in ['live.dump','test.dump','config.env','manifest.json']:
        if not (root/name).is_file():
            raise ValueError('Incomplete backup: '+name)

if __name__=='__main__':
    extract(sys.argv[1],sys.argv[2])
