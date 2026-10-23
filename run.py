import os
from dotenv import load_dotenv
from waitress import serve
from leskdoo.app import create_app
load_dotenv()
if __name__ == '__main__':
    serve(create_app(), host=os.getenv('LESDKOO_HOST','127.0.0.1'),port=int(os.getenv('LESDKOO_PORT','5050')))
