"""Local-only Samsung TV setup. No rooting, package removal or third-party app payloads."""
from __future__ import annotations
import base64, concurrent.futures, ctypes, hashlib, io, ipaddress, json, os, re, shutil
import socket, subprocess, sys, tempfile, time, urllib.request, urllib.parse, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

VERSION = '0.1.0'
APP_ID = 'OpenHomeTV.Launcher'
APP_PACKAGE = 'OpenHomeTV'
STARTUP_ID = APP_PACKAGE + '.Startup'
REQUIRED_TOOLS = ('WebCLI','Certificate-Manager','cert-add-on','TV-SAMSUNG-Extension-Resources')
SDK_URL = 'https://download.tizen.org/sdk/Installer/tizen-sdk_10.0/web-cli_Tizen_SDK_10.0_windows-64.exe'
SDK_SHA256 = 'ad373548a261b4383b6f74d4a74eb853b439c726ceca331a451d89081b7f7920'
CATALOG = [
    {'title':'Netflix', 'match':['org.tizen.netflix-app','Netflix']},
    {'title':'YouTube', 'match':['9Ur5IzDKqV.TizenYouTube','YouTube']},
    {'title':'Unifi TV', 'match':['eNkE8geWIm.UnifiTV','Unifi TV 2.0','Unifi TV']},
    {'title':'Prime Video', 'match':['org.tizen.primevideo','Prime Video','Amazon Prime Video']},
    {'title':'Disney+', 'match':['MCmYXNxgcu.DisneyPlus','Disney+','Disney+ Hotstar']},
    {'title':'Spotify', 'match':['rJeHak5zRg.Spotify','Spotify']},
    {'title':'Stremio', 'match':['Stremio']},
]
LIMITS = [
    'This is not a full TV image or guaranteed factory recovery backup.',
    'Protected TV settings, accounts, installed third-party app binaries and app data cannot be exported by this installer.',
    'Developer Mode and the PC address have already been changed by the owner before SDK inventory is possible.',
    'A pre-existing launcher package cannot be extracted. Rollback is available only for packages previously installed and archived by this installer.',
    'Launcher configuration saved on the PC is the last installer-generated configuration; later edits made only on the TV are not exported.',
    'Encrypted signing backup can be decrypted only by the same Windows account on the same machine. Certificate passwords remain with the owner.',
    'USB settings backup support varies by model; only an imported export is counted as captured.',
]
class SetupError(Exception): pass

def resources() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))

def data_home() -> Path:
    return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'OpenHomeTV'

def sha(path: Path) -> str:
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def valid_ip(value: str) -> str:
    try: addr=ipaddress.IPv4Address(value.strip())
    except ValueError: raise SetupError('Enter a valid local IPv4 TV address.')
    if not addr.is_private or addr.is_loopback or addr.is_multicast or addr.is_unspecified or str(addr).endswith('.255'):
        raise SetupError('Use the TV’s private home-network IPv4 address.')
    return str(addr)

def request_json(ip: str, path='/api/v2/', method='GET'):
    ip=valid_ip(ip)
    # Local traffic must not be sent through the user's Internet proxy.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(f'http://{ip}:8001{path}',method=method),timeout=3) as response:
        raw=response.read(2*1024*1024+1)
        if len(raw)>2*1024*1024: raise SetupError('TV returned an unexpectedly large response.')
        return json.loads(raw)

def tv_info(ip):
    result=request_json(ip)
    if not isinstance(result,dict) or not isinstance(result.get('device'),dict): raise SetupError('This address did not report a Samsung TV device.')
    device=result['device']
    if str(device.get('type','')).lower() not in ('samsung smarttv','samsung smart tv') and not any(k in device for k in ('modelName','model')):
        raise SetupError('Could not verify a Samsung TV at this address.')
    return result

def pc_ip_for(ip):
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.connect((valid_ip(ip),8001)); return s.getsockname()[0]

def port_open(ip,port=26101):
    try:
        with socket.create_connection((valid_ip(ip),port),timeout=1): return True
    except OSError: return False

