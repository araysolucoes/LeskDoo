"""Guest automation for LeskDoo-managed Ubuntu guests.

Operations run only after the operator explicitly starts the service job.
First connection to a newly created VM uses TOFU for the SSH host key,
persisted in a dedicated known_hosts file. Review fingerprints before use in
security-critical environments.
"""
import os
from pathlib import Path
import secrets
import time
import socket
import paramiko

SCRIPT = r"""set -eu
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update
sudo apt-get install -y ca-certificates curl docker.io docker-compose-v2 || {
  sudo apt-get install -y ca-certificates curl docker.io
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  ARCH="$(dpkg --print-architecture)"
  sudo curl -fsSL "https://github.com/docker/compose/releases/download/v2.39.4/docker-compose-linux-${ARCH}" -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
}
sudo systemctl enable --now docker
sudo mkdir -p /opt/leskdoo
sudo chmod 700 /opt/leskdoo
sudo docker compose -f /opt/leskdoo/compose.yml --env-file /opt/leskdoo/.env config -q
sudo docker compose -f /opt/leskdoo/compose.yml --env-file /opt/leskdoo/.env up -d
sudo docker compose -f /opt/leskdoo/compose.yml --env-file /opt/leskdoo/.env ps
"""

COMPOSE = """services:
  zabbix-db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: zabbix
      POSTGRES_PASSWORD: ${ZABBIX_DB_PASSWORD:?required}
      POSTGRES_DB: zabbix
    volumes:
      - zabbix-db:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U zabbix -d zabbix"]
      interval: 10s
      retries: 15
  zabbix-server:
    image: zabbix/zabbix-server-pgsql:alpine-7.4-latest
    restart: unless-stopped
    depends_on:
      zabbix-db:
        condition: service_healthy
    environment:
      DB_SERVER_HOST: zabbix-db
      POSTGRES_USER: zabbix
      POSTGRES_PASSWORD: ${ZABBIX_DB_PASSWORD:?required}
      POSTGRES_DB: zabbix
    ports:
      - "127.0.0.1:10051:10051"
  zabbix-web:
    image: zabbix/zabbix-web-nginx-pgsql:alpine-7.4-latest
    restart: unless-stopped
    depends_on:
      zabbix-db:
        condition: service_healthy
    environment:
      DB_SERVER_HOST: zabbix-db
      POSTGRES_USER: zabbix
      POSTGRES_PASSWORD: ${ZABBIX_DB_PASSWORD:?required}
      POSTGRES_DB: zabbix
      ZBX_SERVER_HOST: zabbix-server
      PHP_TZ: America/Sao_Paulo
    ports:
      - "0.0.0.0:8080:8080"
  zabbix-agent:
    image: zabbix/zabbix-agent2:alpine-7.4-latest
    restart: unless-stopped
    privileged: false
    environment:
      ZBX_SERVER_HOST: zabbix-server
      ZBX_HOSTNAME: leskdoo-guest
  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    volumes:
      - ollama:/root/.ollama
  chat:
    image: ghcr.io/open-webui/open-webui:main
    restart: unless-stopped
    depends_on: [ollama]
    environment:
      OLLAMA_BASE_URL: http://ollama:11434
      WEBUI_SECRET_KEY: ${WEBUI_SECRET_KEY:?required}
      ENABLE_SIGNUP: "false"
    ports:
      - "0.0.0.0:3000:8080"
    volumes:
      - webui:/app/backend/data
volumes:
  zabbix-db:
  ollama:
  webui:
"""

def validate_ssh_key_path(path):
    key=Path(path).expanduser().resolve()
    base=Path.home().resolve()
    if base not in key.parents or not key.is_file():
        raise ValueError("Arquivo de chave privada precisa existir na pasta do usuário atual")
    return key

def wait_ssh(port, timeout=300):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=3):
                return
        except OSError:
            time.sleep(5)
    raise TimeoutError("Ubuntu não disponibilizou SSH no intervalo de 5 minutos")

def ssh_session(username,port,key_file,known_hosts):
    client=paramiko.SSHClient()
    if known_hosts.exists():
        client.load_host_keys(str(known_hosts))
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        # This known_hosts belongs solely to the new managed guest.
        known_hosts.parent.mkdir(parents=True,exist_ok=True)
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('127.0.0.1',port=port,username=username,key_filename=str(key_file),
                   allow_agent=False,look_for_keys=False,timeout=12,auth_timeout=12,banner_timeout=15)
    if not known_hosts.exists():
        client.save_host_keys(str(known_hosts))
    return client

def exec_checked(client,cmd,timeout=1800):
    stdin,stdout,stderr=client.exec_command(cmd,timeout=timeout)
    rc=stdout.channel.recv_exit_status()
    out=stdout.read().decode('utf-8',errors='replace')
    err=stderr.read().decode('utf-8',errors='replace')
    if rc:
        raise RuntimeError(f"Etapa Linux falhou ({rc}): {(err or out)[-1600:]}")
    return out

def deploy(username,port,key_file,folder,update):
    key=validate_ssh_key_path(key_file)
    wait_ssh(port)
    known_hosts=Path(folder)/'guest_known_hosts'
    client=ssh_session(username,port,key,known_hosts)
    try:
        update('running','Validando cloud-init e conectividade SSH...')
        exec_checked(client,'cloud-init status --wait',timeout=1800)
        update('running','Transferindo compose e credenciais para a VM...')
        env=('ZABBIX_DB_PASSWORD='+secrets.token_urlsafe(35)+'\n'
             'WEBUI_SECRET_KEY='+secrets.token_urlsafe(45)+'\n')
        sftp=client.open_sftp()
        with sftp.file('/tmp/leskdoo-compose.yml','w') as f:f.write(COMPOSE)
        with sftp.file('/tmp/leskdoo.env','w') as f:f.write(env)
        sftp.close()
        exec_checked(client,'sudo mkdir -p /opt/leskdoo && sudo mv /tmp/leskdoo-compose.yml /opt/leskdoo/compose.yml && sudo mv /tmp/leskdoo.env /opt/leskdoo/.env && sudo chmod 600 /opt/leskdoo/.env')
        update('running','Instalando Docker e iniciando Zabbix, Ollama e Chat...')
        output=exec_checked(client,'bash -se <<\'LESDKOO_SCRIPT\'\n'+SCRIPT+'\nLESDKOO_SCRIPT',timeout=3600)
        update('running','Baixando modelo local quantizado qwen2.5:1.5b...')
        exec_checked(client,'sudo docker compose -f /opt/leskdoo/compose.yml --env-file /opt/leskdoo/.env exec -T ollama ollama pull qwen2.5:1.5b',timeout=3600)
        update('running','Verificando Ollama e serviços...')
        exec_checked(client,'sudo docker compose -f /opt/leskdoo/compose.yml --env-file /opt/leskdoo/.env exec -T ollama ollama list')
        update('services_started','Stack iniciado, modelo qwen2.5:1.5b disponível. Zabbix local: 127.0.0.1:18080 · Chat: 127.0.0.1:13000. Verifique a prontidão das interfaces.')
        return output
    finally:
        client.close()
