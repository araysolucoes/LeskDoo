# LeskDoo — Aray Soluções

Plataforma local para inspecionar o Windows 11, detectar recursos de hardware e máquinas virtuais do VirtualBox, recomendar capacidade e futuramente provisionar Ubuntu Server com Zabbix, Ollama e chat integrado.

## Estado atual: V001
- Inventário CPU, RAM, GPU, volumes/discos e adaptadores de rede.
- Detecção de VirtualBox e listagem de VMs, bridges e estado operacional.
- Recomendação conservadora de RAM, vCPU e disco.
- Dashboard Flask local; botões de ligar e desligar via ACPI condicionados ao `LESDKOO_ALLOW_MUTATIONS=true`.
- Modelo de persistência PostgreSQL preparado, porém ainda não conectado ao fluxo completo.
- Docker Compose inicial para PostgreSQL e Ollama/Open WebUI.
- Testes unitários básicos do planejador.

**Ainda não implementados:** criação automática de VM, cloud-init, provisionamento Ubuntu, SSH, Zabbix, deploy automático de IA, controles completos de autenticação/CSRF e CRUD persistente. Não exponha a interface à rede.

## Execução Windows 11
Requisitos: Python 3.12+, VirtualBox e, para PostgreSQL, Docker/Compose opcional.

```powershell
git clone https://github.com/araysolucoes/LeskDoo.git
cd LeskDoo
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

Acesse http://127.0.0.1:5050 e mantenha `LESDKOO_ALLOW_MUTATIONS=false` até implementar autenticação, CSRF e autorizações robustas.

## Desenvolvimento
```powershell
python -m pytest -q
git pull --ff-only origin main
```

Consulte [docs/ROADMAP.md](docs/ROADMAP.md) para o roteiro P0–P3. Não versionar `.env`, chaves privadas ou senhas reais.