def discover(seconds=3):
    message=('M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n').encode()
    addresses=set()
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
        s.settimeout(.4); s.sendto(message,('239.255.255.250',1900)); end=time.monotonic()+seconds
        while time.monotonic()<end:
            try:
                raw,peer=s.recvfrom(65535)
                if b'samsung' in raw.lower(): addresses.add(valid_ip(peer[0]))
            except (OSError,SetupError): pass
    def inspect(ip):
        try:
            info=tv_info(ip); d=info['device']; return {'ip':ip,'name':d.get('name',info.get('name','Samsung TV')),'model':d.get('modelName',d.get('model','Unknown'))}
        except Exception: return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        return [d for d in pool.map(inspect,sorted(addresses)) if d]

def command(args,timeout=60,cwd=None):
    args=[str(x) for x in args]
    # SDK .bat entry points are executed through cmd with quoted, validated arguments.
    if args[0].lower().endswith(('.bat','.cmd')):
        if any(re.search(r'[&|<>^%!\r\n"]',x) for x in args): raise SetupError('SDK paths/profile names must not contain shell control characters.')
        args=[os.environ.get('COMSPEC','cmd.exe'),'/d','/s','/c',subprocess.list2cmdline(args)]
    try:
        p=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,text=True,errors='replace',timeout=timeout,cwd=cwd,
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.TimeoutExpired: raise SetupError('The Samsung tool timed out. Leave the TV on and retry.')
    if p.returncode: raise SetupError((p.stdout+'\n'+p.stderr).strip()[-2500:] or 'Samsung tool failed.')
    return p.stdout+'\n'+p.stderr

def sdk_roots(extra=''):
    roots=[Path(extra)] if extra else []
    if os.environ.get('TIZEN_SDK_PATH'): roots.append(Path(os.environ['TIZEN_SDK_PATH']))
    roots += [data_home()/'tizen-studio',Path.home()/'tizen-studio',Path('C:/tizen-studio'),Path('C:/tools/tizen-studio')]
    config=Path.home()/'.tizen.sdk.path.config'
    if config.is_file():
        for line in config.read_text(errors='replace').splitlines():
            if '=' in line:
                value=line.split('=',1)[1].strip()
                if value: roots.append(Path(value))
    return list(dict.fromkeys(roots))

class SDK:
    def __init__(self,root):
        self.root=Path(root).resolve(); self.sdb=self.root/'tools/sdb.exe'; self.cli=self.root/'tools/ide/bin/tizen.bat'
        self.manager=self.root/'tools/certificate-manager/certificate-manager.exe'
        self.packages=self.root/'package-manager/package-manager.exe'
        self.data=self.root.parent/(self.root.name+'-data')
        info=self.root/'sdk.info'
        if info.exists():
            for line in info.read_text(errors='replace').splitlines():
                if line.startswith('TIZEN_SDK_DATA_PATH='): self.data=Path(line.split('=',1)[1].strip())
    @property
    def ready(self): return self.sdb.is_file() and self.cli.is_file()
    def missing_tools(self):
        missing=[name for name in REQUIRED_TOOLS if not (self.root/'.info'/name/(name+'.list')).is_file()]
        if not self.ready and 'WebCLI' not in missing:missing.append('WebCLI')
        if not self.manager.is_file() and 'Certificate-Manager' not in missing:missing.append('Certificate-Manager')
        return missing
    @property
    def can_install_tools(self):
        return (self.root/'jdk/bin/java.exe').is_file() and (self.root/'package-manager/PackageManagerV2-cli.jar').is_file()
    @property
    def profile_file(self): return self.data/'profile/profiles.xml'
    def profiles(self):
        if not self.profile_file.is_file(): return []
        try: root=ET.parse(self.profile_file).getroot()
        except ET.ParseError: return []
        found=[]
        for profile in root.findall('profile'):
            name=profile.get('name','')
            keys=[Path(x.get('key','')) for x in profile.findall('profileitem') if x.get('key')]
            if re.fullmatch(r'[\w .-]{1,80}',name) and len(keys)>=2 and all(k.is_file() for k in keys): found.append(name)
        return found
    def connect(self,ip):
        command([self.sdb,'connect',valid_ip(ip)],15)
        listing=command([self.sdb,'devices'],10)
        if not re.search(re.escape(ip+':26101')+r'\s+device\b',listing): raise SetupError('Developer connection is not ready. Check Developer Mode, PC address, then restart the TV.')
    def inventory(self,ip):
        self.connect(ip)
        text=command([self.sdb,'-s',ip+':26101','shell','0','applist'],20)
        apps=[{'name':m[0],'id':m[1]} for m in re.findall(r"'([^'\r\n]*)'\s+'([^'\r\n]+)'",text)]
        if not apps: raise SetupError('Samsung did not expose an app inventory. Nothing will be installed without a recorded baseline.')
        return apps,text
    def capability(self,ip):
        text=command([self.sdb,'-s',ip+':26101','capability'],15)
        return dict(line.split(':',1) for line in text.splitlines() if ':' in line)
    def open_certificates(self):
        if not self.manager.is_file(): raise SetupError('Install Certificate-Manager and Samsung Certificate Extension in Package Manager first.')
        subprocess.Popen([str(self.manager)],cwd=str(self.manager.parent))
    def open_packages(self):
        if not self.packages.is_file(): raise SetupError('Package Manager was not found in this SDK.')
        subprocess.Popen([str(self.packages)],cwd=str(self.packages.parent))

