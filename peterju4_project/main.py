from google.cloud import datastore
from flask import Flask, request, jsonify, render_template, session, url_for, redirect
import restaurant
import employee
import user
import constants
from entity_processing import AuthError

from six.moves.urllib.request import urlopen
from jose import jwt

from os import environ as env
from urllib.parse import quote_plus, urlencode
from dotenv import find_dotenv, load_dotenv

import json
import requests

from authlib.integrations.flask_client import OAuth

from six.moves.urllib.parse import urlencode
from urllib.parse import quote_plus


app = Flask(__name__)
app.secret_key = 'SECRET_KEY'

app.register_blueprint(employee.bp)
app.register_blueprint(restaurant.bp)
app.register_blueprint(user.bp)

client = datastore.Client()




oauth = OAuth(app)

auth0 = oauth.register(
    'auth0',
    client_id=constants.CLIENT_ID,
    client_secret=constants.CLIENT_SECRET,
    api_base_url="https://" + constants.DOMAIN,
    access_token_url="https://" + constants.DOMAIN + "/oauth/token",
    authorize_url="https://" + constants.DOMAIN + "/authorize",
    client_kwargs={
        'scope': 'openid profile email',
    },
    server_metadata_url=f'https://{constants.DOMAIN}/.well-known/openid-configuration'
)


# This code is adapted from:
# https://auth0.com/docs/quickstart/backend/python/01-authorization?_ga=2.46956069.349333901.1589042886-466012638.1589042885#create-the-jwt-validation-decorator

@app.route('/')
def home():
    if session:
        user = session.get('user')
        id_token = session.get('user')['id_token']
        sub = session.get('user')['userinfo']['sub']

        # check to see if this user already exists
        query = client.query(kind=constants.users)
        results = list(query.fetch())
        for user_iter in results:
            if user_iter["sub"] == sub:
                print("RETURN VISITOR")
                return render_template("home.html",
                                       session=user,
                                       pretty=json.dumps({'id_token': id_token,
                                                          'sub': sub}))
        new_owner = datastore.entity.Entity(key=client.key(constants.users))
        new_owner.update({
            'sub': sub})
        client.put(new_owner)
        print("NEW VISITOR")
        return render_template("home.html",
                               session=user,
                               pretty=json.dumps({'id_token': id_token,
                                                  'sub': sub}))

    else:
        return render_template("home.html", session=session.get('user'))


# Generate a JWT from the Auth0 domain and return it
# Request: JSON body with 2 properties with "username" and "password"
#       of a user registered with this Auth0 domain
# Response: JSON with the JWT as the value of the property id_token
@app.route('/login')
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session['user'] = token
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://" + constants.DOMAIN
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": constants.CLIENT_ID,
            },
            quote_via=quote_plus,
        )
    )


@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response



"""
def login_user():
    content = request.get_json()
    username = content["username"]
    password = content["password"]
    body = {'grant_type': 'password',
            'username': username,
            'password': password,
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
            }
    headers = {'content-type': 'application/json'}
    url = 'https://' + DOMAIN + '/oauth/token'
    r = requests.post(url, json=body, headers=headers)
    id_token = r.json()["id_token"]
    url = f'{request.host_url}decode'
    headers = {'Authorization': f'Bearer {id_token}'}
    r = requests.get(url, headers=headers)
    sub = r.json()["sub"]
    # check to see if this user already exists
    query = client.query(kind=constants.users)
    results = list(query.fetch())
    for user in results:
        if user["id"] == sub:
            return {'return': {
                "id": sub,
                "jwt": id_token
            }}, 200

    new_owner = datastore.entity.Entity(key=client.key(constants.users))
    new_owner.update({'id': sub, 'restaurants': []})
    client.put(new_owner)
    return {'first': {
        "id": sub,
        "jwt": id_token
    }}, 201
"""

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080, debug=True)
