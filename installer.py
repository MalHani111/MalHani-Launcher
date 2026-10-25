"""MalHani Launcher guided Windows installer. Run --self-test for an offline smoke test."""
from __future__ import annotations
import json, os, queue, socket, subprocess, sys, threading, time, traceback, webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import core

GUIDE='https://developer.samsung.com/smarttv/develop/getting-started/setting-up-sdk/installing-tv-sdk.html'
CERTIFICATE_GUIDE = (
    '1. In Certificate Manager, click + → Samsung → TV.\n'
    '2. Profile name: enter MalHaniTV (or your own name), then Next.\n'
    '3. Choose Create a new author certificate. Author name: your name. Choose a password and keep it.\n'
    '4. Sign in to Samsung when asked. Choose a backup folder and continue.\n'
    '5. Choose Create a new distributor certificate. Set Privilege to Partner.\n'
    '6. Add your TV’s DUID: click + beside the connected TV, then continue.\n'
    '7. Click Finish. Return here; setup continues automatically.\n\n'
    'Updating an existing installation? Reuse its author certificate.'
)

class Installer(tk.Tk):
    def __init__(self, home=None, testing=False):
        super().__init__(); self.title('MalHani Launcher Setup · Samsung TV'); self.geometry('1060x800'); self.minsize(940,700)
        self.testing=testing; self.home=Path(home) if home else core.data_home()
        self.home.mkdir(parents=True,exist_ok=True); (self.home/'build').mkdir(exist_ok=True)
        self.events=queue.Queue(); self.working=False; self.stage=0; self.info=None; self.apps=[]; self.caps={}; self.inventory=''; self.backup=None
        self.sdk=None; self.usb=None; self.profile= tk.StringVar(); self.ip=tk.StringVar(); self.sdk_path=tk.StringVar()
        self.status=tk.StringVar(value='Connect the PC and TV to the same home network.'); self.setup_status=tk.StringVar()
        self.setup_heading=tk.StringVar(value='Checking your TV…');self.setup_detail=tk.StringVar(value='Preparation runs automatically.')
        self.advanced_setup=False;self.last_tool_fraction=-1
        self.clock24=tk.BooleanVar(value=True); self.prayer=tk.BooleanVar(value=False); self.zone=tk.StringVar(value='SGR01'); self.place=tk.StringVar(value='Semenyih · Hulu Langat')
        self.selected={s['title']:tk.BooleanVar(value=s['title'] in ('Netflix','YouTube')) for s in core.CATALOG}
        self.profiles=[]; self.last_ready=False; self.last_probe=0; self.auto_tools_opened=False; self.auto_cert_opened=False; self.auto_packages_opened=False
        self.saved_setup=None
        try:
            saved=json.loads((self.home/'setup.json').read_text(encoding='utf-8'));core.valid_ip(saved['ip'])
            self.saved_setup=saved;self.ip.set(saved['ip']);self.sdk_path.set(saved.get('sdk',''));self.profile.set(saved.get('profile',''))
            self.clock24.set(saved.get('clock24h',True));self.prayer.set(saved.get('prayer',False));self.zone.set(saved.get('zone','SGR01'));self.place.set(saved.get('place','Semenyih · Hulu Langat'))
            for title,var in self.selected.items():var.set(title in saved.get('selected',[]))
        except (OSError,ValueError,KeyError,core.SetupError):pass
        self.style=ttk.Style(); self.style.theme_use('clam'); self.configure(background='#edf3f2')
        self.style.configure('TFrame',background='#edf3f2'); self.style.configure('TLabel',background='#edf3f2',foreground='#163633',font=('Segoe UI',11))
        self.style.configure('Title.TLabel',font=('Segoe UI',23,'bold')); self.style.configure('Heading.TLabel',font=('Segoe UI',17,'bold'))
        self.style.configure('MalHani.Horizontal.TProgressbar',background='#197565',troughcolor='#d3e0dd',lightcolor='#197565',darkcolor='#197565',thickness=16)
        self.style.configure('TButton',font=('Segoe UI',11),padding=(12,8)); self.style.configure('TCheckbutton',background='#edf3f2',font=('Segoe UI',11))
        self.style.configure('TLabelframe',background='#edf3f2'); self.style.configure('TLabelframe.Label',background='#edf3f2',font=('Segoe UI',11,'bold'))
        top=ttk.Frame(self,padding=(26,22,26,10)); top.pack(fill='x')
        ttk.Label(top,text='MalHani Launcher Setup',style='Title.TLabel').pack(anchor='w')
        ttk.Label(top,text='Your Samsung TV, with a simpler home screen.').pack(anchor='w',pady=(3,0))
        self.steps=ttk.Label(self,text='');self.steps.pack(anchor='w',padx=28,pady=6)
        content=ttk.Frame(self);content.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(content,background='#edf3f2',highlightthickness=0)
        scrollbar=ttk.Scrollbar(content,orient='vertical',command=self.canvas.yview)
        scrollbar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.body=ttk.Frame(self.canvas,padding=(28,16));self.content_window=self.canvas.create_window((0,0),window=self.body,anchor='nw')
        self.body.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.content_window,width=e.width))
        self.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-int(e.delta/120),'units'))
        foot=ttk.Frame(self,padding=(26,10,26,22));foot.pack(fill='x')
        self.progress_text=tk.StringVar(value='Ready')
        ttk.Label(foot,textvariable=self.progress_text,font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(0,5))
        self.progress=ttk.Progressbar(foot,mode='determinate',maximum=100,style='MalHani.Horizontal.TProgressbar')
        self.progress.pack(fill='x',pady=(0,8))
        ttk.Label(foot,textvariable=self.status,wraplength=960).pack(anchor='w',fill='x',pady=(0,12))
        self.back_button=ttk.Button(foot,text='Back',command=self.back);self.back_button.pack(side='left')
        self.next_button=ttk.Button(foot,text='Continue',command=self.next);self.next_button.pack(side='right')
        ttk.Button(foot,text='Open local files',command=lambda:os.startfile(self.home)).pack(side='left',padx=10)
        self.after(100,self.drain)
        if not testing:self.after(2500,self.poll)
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.show()
        if not testing:self.after(250,self.auto_find)
    def close(self):
        if self.working:
            self.status.set('Please let the current operation finish before closing.'); return
        self.destroy()
    def say(self,text): self.events.put(('status',text))
    def tool_progress(self,done,total):
        fraction=done/max(total,1)
        if fraction-self.last_tool_fraction>=.005 or done==total:
            self.last_tool_fraction=fraction;self.events.put(('progress',(fraction,'Preparing Samsung tools')))
    def task(self,function,success=None):
        if self.working: return
        self.working=True;self.next_button.configure(state='disabled');self.back_button.configure(state='disabled')
        self.progress.configure(mode='indeterminate');self.progress.start(12);self.progress_text.set('Working…')
        def worker():
            try: self.events.put(('result',(success,function())))
            except Exception as e:
                self.events.put(('error',str(e)))
        threading.Thread(target=worker,daemon=True).start()
    def drain(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='status': self.status.set(value);self.progress_text.set(value)
                elif kind=='progress':
                    fraction,label=value;self.progress.stop();self.progress.configure(mode='determinate',value=100*fraction)
                    self.progress_text.set(label+' · '+str(round(100*fraction))+'%')
                elif kind=='error':
                    self.progress.stop();self.progress_text.set('Needs attention')
                    self.working=False; self.status.set('Action stopped: '+value[:700]); self.next_button.configure(state='normal'); self.back_button.configure(state='normal')
                elif kind=='result':
                    self.progress.stop();self.progress.configure(mode='determinate',value=100);self.progress_text.set('Step complete')
                    self.working=False;self.next_button.configure(state='normal');self.back_button.configure(state='normal')
                    callback,result=value
                    if callback: callback(result)
        except queue.Empty: pass
        self.after(100,self.drain)
    def label(self,text,**kwargs):
        widget=ttk.Label(self.body,text=text,wraplength=960,**kwargs);widget.pack(anchor='w',pady=6,fill='x');return widget
    def button(self,text,fn):
        b=ttk.Button(self.body,text=text,command=fn);b.pack(anchor='w',pady=6);return b
    def show(self):
        for child in self.body.winfo_children(): child.destroy()
        self.canvas.yview_moveto(0)
        names=['1 · Find TV','2 · Guided setup','3 · Backup','4 · Apps & clock','5 · Install']
        self.steps.configure(text='     →     '.join(('['+n+']') if i==self.stage else n for i,n in enumerate(names)))
        self.back_button.configure(state='disabled' if self.stage==0 else 'normal');self.next_button.configure(text='Install Launcher' if self.stage==4 else 'Continue',state='normal')
        getattr(self,'page'+str(self.stage))()
    def back(self):
        if not self.working and self.stage>0: self.stage-=1;self.show()
    def next(self):
        if self.working:return
        if self.stage==0:
            self.connect();return
        if self.stage==1:
            self.inspect_setup(advance=True);return
        if self.stage==2:
            if not self.backup: self.status.set('Create the verified backup before continuing.');return
        if self.stage==3:
            try: core.build_config(self.specs(),self.apps,self.zone.get(),self.place.get(),self.clock24.get(),self.prayer.get())
            except core.SetupError as e:self.status.set(str(e));return
        if self.stage==4:self.do_install();return
        self.stage+=1;self.show()
    def page0(self):
        self.label('Find your TV',style='Heading.TLabel')
        if self.saved_setup:self.button('Update saved TV · '+self.saved_setup['ip'],self.quick_update)
        self.label('Keep the TV on. Automatic discovery uses the home network; you can also enter the TV address shown in its Network Status screen.')
        row=ttk.Frame(self.body);row.pack(fill='x',pady=15)
        ttk.Entry(row,textvariable=self.ip,width=24,font=('Segoe UI',15)).pack(side='left')
        ttk.Button(row,text='Find TVs',command=self.find).pack(side='left',padx=12)
        self.tv_list=ttk.Treeview(self.body,columns=('ip','model','name'),show='headings',height=5)
        for column in ('ip','model','name'):self.tv_list.heading(column,text=column.title());self.tv_list.column(column,width=250)
        self.tv_list.pack(fill='x',pady=10);self.tv_list.bind('<<TreeviewSelect>>',self.pick_tv)
    def quick_update(self):
        try:
            self.sdk=core.SDK(self.sdk_path.get())
            if not self.sdk.ready or self.profile.get() not in self.sdk.profiles():
                self.stage=1;self.show();self.inspect_setup();return
        except Exception as e:self.status.set(str(e));return
        self.do_install()
    def find(self):
        self.status.set('Looking for Samsung TVs…');self.task(core.discover,self.found)
    def auto_find(self):
        if self.stage!=0:return
        if self.working:self.after(250,self.auto_find);return
        self.find()
    def found(self,devices):
        if self.stage!=0:return
        self.tv_list.delete(*self.tv_list.get_children())
        for d in devices:self.tv_list.insert('', 'end',values=(d['ip'],d['model'],d['name']))
        if len(devices)==1:
            self.ip.set(devices[0]['ip'])
            self.connect();return
        if devices:self.status.set('More than one TV found. Select yours, then Continue.')
        else:self.status.set('No TV found yet. Keep the TV on and click Find TVs to retry, or enter its address.')
    def pick_tv(self,event=None):
        ids=self.tv_list.selection()
        if ids:self.ip.set(self.tv_list.item(ids[0],'values')[0])
    def connect(self):
        try: ip=core.valid_ip(self.ip.get())
        except core.SetupError as e:self.status.set(str(e));return
        self.status.set('Checking the selected TV…')
        self.task(lambda:(ip,core.tv_info(ip)),self.connected)
    def connected(self,result):
        ip,info=result;self.ip.set(ip);self.info=info;self.backup=None
        for root in core.sdk_roots(self.sdk_path.get()):
            sdk=core.SDK(root)
            if sdk.ready:self.sdk=sdk;self.sdk_path.set(str(root));break
        self.stage=1;self.show();self.inspect_setup()
    def page1(self):
        self.label('Preparing your setup',style='Heading.TLabel')
        self.label('Samsung tools are included and prepared automatically.')
        self.label('',textvariable=self.setup_heading,style='Heading.TLabel')
        self.label('',textvariable=self.setup_detail)
        self.profile_row=ttk.Frame(self.body)
        ttk.Label(self.profile_row,text='Choose your Samsung certificate:').pack(side='left')
        self.profile_box=ttk.Combobox(self.profile_row,textvariable=self.profile,state='readonly',width=35,values=self.profiles)
        self.profile_box.pack(side='left',padx=12)
        if len(self.profiles)>1 and not self.profile.get():self.profile_row.pack(fill='x',pady=7)
        self.button('Hide advanced setup' if self.advanced_setup else 'Advanced setup',self.toggle_advanced)
        if self.advanced_setup:
            row=ttk.Frame(self.body);row.pack(fill='x',pady=8)
            ttk.Label(row,text='Samsung tools folder:').pack(side='left');ttk.Entry(row,textvariable=self.sdk_path,width=55).pack(side='left',padx=10)
            ttk.Button(row,text='Browse',command=self.browse_sdk).pack(side='left')
            row=ttk.Frame(self.body);row.pack(fill='x',pady=5)
            for text,fn in [('Retry preparation',self.get_tools),('Open Package Manager',self.open_packages),('Open Certificate Manager',self.open_certificates)]:ttk.Button(row,text=text,command=fn).pack(side='left',padx=(0,8))
            ttk.Label(self.body,textvariable=self.setup_status,wraplength=950).pack(fill='x',pady=12)
    def toggle_advanced(self):
        if self.working:return
        self.advanced_setup=not self.advanced_setup;self.show()
    def browse_sdk(self):
        folder=filedialog.askdirectory(title='Select the Samsung SDK folder containing tools/sdb.exe')
        if folder:self.sdk_path.set(folder);self.inspect_setup()
    def get_tools(self):
        if self.working:return
        self.last_tool_fraction=-1
        self.status.set('Preparing the included Samsung tools…')
        def ready(sdk):
            self.sdk=sdk;self.sdk_path.set(str(sdk.root))
            self.status.set('Samsung tools are ready. Checking the TV connection…')
            self.inspect_setup()
        self.task(lambda:core.ensure_tools(self.home,self.sdk_path.get(),self.say,self.tool_progress),ready)
    def open_packages(self):
        try:
            sdk=core.SDK(self.sdk_path.get());sdk.open_packages()
            self.status.set('Samsung Package Manager opened. Install Certificate-Manager, Samsung Certificate Extension and TV Extensions. Checks continue automatically.')
        except Exception as e:self.status.set(str(e))
    def open_certificates(self):
        try:
            sdk=core.SDK(self.sdk_path.get());sdk.open_certificates()
            self.status.set('Certificate Manager opened. Complete your own Samsung sign-in and choose Partner and add this TV to the distributor certificate. Profiles appear automatically when finished.')
        except Exception as e:self.status.set(str(e))
    def inspect_setup(self,advance=False):
        if self.working:return
        ip=self.ip.get();root=self.sdk_path.get()
        def inspect():
            info=core.tv_info(ip); d=info['device']; local=core.pc_ip_for(ip)
            sdk=core.find_sdk(root)
            profiles=sdk.profiles() if sdk and sdk.ready else []
            dev=str(d.get('developerMode','')).lower() in ('1','true')
            host=str(d.get('developerIP','')).strip();ready=core.port_open(ip)
            if ready and sdk and sdk.ready:
                try:sdk.connect(ip)
                except core.SetupError:ready=False
            return sdk,profiles,dev,host,local,ready
        def result(values):
            sdk,profiles,dev,host,local,ready=values;self.sdk=sdk;self.profiles=profiles
            if sdk:self.sdk_path.set(str(sdk.root))
            if self.profile.get() not in profiles:self.profile.set(profiles[0] if len(profiles)==1 else '')
            if self.stage==1:self.profile_box.configure(values=profiles)
            host_ok=not host or host==local
            tools_ready=bool(sdk and sdk.ready and not sdk.missing_tools())
            self.last_ready=bool(tools_ready and self.profile.get() in profiles and ready and host_ok)
            self.setup_status.set(' | '.join(['SDK: '+('ready' if sdk and sdk.ready else 'needed'), 'Developer Mode: '+('ON' if dev else 'not reported ON'), 'PC address: '+('matches' if host==local else ('not exposed; SDK will verify' if not host else 'MISMATCH')), 'Developer port: '+('ready' if ready else 'waiting'), 'Signing profiles: '+str(len(profiles))]))
            if not tools_ready:
                self.setup_heading.set('Preparing Samsung tools…')
                self.setup_detail.set('This runs automatically. No folders or components to choose.')
            elif not ready or not host_ok:
                self.setup_heading.set('On your TV: enable Developer Mode')
                self.setup_detail.set('Apps → App Settings → enter 1 2 3 4 5. Enable Developer Mode, enter PC address '+local+', confirm and restart the TV. Setup continues automatically.')
            elif not profiles:
                self.setup_heading.set('Create your Samsung certificate profile')
                self.setup_detail.set(CERTIFICATE_GUIDE)
            elif not self.profile.get():
                self.setup_heading.set('Choose your Samsung certificate')
                self.setup_detail.set('More than one certificate is available. Select the one for this TV below.')
            else:
                self.setup_heading.set('Setup checks passed')
                self.setup_detail.set('Continuing automatically…')
            if self.stage==1:
                self.profile_box.configure(values=profiles)
                if len(profiles)>1 and not self.profile.get():self.profile_row.pack(fill='x',pady=7,before=self.profile_row.master.winfo_children()[-1])
                else:self.profile_row.pack_forget()
            if self.stage==1 and not tools_ready and not self.auto_tools_opened:
                self.auto_tools_opened=True; self.after(200,self.get_tools)
            elif self.stage==1 and tools_ready and ready and not profiles and not self.auto_cert_opened:
                self.auto_cert_opened=True; self.after(200,self.open_certificates)
            if advance or self.last_ready:
                if not self.last_ready:self.status.set('Waiting for the unfinished checks above. Complete those steps; detection refreshes automatically.');return
                self.status.set('Reading app inventory and Tizen version…');self.task(lambda:(sdk.inventory(ip),sdk.capability(ip)),self.inventory_ready)
        self.task(inspect,result)
    def inventory_ready(self,result):
        (self.apps,self.inventory),self.caps=result
        try: version=float(self.caps.get('platform_version','0'))
        except ValueError:version=0
        if version<3:self.status.set('Tizen 3.0 or newer could not be verified. Installation is blocked.');return
        self.stage=2;self.show();self.status.set('Developer connection verified. Create your baseline backup next.')
    def poll(self):
        if self.stage==1 and not self.working:self.inspect_setup()
        elif self.stage==3 and not self.working and self.sdk:
            def refreshed(result):
                apps,inventory=result
                if apps!=self.apps:
                    self.apps,self.inventory=apps,inventory;self.backup=None
                    if self.stage==3:self.show();self.status.set('New app detected. The final backup will include the updated app inventory.')
            self.task(lambda:self.sdk.inventory(self.ip.get()),refreshed)
        self.after(5000,self.poll)
    def page2(self):
        self.label('Backup',style='Heading.TLabel')
        self.label('Your setup files are backed up and verified automatically.')
        self.label('This is not a full TV backup. Accounts, protected app data and most TV settings are not included. Restore is available for previous versions installed by this installer.')
        self.label('USB backup (optional)',style='Heading.TLabel')
        self.label('You can continue without a USB backup. If your TV supports a Samsung settings export, save it to USB and import its folder here.')
        self.button('Open TV settings for USB backup',self.tv_settings)
        self.button('Import an existing USB settings export (optional)',self.import_usb)
        self.label('USB export: '+(str(self.usb) if self.usb else 'Not imported (optional)'))
        if self.usb:self.button('Continue without USB backup',self.skip_usb)
        self.button('Create and verify backup',self.do_backup)
        if self.backup:self.label('Verified backup: '+str(self.backup))
        elif not self.testing:self.after(200,lambda:self.do_backup() if self.stage==2 and not self.working else None)
    def tv_settings(self):
        self.task(lambda:core.command([self.sdk.cli,'run','-s',self.ip.get()+':26101','-p','org.tizen.menu'],40),lambda _:self.status.set('Samsung Settings opened. Import a USB export if the TV offers it.'))
    def import_usb(self):
        path=filedialog.askdirectory(title='Select only the Samsung USB export folder')
        if path:self.usb=Path(path);self.backup=None;self.show()
    def skip_usb(self):
        self.usb=None;self.backup=None;self.show()
    def do_backup(self):
        self.status.set('Capturing and verifying the available baseline…')
        sdk,ip,profile,usb=self.sdk,self.ip.get(),self.profile.get(),self.usb
        def capture():
            info=core.tv_info(ip);apps,inventory=sdk.inventory(ip);caps=sdk.capability(ip)
            return core.make_backup(sdk,ip,profile,info,apps,inventory,caps,self.home,usb),apps,inventory,caps
        def done(result):
            self.backup,self.apps,self.inventory,self.caps=result;self.show();self.status.set('Backup verified. Protected/unavailable data is documented in backup-report.json. You can continue.')
        self.task(capture,done)
    def specs(self):return [spec for spec in core.CATALOG if self.selected[spec['title']].get()]
    def page3(self):
        self.label('Choose up to six app shortcuts',style='Heading.TLabel')
        self.label('Choose your shortcuts. For missing apps, open Samsung Apps, install them on the TV, then click Recheck installed apps.')
        for spec in core.CATALOG:
            row=ttk.Frame(self.body);row.pack(fill='x',pady=4)
            ttk.Checkbutton(row,text=spec['title'],variable=self.selected[spec['title']],width=18).pack(side='left')
            present=core.match_app(spec,self.apps)
            ttk.Label(row,text='Installed · shortcut only' if present else 'Not detected · Samsung Store required',width=45).pack(side='left')
            if not present:ttk.Button(row,text='Open Samsung Apps',command=self.store).pack(side='left')
        self.button('Recheck installed apps',self.refresh_apps)
        ttk.Checkbutton(self.body,text='24-hour clock (Malaysia time, UTC+8)',variable=self.clock24).pack(anchor='w',pady=6)
        ttk.Checkbutton(self.body,text='Show waktu solat (JAKIM, Malaysia)',variable=self.prayer).pack(anchor='w',pady=6)
        row=ttk.Frame(self.body);row.pack(fill='x',pady=6)
        ttk.Label(row,text='JAKIM zone:').pack(side='left');ttk.Entry(row,textvariable=self.zone,width=10).pack(side='left',padx=8)
        ttk.Label(row,text='Location label:').pack(side='left');ttk.Entry(row,textvariable=self.place,width=35).pack(side='left',padx=8)
        self.label('Examples: SGR01 = Semenyih/Hulu Langat, WLY01 = Kuala Lumpur/Putrajaya. Prayer times require Internet and a valid JAKIM zone.')
    def store(self):
        def open_store():
            target=next((a['id'] for a in self.apps if a['id'] in ('org.volt.apps','com.samsung.tv.store')),None)
            if not target:raise core.SetupError('Samsung Apps was not found. Open Apps using the TV remote, then search for the selected app.')
            return core.command([self.sdk.cli,'run','-s',self.ip.get()+':26101','-p',target],40)
        self.task(open_store,lambda _:self.status.set('Samsung Apps opened on the TV. Search and install your chosen app there, then click Recheck installed apps.'))
    def refresh_apps(self):
        def done(result):self.apps,self.inventory=result;self.backup=None;self.show();self.status.set('App inventory refreshed. A fresh backup will be captured automatically before installation.')
        self.task(lambda:self.sdk.inventory(self.ip.get()),done)
    def page4(self):
        self.label('Ready to install MalHani Launcher',style='Heading.TLabel')
        d=self.info['device'];self.label('TV: '+str(d.get('modelName',d.get('model','Samsung TV')))+' · '+self.ip.get())
        self.label('Shortcuts: '+', '.join(s['title'] for s in self.specs()))
        missing=[s['title'] for s in self.specs() if not core.match_app(s,self.apps)]
        if missing:self.label('Still missing: '+', '.join(missing)+'. Install these through Samsung Apps to use them.')
        self.label('Keep the PC and TV on until installation finishes.')
        self.label('Next: set up automatic reopening on your TV.')
        self.button('Restore a previous MalHani Launcher version',self.restore)
    def do_install(self):
        ip,profile,sdk=self.ip.get(),self.profile.get(),self.sdk
        try: config=core.build_config(self.specs(),self.apps,self.zone.get(),self.place.get(),self.clock24.get(),self.prayer.get())
        except core.SetupError as e:self.status.set(str(e));return
        self.status.set('Creating a fresh verified backup before installation…')
        def work():
            info=core.tv_info(ip); apps,inventory=sdk.inventory(ip);caps=sdk.capability(ip)
            backup=core.make_backup(sdk,ip,profile,info,apps,inventory,caps,self.home,self.usb)
            current=core.install(sdk,ip,profile,config,self.home,backup,self.say)
            return backup,current
        def complete(result):
            self.backup,current=result
            saved={'ip':ip,'sdk':str(sdk.root),'profile':profile,'clock24h':self.clock24.get(),'prayer':self.prayer.get(),'zone':self.zone.get(),'place':self.place.get(),'selected':[s['title'] for s in self.specs()]}
            (self.home/'setup.json').write_text(json.dumps(saved,indent=2),encoding='utf-8');self.saved_setup=saved
            for child in self.body.winfo_children():child.destroy()
            self.startup_page()
        self.task(work,complete)
    def startup_page(self):
        for child in self.body.winfo_children():child.destroy()
        self.canvas.yview_moveto(0)
        self.steps.configure(text='6 · Automatic reopening')
        self.label('Finish automatic reopening',style='Heading.TLabel')
        self.label('MalHani Launcher and its startup service are installed. Finish the TV startup settings, then check reopening.')
        self.label('On your TV',style='Heading.TLabel')
        self.label('All Settings → Advanced Features (or General & Privacy) → Start Screen Options. Turn Start with Smart Hub Home OFF. If Autorun Last App is available, turn it ON.')
        self.button('Open TV settings',self.startup_settings)
        self.label('Return to MalHani Launcher. Using the TV remote, switch the TV off, wait 10 seconds, then switch it on. Do not open the launcher yourself during this test.')
        self.label('Back on your PC',style='Heading.TLabel')
        self.label('Keep this installer open while the TV restarts. Once the TV is back on, choose what appeared:')
        self.button('It reopened automatically',lambda:self.startup_result(True))
        self.button('Still showing Samsung Home',lambda:self.startup_result(False))
        self.label('Verified backup: '+str(self.backup))
        self.back_button.configure(state='disabled');self.next_button.configure(state='disabled')
        self.status.set('Installation verified. Automatic reopening: awaiting your TV test.')
        self.save_startup('not-tested')
    def save_startup(self,result):
        saved=dict(self.saved_setup or {})
        saved['startupCheck']={'result':result,'method':'owner-observed-remote-off-on','checkedAt':time.strftime('%Y-%m-%dT%H:%M:%S%z')}
        (self.home/'setup.json').write_text(json.dumps(saved,indent=2),encoding='utf-8');self.saved_setup=saved
    def startup_settings(self):
        def opened(_):
            self.back_button.configure(state='disabled');self.next_button.configure(state='disabled')
            self.status.set('On TV: Start Screen Options → Start with Smart Hub Home OFF.')
        self.task(lambda:core.command([self.sdk.cli,'run','-s',self.ip.get()+':26101','-p','org.tizen.menu'],40),opened)
    def startup_result(self,passed):
        if self.working:return
        self.save_startup('owner-confirmed-pass' if passed else 'needs-attention')
        if not passed:
            self.status.set('Startup needs attention. Check Smart Hub Home startup is OFF, return to MalHani Launcher and retry. If the option is unavailable or it still fails, this TV’s automatic reopening is not verified.')
            return
        if self.testing:
            self.setup_complete();return
        self.finish_setup()
    def finish_setup(self):
        if self.working:return
        for child in self.body.winfo_children():child.destroy()
        self.label('Finishing setup on your TV',style='Heading.TLabel')
        self.label('Keep the installer open and the TV on until this finishes.')
        self.next_button.configure(text='Retry final step',command=self.finish_setup)
        def done(backup):
            self.backup=backup
            self.setup_complete()
        self.task(lambda:core.finish_setup(self.sdk,self.ip.get(),self.profile.get(),self.home,self.say),done)
    def setup_complete(self):
        for child in self.body.winfo_children():child.destroy()
        self.label('Your launcher is ready',style='Heading.TLabel')
        self.label('On your TV: press “Let’s go” to enter MalHani Launcher.')
        self.label('You can turn off the PC now.')
        self.label('Verified backup: '+str(self.backup))
        self.next_button.configure(text='Finish',command=self.close,state='normal')
        self.back_button.configure(state='disabled')
        saved=dict(self.saved_setup or {});saved['setupComplete']=True
        (self.home/'setup.json').write_text(json.dumps(saved,indent=2),encoding='utf-8');self.saved_setup=saved
        self.status.set('Setup complete. Automatic reopening confirmed by you on this TV.')
    def restore(self):
        folder=filedialog.askdirectory(initialdir=self.home/'backups',title='Select a MalHani Launcher backup containing a previous installer version')
        if folder:self.task(lambda:core.rollback(self.sdk,self.ip.get(),Path(folder)),lambda _:self.status.set('Previous MalHani Launcher package restored and launch verified. Samsung settings and third-party app data are outside this rollback.'))

if __name__=='__main__':
    if '--self-test' in sys.argv:
        result=core.self_test()
        if '--report' in sys.argv:Path(sys.argv[sys.argv.index('--report')+1]).write_text(result,encoding='utf-8')
        else:print(result)
    else:
        test_home=None
        if '--test-home' in sys.argv:test_home=Path(sys.argv[sys.argv.index('--test-home')+1])
        app=Installer(test_home,testing='--ui-smoke-test' in sys.argv)
        if '--ui-smoke-test' in sys.argv:app.after(1200,app.destroy)
        app.mainloop()
