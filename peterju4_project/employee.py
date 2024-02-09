from flask import Blueprint, request
from google.cloud import datastore
from entity_processing import EntityProcessing, ContentValidation
import json
import constants


client = datastore.Client()

bp = Blueprint('employee', __name__, url_prefix='/employees')


@bp.route('/all', methods=['DELETE'])
def restaurants_delete_all():
    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406

    if request.method == "DELETE":
        query = client.query(kind=constants.employees)
        results = list(query.fetch())
        for e in results:
            employee_key = client.key(constants.employees, int(e.key.id))
            client.delete(employee_key)
        return {"Success": "Deleted all employees"}, 204


@bp.route('', methods=['POST', 'GET'])
def employees_get_post():
    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406

    # Create an employee
    if request.method == 'POST':
        content = request.get_json()

        # validate
        content_error = ContentValidation.validation_all_attributes(content, constants.employees)
        if content_error:
            return content_error

        # create
        new_employee = datastore.entity.Entity(key=client.key(constants.employees))

        # update
        new_employee = EntityProcessing.update_entity_all(content, constants.employees, new_employee)

        client.put(new_employee)
        new_employee["id"] = new_employee.key.id
        new_employee["self"] = f'{request.host_url}employees/{new_employee.key.id}'
        return new_employee, 201

    # View all employees
    elif request.method == 'GET':
        query = client.query(kind=constants.employees)
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
            e["self"] = f'{request.host_url}employees/{e.key.id}'
        output = {
            "count": count,
            "employees": results
        }
        if next_url:
            output["next"] = next_url
        return json.dumps(output)


@bp.route('/<id>', methods=['GET', 'PUT', 'DELETE', 'PATCH'])
def employees_get_put_delete(id):
    if "application/json" not in request.accept_mimetypes:
        return {"Error": "This endpoint only supports the return of JSON objects"}, 406

    employee_key = client.key(constants.employees, int(id))
    employee = client.get(key=employee_key)

    existence_error = ContentValidation.validate_entity_exists(entity_type=constants.employees, entity=employee)
    if existence_error:
        return existence_error

    # View one specific employee
    if request.method == 'GET':

        employee["id"] = employee.id
        employee["self"] = f'{request.host_url}employees/{employee.id}'
        return employee, 200

    # Delete an employee
    elif request.method == 'DELETE':

        # if unemployed, delete employee
        if employee["workplace"] is None:
            client.delete(employee)

        # update the restaurant they work at
        else:
            restaurant_id = employee["workplace"]["id"]
            restaurant_key = client.key(constants.restaurants, int(restaurant_id))
            restaurant = client.get(key=restaurant_key)

            employee, restaurant = EntityProcessing.remove_employee_from_restaurant(employee, restaurant)

            client.delete(employee)
            client.put(restaurant)
        return '', 204

    # Update all attributes of an employee
    elif request.method == 'PUT':
        content = request.get_json()

        # validate
        content_error = ContentValidation.validation_all_attributes(content, constants.employees)
        if content_error:
            return content_error

        # update
        employee = EntityProcessing.update_entity_all(content, constants.employees, employee)

        client.put(employee)
        return '', 204

    # Update some attributes of an employee
    elif request.method == 'PATCH':
        content = request.get_json()

        # validate
        content_error = ContentValidation.validation_some_attributes(content, constants.employees)
        if content_error:
            return content_error

        # update
        employee = EntityProcessing.update_entity_some(content, employee)

        client.put(employee)
        return employee, 204
    else:
        return 'Method not recognized'

