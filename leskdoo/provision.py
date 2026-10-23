"""Provisioning jobs: Ubuntu cloud image + NoCloud seed, Windows VirtualBox host.

Requires PostgreSQL, pycdlib and an SSH public key. Operations are serialized
in background daemon threads and tracked in PostgreSQL; restart recovery is
reported as interrupted, never silently retried.
"""
import hashlib
import io
import os
from pathlib import Path
import re
import secrets
import subprocess
import threading
import urllib.request
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .inventory import vbox, vbox_executable

Base=declarative_base()
class Job(Base):
    __tablename__='provision_jobs'
    id=Column(String(32), primary_key=True)
    vm_name=Column(String(64), nullable=False)
    state=Column(String(20),nullable=False,default='queued')
    detail=Column(Text,default='')
    uuid=Column(String(36),nullable=True)
    created_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at=Column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

_engine=None
_lock=threading.Lock()
def session_factory():
    global _engine
    if _engine is None:
        url=os.environ.get('DATABASE_URL')
        if not url: raise RuntimeError('DATABASE_URL não configurada. Inicie PostgreSQL primeiro.')
        _engine=create_engine(url,pool_pre_ping=True,connect_args={'connect_timeout':5})
        Base.metadata.create_all(_engine)
        with sessionmaker(_engine)() as s:
            for j in s.query(Job).filter(Job.state.in_(['queued','running'])):
                j.state='interrupted'
                j.detail='Processo reiniciado; verifique VM e disco antes de tentar novamente'
            s.commit()
    return sessionmaker(_engine)

def update(job_id, state, detail, uuid=None):
    with session_factory()() as s:
        j=s.get(Job,job_id)
        if not j:return
        j.state=state;j.detail=detail;j.updated_at=datetime.now(timezone.utc)
        if uuid:j.uuid=uuid
        s.commit()

def jobs():
    with session_factory()() as s:
        all_jobs=s.query(Job).order_by(Job.created_at.desc()).limit(30).all()
        return [dict(id=j.id,name=j.vm_name,state=j.state,detail=j.detail,
                     uuid=j.uuid,created_at=j.created_at.isoformat() if j.created_at else '') for j in all_jobs]

def safe_name(name):
    return bool(re.fullmatch(r'[a-zA-Z][a-zA-Z0-9-]{2,39}',name))

def run_vbox(*args):
    return vbox(list(args))

def download_image(cache):
    url='https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.vmdk'
    sums='https://cloud-images.ubuntu.com/noble/current/SHA256SUMS'
    cache.mkdir(parents=True,exist_ok=True)
    checksum=urllib.request.urlopen(sums,timeout=45).read().decode()
    name=url.rsplit('/',1)[-1]
    matches=re.findall(r'^([a-f0-9]{64})\s+\*?'+re.escape(name)+r'$',checksum,re.MULTILINE)
    if not matches: raise RuntimeError('Imagem VMDK não encontrada na lista SHA256SUMS oficial')
    expected=matches[0]
    output=cache/name
    if output.exists() and sha256(output)==expected:return output
    temp=output.with_suffix('.partial')
    request=urllib.request.Request(url,headers={'User-Agent':'LeskDoo/0.2'})
    with urllib.request.urlopen(request,timeout=90) as response, open(temp,'wb') as file:
        while True:
            chunk=response.read(1024*1024)
            if not chunk:break
            file.write(chunk)
    if sha256(temp)!=expected:
        temp.unlink(missing_ok=True)
        raise RuntimeError('Falha de integridade SHA256 da imagem Ubuntu')
    temp.replace(output)
    return output

