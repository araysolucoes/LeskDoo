"""LeskDoo Flask application - local management dashboard."""
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

    @app.before_request
    def restrict_local_api():
        # Prevent browsers on remote pages from using this loopback-only admin panel.
        # A future remote deployment requires real authentication and TLS.
        if request.path.startswith('/api/'):
            if request.remote_addr not in ('127.0.0.1', '::1'):
                return jsonify({'error': 'API permitida apenas via localhost'}), 403
            if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                from urllib.parse import urlsplit
                origin = request.headers.get('Origin')
                if origin:
                    parsed = urlsplit(origin)
                    if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
                        return jsonify({'error': 'Origem não autorizada'}), 403

    @app.after_request
    def harden(response):
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        return response

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

    @app.get('/api/jobs')
    def job_list():
        try:
            from .provision import jobs
            return jsonify({'jobs':jobs()})
        except Exception as exc:
            return jsonify({'jobs':[], 'error':str(exc)}),503

    @app.post('/api/jobs')
    def create_job():
        if os.getenv('LESDKOO_ALLOW_MUTATIONS','false').lower()!='true':
            return jsonify({'error':'Habilite LESDKOO_ALLOW_MUTATIONS=true no .env para provisionar'}),403
        # Loopback-only deployment required. This is NOT suitable for exposed LAN access.
        from .provision import submit
        try:
            payload=request.get_json(silent=True)
            if not isinstance(payload,dict):abort(400)
            job_id=submit(payload)
            return jsonify({'id':job_id,'state':'queued'}),202
        except ValueError as exc:
            return jsonify({'error':str(exc)}),422
        except Exception as exc:
            return jsonify({'error':str(exc)}),503

    @app.post('/api/jobs/<job_id>/services')
    def deploy_services(job_id):
        if os.getenv('LESDKOO_ALLOW_MUTATIONS','false').lower()!='true':
            return jsonify({'error':'Mutações estão desativadas'}),403
        if not re.fullmatch(r'[0-9a-f]{24}',job_id):
            abort(400)
        from .provision import start_services
        try:
            payload=request.get_json(silent=True)
            if not isinstance(payload,dict):abort(400)
            start_services(job_id,payload)
            return jsonify({'id':job_id,'state':'services_queued'}),202
        except ValueError as exc:
            return jsonify({'error':str(exc)}),422
        except Exception as exc:
            return jsonify({'error':str(exc)}),503

    @app.post('/api/vms/<uuid>/power')
    def vm_power(uuid):
        if os.getenv('LESDKOO_ALLOW_MUTATIONS', 'false').lower() != 'true':
            return jsonify({'error':'Operações desabilitadas no .env'}),403
        if not UUID.fullmatch(uuid): abort(400)
        action = (request.get_json(silent=True) or {}).get('action')
        if action not in ('start','acpi_shutdown'): abort(400)
        current = next((v for v in virtual_machines() if v['uuid'].lower() == uuid.lower()),None)
        if current is None: abort(404)
        # Do not operate on unrelated machines, even if VirtualBox lists them.
        from .provision import jobs
        registered = jobs()
        if not any(j.get('uuid', '').lower() == uuid.lower() for j in registered if j.get('uuid')):
            return jsonify({'error': 'VM não gerenciada pelo LeskDoo'}), 403
        if action == 'start' and current['state'] != 'stopped': abort(409)
        if action == 'acpi_shutdown' and current['state'] != 'running': abort(409)
        if action == 'start': vbox(['startvm',uuid,'--type','headless'])
        else: vbox(['controlvm',uuid,'acpipowerbutton'])
        return jsonify({'ok':True,'action':action,'vm':uuid})

    return app
