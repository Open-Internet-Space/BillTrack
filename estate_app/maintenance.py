"""Read-only superuser guides; never execute recovery scripts or serve backup contents."""
import json
import re
from pathlib import Path
from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.template.response import TemplateResponse
from django.views.decorators.http import require_GET

PARTS=(
 ('email-accounts','Signup and email recovery','Run prepare_account_rollback --apply before restoring older source. Signup-created users are disabled and their tokens revoked; current financial records and account rows are retained.'),
 ('admin-guides','Admin help pages','Restores the earlier application version, including removal of these help pages.'),
 ('email-reminders','Email reminders','The recovery helper disables the separate mail task and restores the earlier app version; existing records and mail history remain.'),
 ('cursor-size','Cursor size','Historical source/static manifest backup. Restore matching assets together; this is not a standalone feature toggle.'),
 ('cursor-style','Cursor appearance','Restores the application version before the cursor update; later features may also be removed.'),
 ('modular-deployment','Modular code structure','Restores the recorded pre-refactor source and build. Later features are not independent of that version.'),
 ('boot-autostart','Windows boot scheduling','Task-only recovery returns to the earlier interactive/on-demand task; automatic startup before login is lost.'),
 ('user-visible-errors','User-visible errors','Historical application recovery. Check the installed version and current repeating task before following older instructions.'),
 ('totp-recovery','Authenticator recovery','Historical application recovery; preserve the current ledger and review newer security changes.'),
 ('reset-page-ui','Password-reset appearance','Historical template recovery; consult its local instructions and preserve subsequent changes.'),
 ('pre-production','Original production setup','May restore application, settings, firewall and task state. Requires particular care because newer operational settings can change.'),
 ('frontend','Frontend build backups','Historical build artifacts only; confirm the source/build/static versions match before restoration.'),
)
HELPERS=('rollback-email-reminders.ps1','rollback-task.ps1','rollback-modular.ps1','rollback.ps1')
NOTES=('OPERATIONS.md','ROLLBACK.txt','ROLLBACK.md')

def local_file(folder,name):
    path=folder/name
    return path if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(folder.resolve()) else None

def rollback_catalog(root):
    root=Path(root).resolve();backups=root/'backups';sections=[]
    usable=backups.is_dir() and not backups.is_symlink() and backups.resolve().is_relative_to(root)
    for key,title,effect in PARTS:
        section={'folder':key,'title':title,'effect':effect,'snapshots':[]}
        category=backups/key
        if usable and category.is_dir() and not category.is_symlink() and category.resolve().is_relative_to(backups.resolve()):
            try:folders=sorted(category.iterdir(),key=lambda path:path.name,reverse=True)
            except OSError:folders=[]
            for folder in folders:
                if not folder.is_dir() or folder.is_symlink() or not folder.resolve().is_relative_to(backups.resolve()):
                    continue
                version='';previous=''
                metadata=local_file(folder,'manifest.json')
                try:
                    if metadata and metadata.stat().st_size<=2*1024*1024:
                        data=json.loads(metadata.read_text(encoding='utf-8-sig'))
                        for name in ['installed_commit','before']:
                            value=data.get(name,'')
                            if isinstance(value,str) and re.fullmatch('[0-9a-f]{40}',value):
                                if name=='installed_commit':version=value
                                else:previous=value
                except (OSError,ValueError,AttributeError):pass
                helper=next((local_file(folder,name) for name in HELPERS if local_file(folder,name)),None)
                notes=[str(path) for name in NOTES if (path:=local_file(folder,name))]
                data_archive=False
                for source in [folder,folder/'online',folder/'stopped']:
                    if source.is_dir() and not source.is_symlink() and source.resolve().is_relative_to(folder.resolve()):
                        data_archive=data_archive or any(local_file(source,path.name) for path in source.glob('billtrack-backup-*.zip'))
                artifacts=[]
                for label,names in [('Source archive',['source-before.zip','application.zip']),
                    ('Frontend/static archive',['runtime-before.zip']),('Task definition',['before-task.xml','production-task.xml'])]:
                    if any(local_file(folder,name) for name in names):artifacts.append(label)
                if data_archive:artifacts.append('Database/data backup')
                section['snapshots'].append({'name':folder.name,'path':str(folder),'expected_version':version,
                    'previous_version':previous,'helper':str(helper) if helper else '',
                    'notes':notes,'artifacts':artifacts})
        sections.append(section)
    return sections

@require_GET
def rollback_view(request):
    if not request.user.is_superuser:raise PermissionDenied
    root=Path(settings.BASE_DIR)
    return TemplateResponse(request,'admin/rollbacks.html',{**admin.site.each_context(request),
        'title':'Rollbacks and backup details','sections':rollback_catalog(root),'root':str(root),
        'version_command':"git -C '"+str(root).replace("'","''")+"' rev-parse HEAD"})

class MapSearch(forms.Form):
    q=forms.CharField(required=False,max_length=200,label='Which section do you want to change?',
        widget=forms.TextInput(attrs={'placeholder':'Try invoice, logo, allottees, password or email reminders','size':50}))

@require_GET
def modification_view(request):
    if not request.user.is_superuser:raise PermissionDenied
    form=MapSearch(request.GET);query='';components=[];recipes=[];error=''
    try:
        root=Path(settings.BASE_DIR).resolve();path=root/'docs/component-map.json'
        if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError
        if path.stat().st_size>2*1024*1024:raise ValueError
        data=json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data,dict) or not isinstance(data.get('components'),list):raise ValueError
        if form.is_valid():
            query=form.cleaned_data['q'].strip().casefold()
            components=[entry for entry in data['components'] if not query or query in json.dumps(entry,ensure_ascii=False).casefold()]
            recipes=data.get('recipes',[]) if not query else []
    except (OSError,ValueError,TypeError,KeyError):
        error='Modification guide unavailable. Restore or regenerate docs/component-map.json on the server.'
    return TemplateResponse(request,'admin/modification_guide.html',{**admin.site.each_context(request),
        'title':'Which code to change','search_form':form,'query':query,'components':components,
        'recipes':recipes,'guide_error':error,'root':str(settings.BASE_DIR)})
