import json

try:
    from secret_files import *
except ImportError:
    pass

from flask import Flask, request, redirect
import requests
from db_clases import Character
import bson
from db import characters

app = Flask(__name__)


@app.route('/')
def index():
    return app.send_static_file('DiscordEmbeddedGodot.html')


@app.route('/<path:path>')
def static_file(path):
    return app.send_static_file(path)


@app.route('/get_char/', methods=['POST'])
def get_char():
    print(
        'here'
    )
    print(request.json)
    char_id = request.json.get('char_id')
    all_chars = []
    for char in characters.find():
        all_chars.append({'name': char['name'], 'coordinates': char['coordinates'], 'id': str(char['_id'])})
    return json.dumps({'chars': all_chars})


@app.route('/set_char_position/', methods=['POST'])
def set_char_position():
    char_id = str(request.json.get('char_id'))
    x = int(request.json.get('x'))
    y = int(request.json.get('y'))
    coordinates = (x, y)
    characters.update_one({'_id': bson.ObjectId(char_id)}, {'$set': {'coordinates': coordinates}})
    return 'ok'


@app.route('/auth/', methods=['POST'])
def oauth_callback():
    code = request.form.get('code')
    if not code:
        return "Error: No authorization code received."

    token_response = requests.post('https://discord.com/api/oauth2/token', data={
        'client_id': os.environ.get('ID'),
        'client_secret': os.environ.get('SECRET'),
        'grant_type': 'authorization_code',
        'code': code
    })

    token_json = token_response.json()
    access_token = token_json.get('access_token')

    if not access_token:
        return "Error: Could not retrieve access token."

    return f'{{"access_token": "{access_token}"}}'


app.run(debug=True)
