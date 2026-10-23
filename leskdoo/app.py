"""First milestone: read-only dashboard and deliberately gated VM power actions."""
import os
import re
from flask import Flask, jsonify, render_template, request, abort
from .inventory import host_inventory, virtual_machines, network_interfaces, vbox
from .planner import recommend

UUID = re.compile(r'^[0-9a-fA-F-]{36}$')

def create_app():
    app = Flask(__name__, template_folder='../templates')
    app.secret_key = os.getenv('LESDKOO_SECRET_KEY') or os.urandom(32)
    app.config['JSON_SORT_KEYS'] = False

    @app.get('/')
    def dashboard():
        return render_template('dashboard.html')

    @app.get('/api/status')
    def status():
        host = host_inventory()
        warnings = []
        try: vms = virtual_machines()
        except Exception as exc: vms=[]; warnings.append(str(exc))
        try: bridges = network_interfaces()
        except Exception as exc: bridges=[]; warnings.append(str(exc))
        return jsonify({'host':host, 'recommendation':recommend(host),'vms':vms,
                        'bridged_interfaces':bridges,'warnings':warnings})

    @app.post('/api/vms/<uuid>/power')
    def vm_power(uuid):
        if os.getenv('LESDKOO_ALLOW_MUTATIONS', 'false').lower() != 'true':
            return jsonify({'error':'Operações destrutivas desabilitadas no .env'}),403
        if not UUID.fullmatch(uuid): abort(400)
        action = (request.get_json(silent=True) or {}).get('action')
        if action not in ('start','acpi_shutdown'): abort(400)
        current = next((v for v in virtual_machines() if v['uuid'].lower() == uuid.lower()),None)
        if current is None: abort(404)
        if action == 'start' and current['state'] != 'stopped': abort(409)
        if action == 'acpi_shutdown' and current['state'] != 'running': abort(409)
        if action == 'start': vbox(['startvm',uuid,'--type','headless'])
        else: vbox(['controlvm',uuid,'acpipowerbutton'])
        return jsonify({'ok':True,'action':action,'vm':uuid})

    return app
