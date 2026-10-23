"""Conservative recommendations, not capacity guarantees."""

def recommend(host):
    free = float(host['ram_available_gb'])
    usable = max(0, free - 4.0)
    ram = min(12, int(usable * .6))
    cpu = max(1, min(4, int(host['cpu_physical']) - 2))
    candidates = [d for d in host['disks'] if d['free_gb'] >= 80]
    disk = max(candidates, key=lambda d:d['free_gb'], default=None)
    enabled = ram >= 6 and cpu >= 2 and bool(disk) and host['virtualbox_installed']
    reasons = []
    if ram < 6: reasons.append('RAM livre insuficiente para o perfil combinado Zabbix + IA.')
    if cpu < 2: reasons.append('Núcleos físicos insuficientes para o perfil combinado.')
    if not disk: reasons.append('Nenhum volume com ao menos 80 GiB livres.')
    if not host['virtualbox_installed']: reasons.append('VirtualBox não localizado.')
    return {'eligible':enabled,'ram_gb':max(0,ram),'vcpus':cpu,
            'disk_gb':60 if disk else 0,'volume':disk['mount'] if disk else None,
            'model_tier':'1B–3B quantizado CPU' if enabled else 'não recomendado',
            'notes':reasons + ['Disco escolhido por espaço livre do volume; SSD/NVMe depende do mapeamento físico.',
                                'Capacidade GPU do host não é presumida disponível no guest.']}
