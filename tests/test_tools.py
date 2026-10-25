import json,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core

class BundledToolsTests(unittest.TestCase):
    def bundle(self,root,extra=None):
        base=root/'resources/bundled-tools';base.mkdir(parents=True)
        with zipfile.ZipFile(base/'samsung-tools.zip','w') as z:
            for name in ['tools/sdb.exe','tools/ide/bin/tizen.bat','tools/certificate-manager/certificate-manager.exe']:
                z.writestr(name,'test stub')
            for name in core.REQUIRED_TOOLS:z.writestr('.info/'+name+'/'+name+'.list','installed')
            z.writestr('tools/certificate-manager/eclipse.ini','__MALHANI_SDK_ROOT__/jdk/bin/javaw.exe')
            if extra:z.writestr(extra,'untrusted')
        (base/'manifest.json').write_text(json.dumps({'sha256':core.sha(base/'samsung-tools.zip'),'version':'test-v1'}))
        return root/'resources'
    def test_relocation_progress_and_no_vendor_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);resources=self.bundle(root);progress=[]
            with patch.object(core,'resources',return_value=resources),patch.object(core,'command') as command:
                sdk=core.unpack_tools(root/'home',progress_bytes=lambda done,total:progress.append((done,total)))
                command.assert_not_called()
            self.assertFalse(sdk.missing_tools());self.assertTrue(sdk.ready)
            self.assertEqual(progress[-1][0],progress[-1][1])
            self.assertEqual([v[0] for v in progress],sorted(v[0] for v in progress))
            self.assertNotIn('__MALHANI_', (sdk.root/'tools/certificate-manager/eclipse.ini').read_text())
            self.assertTrue(sdk.data.is_relative_to(root/'home'))
    def test_archive_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);resources=self.bundle(root,'../../escape.txt')
            with patch.object(core,'resources',return_value=resources):
                with self.assertRaises(core.SetupError):core.unpack_tools(root/'home')
            self.assertFalse((root/'escape.txt').exists())
    def test_corrupted_bundle_stops_before_extracting(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);resources=self.bundle(root)
            with (resources/'bundled-tools/samsung-tools.zip').open('ab') as f:f.write(b'changed')
            with patch.object(core,'resources',return_value=resources):
                with self.assertRaisesRegex(core.SetupError,'integrity'):core.unpack_tools(root/'home')
            self.assertFalse((root/'home').exists())
    def test_reuse_complete_existing_tools(self):
        class Existing:
            def missing_tools(self):return []
        sdk=Existing()
        with patch.object(core,'find_sdk',return_value=sdk),patch.object(core,'download_sdk') as download:
            self.assertIs(core.ensure_tools(Path('unused')),sdk);download.assert_not_called()

if __name__=='__main__':unittest.main()