def match_app(spec,apps):
    targets={x.casefold() for x in spec['match']}
    return next((a for a in apps if a['id'].casefold() in targets or a['name'].casefold() in targets),None)

def user_apps(apps):
    builtins={'org.tizen.netflix-app','org.tizen.primevideo','org.tizen.browser','com.samsung.tv.SmartThingsApp'}
    return [a for a in apps if a['id'] in builtins or (re.match(r'^[A-Za-z0-9]{10}\.',a['id']) and not re.search(r'service|factory|test|launcher|epop|promotion|emanual|tizentube',a['id']+' '+a['name'],re.I))]

def protect(data, decrypt=False):
    if sys.platform!='win32': raise SetupError('Encrypted signing backups require Windows DPAPI.')
    from ctypes import wintypes
    class BLOB(ctypes.Structure): _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]
    buf=ctypes.create_string_buffer(data); src=BLOB(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte))); dst=BLOB()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True); kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    function=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes=[ctypes.POINTER(BLOB),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(BLOB)]
    function.restype=wintypes.BOOL; kernel.LocalFree.argtypes=[ctypes.c_void_p]
    if not function(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dst)): raise SetupError('Windows could not protect the certificate backup.')
    try: return ctypes.string_at(dst.pbData,dst.cbData)
    finally: kernel.LocalFree(dst.pbData)

def signing_bundle(sdk,profile):
    root=ET.parse(sdk.profile_file).getroot(); selected=next((p for p in root.findall('profile') if p.get('name')==profile),None)
    if selected is None: raise SetupError('Choose a valid Samsung TV signing profile first.')
    filtered=ET.Element('profiles',{'active':profile,'version':root.get('version','3.1')}); filtered.append(selected)
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('profiles.xml',ET.tostring(filtered,encoding='utf-8'))
        seen=set()
        for item in selected.findall('profileitem'):
            for field in ('key','ca','rootca'):
                path=Path(item.get(field,''))
                if path.is_file() and path.suffix.lower() in ('.p12','.pem','.crt','.cer') and str(path) not in seen:
                    seen.add(str(path)); archive.write(path,f'certificates/{len(seen):02d}-{path.name}')
    return stream.getvalue()