def sha256(path):
    sha=hashlib.sha256()
    with open(path,'rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):sha.update(part)
    return sha.hexdigest()

def seed_iso(path,username,ssh_key,hostname):
    import pycdlib
    import json
    # Avoid YAML string interpolation; user-data is generated from validated values.
    user_data=('#cloud-config\n'
               'users:\n  - name: '+username+'\n'
               '    groups: [sudo]\n    shell: /bin/bash\n'
               '    sudo: ALL=(ALL) NOPASSWD:ALL\n'
               '    lock_passwd: true\n'
               '    ssh_authorized_keys:\n      - '+json.dumps(ssh_key)+'\n'
               'ssh_pwauth: false\n'
               'package_update: true\n'
               'packages: [openssh-server, qemu-guest-agent]\n'
               'runcmd:\n  - [systemctl, enable, --now, ssh]\n')
    meta='instance-id: '+hostname+'\nlocal-hostname: '+hostname+'\n'
    iso=pycdlib.PyCdlib()
    iso.new(interchange_level=3,vol_ident='cidata',joliet=3,rock_ridge='1.09')
    for name,data in [('user-data',user_data),('meta-data',meta)]:
        binary=data.encode('utf-8')
        iso.add_fp(io.BytesIO(binary),len(binary),iso_path='/'+name.upper()+';1',
                   rr_name=name,joliet_path='/'+name)
    iso.write(str(path));iso.close()

def worker(job_id,config):
    name=config['name']; target=Path(config['directory'])/name
    created=False
    try:
        with _lock:
            update(job_id,'running','Obtendo imagem oficial Ubuntu 24.04 (SHA256)...')
            if target.exists():raise RuntimeError('Diretório de destino já existe')
            target.mkdir(parents=True);created=True
            image=download_image(Path(config['directory'])/'_leskdoo_cache')
            update(job_id,'running','Gerando imagem de disco e cloud-init...')
            disk=target/'ubuntu.vdi'
            run_vbox('clonemedium','disk',str(image),str(disk),'--format','VDI')
            run_vbox('modifymedium','disk',str(disk),'--resize',str(config['disk_gb']*1024))
            seed=target/'seed.iso'
            seed_iso(seed,config['username'],config['ssh_key'],name)
            update(job_id,'running','Registrando VM no VirtualBox...')
            result=run_vbox('createvm','--name',name,'--ostype','Ubuntu_64',
                            '--basefolder',str(Path(config['directory'])),'--register')
            match=re.search(r'UUID:\s*([a-f0-9-]{36})',result,re.I)
            vmid=match.group(1) if match else name
            update(job_id,'running','Configurando CPU, RAM, NAT e disco...')
            run_vbox('modifyvm',vmid,'--memory',str(config['ram_gb']*1024),
                     '--cpus',str(config['vcpus']),'--nic1','nat',
                     '--natpf1','ssh,tcp,127.0.0.1,'+str(config['ssh_port'])+',,22',
                     '--boot1','disk','--boot2','dvd')
            run_vbox('storagectl',vmid,'--name','SATA','--add','sata','--controller','IntelAhci')
            run_vbox('storageattach',vmid,'--storagectl','SATA','--port','0',
                     '--device','0','--type','hdd','--medium',str(disk))
            run_vbox('storageattach',vmid,'--storagectl','SATA','--port','1',
                     '--device','0','--type','dvddrive','--medium',str(seed))
            run_vbox('startvm',vmid,'--type','headless')
            update(job_id,'created','VM criada e iniciada; cloud-init/SSH ainda precisam ser validados. Zabbix e IA não instalados.',vmid if vmid!=name else None)
    except Exception as exc:
        update(job_id,'error',str(exc)[:1200])
        # No automated deletion of partially registered VirtualBox VMs or disks.
        # Preserve artifacts for diagnosis and safe manual cleanup.

def submit(config):
    if not vbox_executable():raise ValueError('VirtualBox não detectado')
    if not safe_name(config.get('name','')):raise ValueError('Nome deve ter 3 a 40 caracteres alfanuméricos ou hífen')
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{1,30}',config.get('username','')):
        raise ValueError('Usuário Linux inválido')
    key=config.get('ssh_key','').strip()
    if not (key.startswith('ssh-ed25519 ') or key.startswith('ssh-rsa ')):
        raise ValueError('Informe uma chave pública SSH (ssh-ed25519 ou ssh-rsa)')
    from .inventory import host_inventory, virtual_machines
    from .planner import recommend
    host=host_inventory(); plan=recommend(host)
    if not plan['eligible']:raise ValueError('Hardware insuficiente para provisionamento automático')
    if any(v['name'].lower()==config['name'].lower() for v in virtual_machines()):
        raise ValueError('Já existe uma VM com esse nome')
    for field,minimum,maximum in [('ram_gb',4,plan['ram_gb']),('vcpus',2,plan['vcpus']),('disk_gb',40,200)]:
        value=config.get(field)
        if type(value)!=int or not minimum<=value<=maximum:
            raise ValueError(field+' fora do intervalo permitido')
    port=config.get('ssh_port',2222)
    if type(port)!=int or not 1024<=port<=65535:raise ValueError('Porta SSH inválida')
    import socket
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1',port))==0:raise ValueError('Porta SSH já está em uso')
    directory=Path(config.get('directory','')).expanduser().resolve()
    if not directory.is_absolute() or not directory.drive:
        raise ValueError('Selecione um diretório absoluto em volume Windows')
    allowed=[Path(d['mount']).resolve() for d in host['disks'] if d['free_gb']>config['disk_gb']+15]
    if not any(directory==p or p in directory.parents for p in allowed):
        raise ValueError('Volume sem espaço suficiente ou não autorizado')
    # PostgreSQL is mandatory, so errors are reported before starting.
    factory=session_factory()
    jid=secrets.token_hex(12)
    with factory() as s:
        s.add(Job(id=jid,vm_name=config['name'],state='queued',detail='Aguardando execução'))
        s.commit()
    threading.Thread(target=worker,args=(jid,{**config,'ssh_key':key,'ssh_port':port,
                            'directory':str(directory)}),daemon=True).start()
    return jid
