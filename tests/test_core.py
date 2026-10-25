import base64, json, os, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core

class CoreTests(unittest.TestCase):
    def test_reject_nonlocal_and_shell_addresses(self):
        for text in ('8.8.8.8','127.0.0.1','192.168.1.1 & whoami','::1','0.0.0.0'):
            with self.assertRaises(core.SetupError):core.valid_ip(text)
        self.assertEqual(core.valid_ip('192.168.1.24'),'192.168.1.24')
    def test_no_excluded_app_in_catalog(self):
        self.assertNotIn('tizentube',json.dumps(core.CATALOG).lower())
    def test_config_maps_installed_id_without_guessing(self):
        apps=[{'name':'Stremio','id':'abcdefghij.RealApp'}]
        config=core.build_config([core.CATALOG[-1]],apps)
        self.assertEqual(config['favorites'][0]['match'],['abcdefghij.RealApp'])
        self.assertFalse(config['hideMissing'])
    def test_invalid_configuration_stops(self):
        for selected,zone in (([],'SGR01'),(core.CATALOG,'SGR01'),(core.CATALOG[:1],"SGR01';alert(1)")):
            with self.assertRaises(core.SetupError):core.build_config(selected,[],zone)
    def test_internal_apps_filtered(self):
        apps=[{'id':'2026ePop02.SmartTV','name':'2026.SmartTV.Kant'},{'id':'abcdefghij.Stremio','name':'Stremio'},{'id':'xvvl3S1TT1.TizenTubeStandalone','name':'TizenTube'},{'id':'org.tizen.netflix-app','name':'Netflix'}]
        self.assertEqual([a['name'] for a in core.user_apps(apps)],['Stremio','Netflix'])
    def test_no_nested_installer_or_private_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            stage=core.prepare_stage(core.build_config(core.CATALOG[:1],[]),Path(temp)/'stage')
            names=[p.name for p in stage.rglob('*') if p.is_file()]
            self.assertNotIn('config.local.example.js',names)
            self.assertNotIn('alarm.js',names)
            text='\n'.join(p.read_text(encoding='utf-8') for p in stage.rglob('*') if p.suffix in ('.js','.html','.xml','.css'))
            for secret in ('birthday-song.mp3','birthday-video.mp4','tv-token.json','TizenTubeStandalone'):
                self.assertNotIn(secret,text)
            self.assertIn('OpenHomeTV.Launcher',(stage/'config.xml').read_text())
    def test_backup_tampering_stops_installation(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);(p/'report.txt').write_text('original');core.manifest(p);core.verify_backup(p)
            (p/'report.txt').write_text('modified')
            with self.assertRaises(core.SetupError):core.verify_backup(p)
    def test_backup_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);outside=p/'private.txt';outside.write_text('private');folder=p/'backup';folder.mkdir()
            (folder/'manifest.json').write_text(json.dumps([{'file':'../private.txt','sha256':core.sha(outside)}]))
            with self.assertRaises(core.SetupError):core.verify_backup(folder)
    @unittest.skipUnless(sys.platform=='win32','DPAPI requires Windows')
    def test_windows_encryption_roundtrip(self):
        data=b'fake certificate material\x00\xff';encrypted=core.protect(data)
        self.assertNotIn(data,encrypted);self.assertEqual(core.protect(encrypted,True),data)
    def test_backup_report_and_certificate_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sdkroot=root/'sdk';sdkroot.mkdir();sdkdata=root/'sdk-data/profile';sdkdata.mkdir(parents=True)
            author=root/'author.p12';author.write_bytes(b'FAKE AUTHOR CERTIFICATE')
            dist=root/'distributor.p12';dist.write_bytes(b'FAKE DISTRIBUTOR CERTIFICATE')
            (sdkdata/'profiles.xml').write_text(f'<profiles active="tv" version="3.1"><profile name="tv"><profileitem key="{author}" password="fake-encrypted"/><profileitem key="{dist}" password="fake-encrypted"/></profile></profiles>')
            sdk=core.SDK(sdkroot)
            self.assertEqual(sdk.profiles(),['tv'])
            backup=core.make_backup(sdk,'192.168.1.24','tv',{'device':{'modelName':'TEST'}},[{'id':'app','name':'App'}],'inventory',{'platform_version':'10.0'},root/'data')
            report=json.loads((backup/'backup-report.json').read_text())
            self.assertFalse(report['usbExportImported']);self.assertFalse(report['previousInstallerPackageCaptured'])
            self.assertIn('not a full TV image',' '.join(report['limitations']))
            self.assertNotIn(b'FAKE AUTHOR', (backup/'signing.dpapi').read_bytes())
            core.verify_backup(backup)
    def test_restore_never_installs_an_unrelated_application(self):
        with tempfile.TemporaryDirectory() as temp:
            package=Path(temp)/'wrong.wgt'
            with zipfile.ZipFile(package,'w') as z:z.writestr('config.xml','<widget xmlns:tizen="http://tizen.org/ns/widgets"><tizen:application id="Other.App"/></widget>')
            with self.assertRaises(core.SetupError):core.install_package(None,'192.168.1.24',package)
    def test_rollback_requires_previous_package(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);(folder/'report.txt').write_text('baseline');core.manifest(folder)
            with self.assertRaises(core.SetupError):core.rollback(None,'192.168.1.24',folder)
    def test_startup_rejects_public_issuer_even_when_subject_mentions_partner(self):
        def tlv(tag,data):
            size=len(data)
            return bytes([tag])+ (bytes([size]) if size<128 else b'\x81'+bytes([size])) +data
        for issuer,allowed in ((b'VD DEVELOPER Public CA Class0',False),(b'VD DEVELOPER Partner CA Class0',True)):
            body=tlv(2,b'\x01')+tlv(0x30,b'')+tlv(0x30,tlv(0x0c,issuer))+tlv(0x30,b'VD DEVELOPER Partner CA Class0')
            certificate=tlv(0x30,tlv(0x30,body))
            with tempfile.TemporaryDirectory() as temp:
                package=Path(temp)/'test.wgt'
                with zipfile.ZipFile(package,'w') as z:
                    z.write(core.resources()/'launcher/config.xml','config.xml')
                    z.writestr('startup-service.js','test')
                    z.writestr('signature1.xml','<Signature xmlns="http://www.w3.org/2000/09/xmldsig#"><KeyInfo><X509Data><X509Certificate>'+base64.b64encode(certificate).decode()+'</X509Certificate></X509Data></KeyInfo></Signature>')
                if allowed:core.verify_startup_package(package)
                else:
                    with self.assertRaisesRegex(core.SetupError,'Partner distributor'):core.verify_startup_package(package)
    def test_malformed_signing_certificate_rejected(self):
        for cert in (b'',b'\x30\x82\xff',b'\x30\x01\x00',b'\x30\x80'):
            with self.assertRaises(core.SetupError):core.certificate_issuer_der(cert)
    def test_final_step_enables_welcome_only_after_fresh_backup(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            home=Path(temp);current=home/'devices/192.168.1.24/current';current.mkdir(parents=True)
            config=core.build_config(core.CATALOG[:1],[])
            self.assertNotEqual(config.get('welcomeReady'),True)
            (current/'config.json').write_text(json.dumps(config))
            (current/'install.json').write_text(json.dumps({'appId':core.APP_ID,'signedProfile':'test'}))
            sdk=SimpleNamespace(inventory=lambda ip:([],'inventory'),capability=lambda ip:{'platform_version':'10.0'})
            calls=[]
            with patch.object(core,'tv_info',return_value={'device':{}}),patch.object(core,'make_backup',side_effect=lambda *args:calls.append('backup') or home/'backup'),patch.object(core,'install',side_effect=lambda *args:calls.append(('install',args[3]))):
                core.finish_setup(sdk,'192.168.1.24','test',home)
            self.assertEqual(calls[0],'backup');self.assertTrue(calls[1][1]['welcomeReady'])
            self.assertEqual(calls[1][1]['favorites'],config['favorites'])
            with self.assertRaises(core.SetupError):core.finish_setup(sdk,'192.168.1.24','another-profile',home)

if __name__=='__main__':unittest.main()
