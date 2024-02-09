from flask import Blueprint, request
from google.cloud import datastore
from entity_processing import EntityProcessing, ContentValidation
import json
import constants


client = datastore.Client()

bp = Blueprint('user', __name__, url_prefix='/users')


@bp.route('/all', methods=['DELETE'])
def users_delete_all():
    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406

    if request.method == "DELETE":
        query = client.query(kind=constants.users)
        results = list(query.fetch())
        print(results)
        for e in results:
            user_key = client.key(constants.users, int(e.key.id))
            client.delete(user_key)
        query = client.query(kind=constants.users)
        results = list(query.fetch())
        print(results)
        return {"Success": "Deleted all users"}, 204


@bp.route('', methods=['GET'])
def users_get():
    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406

        # View all employees
    if request.method == 'GET':
        query = client.query(kind=constants.users)
        results = list(query.fetch())
        return json.dumps(results)

