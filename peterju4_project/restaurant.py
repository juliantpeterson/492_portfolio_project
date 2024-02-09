from flask import Blueprint, request
from google.cloud import datastore
from entity_processing import EntityProcessing, ContentValidation, JWTVerification
import json
import constants

client = datastore.Client()

bp = Blueprint('restaurant', __name__, url_prefix='/restaurants')


@bp.route('/all', methods=['DELETE'])
def restaurants_delete_all():
    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406

    if request.method == "DELETE":
        query = client.query(kind=constants.restaurants)
        results = list(query.fetch())
        for e in results:
            restaurant_key = client.key(constants.restaurants, int(e.key.id))
            client.delete(restaurant_key)
        return {"Success": "Deleted all restaurants"}, 204


@bp.route('', methods=['POST', 'GET'])
def restaurants_post_get():
    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406
    payload = JWTVerification.verify_jwt(request)

    # Create a restaurant:
    if request.method == 'POST':

        content = request.get_json()

        # validate
        content_error = ContentValidation.validation_all_attributes(content, constants.restaurants)
        if content_error:
            return content_error

        content['owner'] = payload['sub']

        # create
        new_restaurant = datastore.entity.Entity(key=client.key(constants.restaurants))

        # update
        new_restaurant = EntityProcessing.update_entity_all(content, constants.restaurants, new_restaurant)

        client.put(new_restaurant)
        new_restaurant["id"] = new_restaurant.key.id
        new_restaurant["self"] = f'{request.url}/{new_restaurant.key.id}'

        return new_restaurant, 201

    # Get ALL restaurants, with pagination (limit = 5):
    elif request.method == 'GET':
        query = client.query(kind=constants.restaurants)
        count = len(list(query.fetch()))
        q_limit = int(request.args.get('limit', '5'))
        q_offset = int(request.args.get('offset', '0'))
        g_iterator = query.fetch(limit=q_limit, offset=q_offset)
        pages = g_iterator.pages
        results = list(next(pages))
        if g_iterator.next_page_token:
            next_offset = q_offset + q_limit
            next_url = request.base_url + "?limit=" + str(q_limit) + "&offset=" + str(next_offset)
        else:
            next_url = None
        for e in results:
            e["id"] = e.key.id
            e["self"] = f'{request.url}/{e.key.id}'
        output = {
            "count": count,
            "restaurants": results
        }
        if next_url:
            output["next"] = next_url
        return json.dumps(output)


@bp.route('/<id>', methods=['GET', 'DELETE', 'PUT', 'PATCH'])
def restaurants_get_delete_update(id):
    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406
    payload = JWTVerification.verify_jwt(request)

    restaurant_key = client.key(constants.restaurants, int(id))
    restaurant = client.get(key=restaurant_key)

    existence_error = ContentValidation.validate_entity_exists(entity_type=constants.restaurants, entity=restaurant)
    if existence_error:
        return existence_error

    authorization_error = JWTVerification.authorize_protected_resource(restaurant, payload)
    if authorization_error:
        return authorization_error

    # Get a specific restaurant
    if request.method == 'GET':

        restaurant["id"] = restaurant.key.id
        restaurant["self"] = f"{request.url}"
        return restaurant, 200

    # Delete a restaurant
    elif request.method == 'DELETE':

        # remove all employees from restaurant
        for employee in restaurant["employees"]:
            employee_key = client.key(constants.employees, int(employee["id"]))
            emp = client.get(key=employee_key)
            emp["workplace"] = None
            client.put(emp)

        client.delete(restaurant_key)
        return '', 204

    # Update all attributes of a restaurant
    elif request.method == 'PUT':
        content = request.get_json()

        # validate
        content_error = ContentValidation.validation_all_attributes(content, constants.restaurants)
        if content_error:
            return content_error

        # update
        restaurant = EntityProcessing.update_entity_all(content, constants.restaurants, restaurant)

        client.put(restaurant)
        return '', 204

    # Update some attributes of a restaurant
    elif request.method == 'PATCH':
        content = request.get_json()

        # validate
        content_error = ContentValidation.validation_some_attributes(content, constants.restaurants)
        if content_error:
            return content_error

        # update
        restaurant = EntityProcessing.update_entity_some(content, restaurant)

        client.put(restaurant)
        return '', 204
    else:
        return 'Method not recognized'


@bp.route('/<restaurant_id>/employees/<employee_id>', methods=['PUT', 'DELETE'])
def add_delete_employee_with_restaurant(restaurant_id, employee_id):

    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406

    payload = JWTVerification.verify_jwt(request)

    restaurant_key = client.key(constants.restaurants, int(restaurant_id))
    restaurant = client.get(key=restaurant_key)
    employee_key = client.key(constants.employees, int(employee_id))
    employee = client.get(key=employee_key)

    authorization_error = JWTVerification.authorize_protected_resource(restaurant, payload)
    if authorization_error:
        return authorization_error

    # connect an employee with a restaurant
    if request.method == 'PUT':
        # validate
        hiring_error = ContentValidation.validation_employee_hire(employee, restaurant)
        if hiring_error:
            return hiring_error

        # update entities
        restaurant, employee = EntityProcessing.link_restaurant_and_employee(restaurant, employee, request)

        client.put(restaurant)
        client.put(employee)
        return '', 204

    # remove connection between an employee and a restaurant
    if request.method == 'DELETE':
        # validate
        removal_error = ContentValidation.validation_employee_removal(employee, restaurant)
        if removal_error:
            return removal_error

        # update
        employee, restaurant = EntityProcessing.remove_employee_from_restaurant(employee, restaurant)

        client.put(restaurant)
        client.put(employee)
        return '', 204

