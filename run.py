import os
from dotenv import load_dotenv
from waitress import serve
from leskdoo.app import create_app
load_dotenv()
if __name__ == '__main__':
    host = os.getenv('LESDKOO_HOST', '127.0.0.1')
    if host not in ('127.0.0.1', '::1', 'localhost'):
        raise SystemExit('LeskDoo somente pode escutar em localhost. Não exponha na rede.')
    serve(create_app(), host=host, port=int(os.getenv('LESDKOO_PORT', '5050')))