def manifest(folder):
    folder=Path(folder)
    records=[{'file':p.relative_to(folder).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='manifest.json']
    (folder/'manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    verify_backup(folder)

def verify_backup(folder):
    folder=Path(folder).resolve()
    for row in json.loads((folder/'manifest.json').read_text(encoding='utf-8')):
        target=(folder/row['file']).resolve()
        if not target.is_relative_to(folder) or not target.is_file() or sha(target)!=row['sha256']: raise SetupError('Backup integrity check failed. Installation stopped.')

def make_backup(sdk,ip,profile,info,apps,inventory,caps,home,usb=None):
    home=Path(home); backup=home/'backups'/ip/datetime.now().strftime('%Y%m%d-%H%M%S-%f'); backup.mkdir(parents=True)
    (backup/'device.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    (backup/'installed-apps.json').write_text(json.dumps(apps,indent=2),encoding='utf-8')
    (backup/'installed-apps.txt').write_text(inventory,encoding='utf-8')
    (backup/'capabilities.json').write_text(json.dumps(caps,indent=2),encoding='utf-8')
    bundle=signing_bundle(sdk,profile); encrypted=protect(bundle)
    if protect(encrypted,decrypt=True)!=bundle: raise SetupError('Signing backup verification failed.')
    (backup/'signing.dpapi').write_bytes(encrypted)
    previous=home/'devices'/ip/'current'
    if previous.is_dir(): shutil.copytree(previous,backup/'previous-installer-version')
    usb_captured=False
    if usb:
        usb=Path(usb).resolve()
        if usb==Path(usb.anchor): raise SetupError('Select the exported backup folder, not an entire drive.')
        files=[p for p in usb.rglob('*') if p.is_file() and not p.is_symlink()]
        if not files: raise SetupError('The selected USB backup folder is empty.')
        if sum(p.stat().st_size for p in files)>4*1024**3: raise SetupError('USB export exceeds the 4 GB import limit. Keep it separately and retry without importing it.')
        for source in files:
            target=backup/'usb-export'/source.relative_to(usb); target.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(source,target)
        usb_captured=True
    report={'tvIP':ip,'signingProfile':profile,'created':datetime.now().astimezone().isoformat(),'captured':['TV-reported device information','Installed app inventory','SDK capabilities','Selected signing profile/certificates encrypted with Windows DPAPI'],
            'usbExportImported':usb_captured,'previousInstallerPackageCaptured':previous.is_dir(),'limitations':LIMITS}
    (backup/'backup-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (backup/'README.txt').write_text('MALHANI LAUNCHER BACKUP\n\n'+ '\n'.join(LIMITS)+'\n\nCertificates are encrypted in signing.dpapi. Never upload this backup to GitHub.\n',encoding='utf-8')
    manifest(backup); return backup

def build_config(selected,apps,zone='SGR01',place='Semenyih · Hulu Langat',clock24=True,prayer=True):
    if not re.fullmatch(r'[A-Z]{3}\d{2}',zone): raise SetupError('Enter a JAKIM zone such as SGR01 or WLY01.')
    favorites=[]
    for spec in selected:
        installed=match_app(spec,apps)
        favorites.append({'title':spec['title'],'match':[installed['id']] if installed else spec['match'],'bg':'#22242b'})
    if not favorites: raise SetupError('Choose at least one app shortcut.')
    if len(favorites)>6: raise SetupError('Choose up to six app shortcuts.')
    return {'returnToLauncher':True,'launcherOnPowerOn':True,'fastStart':True,'clock24h':bool(clock24),'hideMissing':False,
            'weather':{'latitude':None,'longitude':None},'idleSource':None,'wallpapers':{'minutes':.5},'favorites':favorites,
            'prayer':{'enabled':bool(prayer),'zone':zone,'place':place.strip()[:100]}}

def prepare_stage(config,destination):
    dest=Path(destination)
    if dest.exists(): raise SetupError('Build staging directory must be new.')
    shutil.copytree(resources()/'launcher',dest)
    forbidden={'.p12','.wgt','.mp4','.wav','.mp3','.dpapi'}
    if any(p.is_file() and p.suffix.lower() in forbidden for p in dest.rglob('*')): raise SetupError('Unexpected private media, certificate or package in public resources.')
    (dest/'config.local.js').write_text('var LAUNCHER_LOCAL = '+json.dumps(config,ensure_ascii=True,indent=2)+';\n',encoding='utf-8')
    return dest

def download_sdk(target,progress=lambda value:None):
    target=Path(target); target.parent.mkdir(parents=True,exist_ok=True); temp=target.with_suffix('.part')
    with urllib.request.urlopen(SDK_URL,timeout=30) as response, open(temp,'wb') as out:
        total=int(response.headers.get('Content-Length','0')); count=0
        while True:
            chunk=response.read(1024*1024)
            if not chunk: break
            count+=len(chunk)
            if count>500*1024*1024: raise SetupError('SDK download exceeded its expected size.')
            out.write(chunk); progress(f'Downloading Samsung tools: {count//1048576} MB'+(f' / {total//1048576} MB' if total else ''))
    if sha(temp)!=SDK_SHA256: temp.unlink(missing_ok=True); raise SetupError('Samsung installer checksum did not match. Nothing was executed.')
    temp.replace(target); return target

def find_sdk(preferred=''):
    candidates=[SDK(root) for root in sdk_roots(preferred)]
    return next((sdk for sdk in candidates if sdk.ready),None) or next((sdk for sdk in candidates if sdk.can_install_tools),None)

def unpack_tools(home,progress=lambda value:None,progress_bytes=lambda done,total:None):
    source=resources()/'bundled-tools';bundle=source/'samsung-tools.zip'
    metadata=json.loads((source/'manifest.json').read_text(encoding='utf-8'))
    if sha(bundle)!=metadata['sha256']:raise SetupError('The bundled Samsung tools failed their integrity check.')
    version=metadata['version']
    if not re.fullmatch(r'[A-Za-z0-9._-]+',version):raise SetupError('Invalid tools bundle version.')
    parent=Path(home).resolve()/'toolsets'/version;parent.mkdir(parents=True,exist_ok=True)
    dest=parent/'tizen-studio';data=parent/'tizen-studio-data'
    sdk=SDK(dest)
    if sdk.ready and not sdk.missing_tools():return sdk
    progress('Preparing bundled Samsung tools…')
    with tempfile.TemporaryDirectory(dir=parent,prefix='extract-') as temp:
        stage=Path(temp)/'sdk';stage.mkdir()
        with zipfile.ZipFile(bundle) as archive:
            entries=archive.infolist();total=sum(x.file_size for x in entries);done=0
            for entry in entries:
                path=(stage/entry.filename).resolve()
                if not path.is_relative_to(stage.resolve()) or ':' in entry.filename or (entry.external_attr>>16)&0o170000==0o120000:
                    raise SetupError('Invalid file path in Samsung tools bundle.')
                if entry.is_dir():path.mkdir(parents=True,exist_ok=True);continue
                path.parent.mkdir(parents=True,exist_ok=True)
                content=archive.read(entry)
                if b'__MALHANI_SDK_' in content:
                    content=content.replace(b'__MALHANI_SDK_ROOT__',str(dest).replace('\\','/').encode()).replace(b'__MALHANI_SDK_DATA__',str(data).replace('\\','/').encode())
                path.write_bytes(content);done+=entry.file_size;progress_bytes(done,total)
        (stage/'sdk.info').write_text('TIZEN_SDK_INSTALLED_PATH='+str(dest)+'\nTIZEN_SDK_DATA_PATH='+str(data)+'\n',encoding='utf-8')
        if dest.exists():
            preserved=parent/('incomplete-tools-'+str(time.time_ns()))
            dest.rename(preserved)
        stage.rename(dest)
    sdk=SDK(dest)
    if not sdk.ready or sdk.missing_tools():raise SetupError('Bundled Samsung tools are incomplete.')
    return sdk

def ensure_tools(home,preferred='',progress=lambda value:None,progress_bytes=lambda done,total:None):
    home=Path(home);sdk=find_sdk(preferred)
    if sdk and not sdk.missing_tools():return sdk
    if (resources()/'bundled-tools/samsung-tools.zip').is_file():
        return unpack_tools(home,progress,progress_bytes)
    if sdk is None:
        target=home/'downloads/Tizen-SDK-10-CLI.exe'
        if not target.is_file() or sha(target)!=SDK_SHA256:
            progress('Downloading Samsung tools…');download_sdk(target,progress)
        root=home/'tizen-studio'
        progress('Installing Samsung tools automatically…')
        command([target,'--accept-license','--no-java-check',root],1200)
        sdk=SDK(root)
        # Some vendor launchers return before their child installer finishes.
        end=time.monotonic()+120
        while not sdk.can_install_tools and time.monotonic()<end:time.sleep(1)
        if not sdk.can_install_tools:raise SetupError('Samsung tools did not finish installing. Retry preparation, or open Advanced setup.')
    missing=sdk.missing_tools()
    if missing:
        if not sdk.can_install_tools:raise SetupError('Samsung tool files are incomplete. Retry preparation, or choose an existing installation under Advanced setup.')
        progress('Preparing the required Samsung components…')
        command([sdk.root/'jdk/bin/java.exe','-jar',sdk.root/'package-manager/PackageManagerV2-cli.jar',
                 'install','--accept-license','--no-java-check',','.join(missing)],1200,cwd=sdk.root/'package-manager')
    if sdk.missing_tools():raise SetupError('Samsung component installation is incomplete. Retry preparation; technical details are under Advanced setup.')
    progress('Samsung tools ready.')
    return sdk

def certificate_issuer_der(der):
    # Only parse the X.509 issuer field; a device ID in SAN is not privilege evidence.
    def tlv(offset,limit):
        if offset+2>limit: raise SetupError('Invalid signing certificate.')
        tag=der[offset]; length=der[offset+1]; start=offset+2
        if length&128:
            count=length&127
            if not 1<=count<=4 or start+count>limit: raise SetupError('Invalid certificate length.')
            length=int.from_bytes(der[start:start+count],'big');start+=count
        end=start+length
        if end>limit: raise SetupError('Truncated signing certificate.')
        return tag,start,end
    tag,start,end=tlv(0,len(der))
    if tag!=0x30 or end!=len(der): raise SetupError('Invalid certificate container.')
    tag,offset,limit=tlv(start,end)
    if tag!=0x30: raise SetupError('Invalid certificate body.')
    if der[offset]==0xa0: _,_,offset=tlv(offset,limit)
    for expected in (0x02,0x30):
        tag,_,offset=tlv(offset,limit)
        if tag!=expected: raise SetupError('Invalid certificate fields.')
    tag,start,end=tlv(offset,limit)
    if tag!=0x30: raise SetupError('Invalid certificate issuer.')
    return der[start:end]

def verify_startup_package(package):
    with zipfile.ZipFile(package) as archive:
        root=ET.fromstring(archive.read('config.xml'))
        service=root.find('{http://tizen.org/ns/widgets}service')
        if service is None or service.get('id')!=STARTUP_ID or service.get('on-boot')!='true' or service.get('auto-restart')!='true':
            raise SetupError('The launcher startup service is missing or incorrectly configured.')
        content=service.find('{http://tizen.org/ns/widgets}content')
        if content is None or content.get('src')!='startup-service.js' or 'startup-service.js' not in archive.namelist():
            raise SetupError('The startup service script is missing.')
        signature=ET.fromstring(archive.read('signature1.xml'))
        cert=signature.find('.//{http://www.w3.org/2000/09/xmldsig#}X509Certificate')
        try: issuer=certificate_issuer_der(base64.b64decode(cert.text)) if cert is not None else b''
        except (ValueError,TypeError): raise SetupError('Cannot read the Samsung distributor certificate.')
        # Early privilege check, not a substitute for the TV's signature/device validation.
        if not any(marker in issuer for marker in (b'VD DEVELOPER Partner CA',b'VD DEVELOPER Platform CA')):
            raise SetupError('Startup requires a Samsung Partner distributor certificate. Open Certificate Manager, edit this profile, choose Partner and add your TV, then retry. Nothing was installed.')

def package_stage(sdk,stage,profile):
    if profile not in sdk.profiles(): raise SetupError('The selected signing profile is no longer valid.')
    output=command([sdk.cli,'package','-t','wgt','-s',profile,'--',stage],120)
    candidates=list(Path(stage).glob('*.wgt'))
    if len(candidates)!=1 or 'Package File Location:' not in output: raise SetupError('Samsung did not produce one signed launcher package.\n'+output[-1000:])
    package=candidates[0]
    with zipfile.ZipFile(package) as archive:
        names=archive.namelist()
        if not {'author-signature.xml','signature1.xml'}.issubset(names): raise SetupError('The package is missing Samsung signing certificates.')
        if any(n.lower().endswith(('.p12','.wgt','.mp4','.dpapi','.mp3','.wav')) for n in names): raise SetupError('Private payload detected in package.')
    verify_startup_package(package)
    # Samsung's install CLI fails silently when the outer WGT filename has spaces.
    safe_name=Path(stage)/'Launcher.wgt'
    if package!=safe_name: package.replace(safe_name)
    package=safe_name
    return package

def install_package(sdk,ip,package):
    with zipfile.ZipFile(package) as archive:
        root=ET.fromstring(archive.read('config.xml'))
        app=root.find('{http://tizen.org/ns/widgets}application')
        if app is None or app.get('id')!=APP_ID: raise SetupError('This is not an MalHani Launcher launcher package. Installation stopped.')
    result=command([sdk.cli,'install','-s',ip+':26101','-n',Path(package).name,'--',Path(package).parent],180)
    if 'successfully installed' not in result.lower(): raise SetupError('Installation was not confirmed.\n'+result[-1500:])
    result=command([sdk.cli,'run','-s',ip+':26101','-p',APP_ID],40)
    if 'successfully launched' not in result.lower(): raise SetupError('The app installed, but launch was not confirmed.')
    end=time.monotonic()+12
    while time.monotonic()<end:
        try:
            state=request_json(ip,'/api/v2/applications/'+APP_ID)
            if state.get('running') is True and state.get('visible') is True: return
        except Exception: pass
        time.sleep(1)
    raise SetupError('The TV did not confirm the launcher is visible. It may need to be opened from Samsung Apps.')

def install(sdk,ip,profile,config,home,backup,progress=lambda value:None):
    verify_backup(backup)
    report=json.loads((Path(backup)/'backup-report.json').read_text(encoding='utf-8'))
    if report.get('tvIP')!=ip or report.get('signingProfile')!=profile: raise SetupError('The backup belongs to a different TV/signing profile. Create a fresh backup.')
    apps,_=sdk.inventory(ip)
    caps=sdk.capability(ip)
    try: platform=float(str(caps.get('platform_version','0')).strip())
    except ValueError: platform=0
    if platform<3: raise SetupError('This installer requires Tizen 3.0 or newer. This TV could not be verified.')
    verify_backup(backup)
    progress('Preparing the launcher…')
    with tempfile.TemporaryDirectory(prefix='openhome-',dir=Path(home)/'build') as temp:
        stage=prepare_stage(config,Path(temp)/'launcher'); progress('Signing with your Samsung TV profile…'); package=package_stage(sdk,stage,profile)
        verify_backup(backup); progress('Installing and checking the launcher…'); install_package(sdk,ip,package)
        current=Path(home)/'devices'/ip/'current'; current.mkdir(parents=True,exist_ok=True)
        shutil.copy2(package,current/'Launcher.wgt')
        (current/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
        (current/'install.json').write_text(json.dumps({'appId':APP_ID,'version':VERSION,'sha256':sha(package),'backup':str(backup),'signedProfile':profile,'installedAt':datetime.now().astimezone().isoformat()},indent=2),encoding='utf-8')
    return current

def rollback(sdk,ip,backup):
    verify_backup(backup)
    report_file=Path(backup)/'backup-report.json'
    if report_file.is_file() and json.loads(report_file.read_text(encoding='utf-8')).get('tvIP')!=ip:
        raise SetupError('This backup belongs to a different TV.')
    package=Path(backup)/'previous-installer-version/Launcher.wgt'
    if not package.is_file(): raise SetupError('This backup has no previous installer-managed package. Original Samsung apps were never removed.')
    install_package(sdk,ip,package)

def finish_setup(sdk,ip,profile,home,progress=lambda value:None):
    current=Path(home)/'devices'/valid_ip(ip)/'current'
    record=json.loads((current/'install.json').read_text(encoding='utf-8'))
    if record.get('appId')!=APP_ID or record.get('signedProfile')!=profile:
        raise SetupError('The installed launcher does not match this setup. Retry installation first.')
    config=json.loads((current/'config.json').read_text(encoding='utf-8'))
    config['welcomeReady']=True
    progress('Saving the final setup backup…')
    info=tv_info(ip);apps,inventory=sdk.inventory(ip);caps=sdk.capability(ip)
    backup=make_backup(sdk,ip,profile,info,apps,inventory,caps,home)
    progress('Finishing setup on your TV…')
    install(sdk,ip,profile,config,home,backup,progress)
    return backup

def self_test():
    config=build_config(CATALOG[:2],[],prayer=False)
    with tempfile.TemporaryDirectory() as temp:
        stage=prepare_stage(config,Path(temp)/'stage')
        assert 'TizenTube' not in (stage/'main.js').read_text(encoding='utf-8')
        assert not any(p.suffix in {'.p12','.wgt','.mp4','.mp3','.wav'} for p in stage.rglob('*') if p.is_file())
        assert 'welcome.js' in (stage/'index.html').read_text(encoding='utf-8')
        probe=Path(temp)/'backup';probe.mkdir();(probe/'sample.txt').write_text('test');manifest(probe);verify_backup(probe)
    return 'PASS: resources, public configuration, welcome screen and backup verification. No TV connection or modification.'
