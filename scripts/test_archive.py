import importlib.util
import io
import pathlib
import tarfile
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('archive',pathlib.Path(__file__).resolve().parent.parent/'deploy/archive.py')
archive_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(archive_module)

class ArchiveTests(unittest.TestCase):
    def test_rejects_path_traversal_and_symlink(self):
        for bad in ['../escaped','/absolute','link']:
            with self.subTest(bad=bad),tempfile.TemporaryDirectory() as temp:
                source=pathlib.Path(temp)/'bad.tar.gz'
                with tarfile.open(source,'w:gz') as tar:
                    info=tarfile.TarInfo(bad)
                    if bad=='link':info.type=tarfile.SYMTYPE;info.linkname='/etc/passwd';tar.addfile(info)
                    else:info.size=1;tar.addfile(info,io.BytesIO(b'x'))
                with self.assertRaises(ValueError):archive_module.extract(source,pathlib.Path(temp)/'out')
    def test_restores_regular_files_and_rejects_incomplete_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            source=pathlib.Path(temp)/'good.tar.gz';out=pathlib.Path(temp)/'out'
            with tarfile.open(source,'w:gz') as tar:
                for name in ['live.dump','test.dump','config.env','manifest.json','signatures/live/a.png']:
                    info=tarfile.TarInfo(name);info.size=1;tar.addfile(info,io.BytesIO(b'x'))
            archive_module.extract(source,out)
            self.assertEqual((out/'signatures/live/a.png').read_bytes(),b'x')
            with tarfile.open(source,'w:gz') as tar:
                info=tarfile.TarInfo('live.dump');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
            with self.assertRaises(ValueError):archive_module.extract(source,pathlib.Path(temp)/'incomplete')

if __name__=='__main__':unittest.main()
