from flask import jsonify
from six.moves.urllib.request import urlopen
from jose import jwt
import json
import constants


class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code


class JWTVerification:

    @staticmethod
    def authorize_protected_resource(restaurant, payload):
        if restaurant['owner'] != payload['sub']:
            return {"Error": "You are not authorized to view this restaurant"}, 403
        return

    @staticmethod
    def verify_jwt(request):
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization'].split()
            token = auth_header[1]
        else:
            raise AuthError({"Error": "Missing token"}, 401)

        jsonurl = urlopen("https://" + constants.DOMAIN + "/.well-known/jwks.json")
        jwks = json.loads(jsonurl.read())
        try:
            unverified_header = jwt.get_unverified_header(token)
        except jwt.JWTError:
            raise AuthError({"code": "invalid_header",
                             "description":
                                 "Invalid header. "
                                 "Use an RS256 signed JWT Access Token"}, 401)
        if unverified_header["alg"] == "HS256":
            raise AuthError({"code": "invalid_header",
                             "description":
                                 "Invalid header. "
                                 "Use an RS256 signed JWT Access Token"}, 401)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"]
                }
        if rsa_key:
            try:
                payload = jwt.decode(
                    token,
                    rsa_key,
                    algorithms=constants.ALGORITHMS,
                    audience=constants.CLIENT_ID,
                    issuer="https://" + constants.DOMAIN + "/"
                )
            except jwt.ExpiredSignatureError:
                raise AuthError({"code": "token_expired",
                                 "description": "token is expired"}, 401)
            except jwt.JWTClaimsError:
                raise AuthError({"code": "invalid_claims",
                                 "description":
                                     "incorrect claims,"
                                     " please check the audience and issuer"}, 401)
            except Exception:
                raise AuthError({"code": "invalid_header",
                                 "description":
                                     "Unable to parse authentication"
                                     " token."}, 401)

            return payload
        else:
            raise AuthError({"code": "no_rsa_key",
                             "description":
                                 "No RSA key in JWKS"}, 401)

    # Decode the JWT supplied in the Authorization header
    @staticmethod
    def decode_jwt(request):
        payload = JWTVerification.verify_jwt(request)
        return payload


class EntityProcessing:

    @staticmethod
    def update_entity_all(content, entity_type, entity):
        """
        Updates the entity with the content passed in the JSON request
        :param content: request JSON
        :param entity_type: either "restaurants" or "employees" (uses constants.x)
        :param entity: the entity to be updated with new information
        :return: updated entity
        """
        # employees
        if entity_type == "employees":
            if "workplace" in entity:
                entity.update(content)
            else:
                entity.update({
                    "name": content["name"],
                    "wage": float(content["wage"]),
                    "position": content["position"],
                    "workplace": None})
        # restaurants
        elif entity_type == "restaurants":
            entity.update(content)
            if "employees" not in entity:
                entity['employees'] = []
        return entity

    @staticmethod
    def update_entity_some(content, entity):
        """

        :param content:
        :param entity:
        :return:
        """
        entity.update(content)
        return entity

    @staticmethod
    def link_restaurant_and_employee(restaurant, employee, request):
        """
        makes a logical connection between restaurant and employee (aka, a restaurant hires this employee)
        :param restaurant: hiring restaurant
        :param employee: new employee
        :param request: flask request
        :return: updated restaurant and employee
        """
        employee['workplace'] = {
            "id": restaurant.id,
            "name": restaurant['name'],
            "self": f'{request.host_url}restaurants/{restaurant.id}'
        }
        restaurant['employees'].append({
            "id": employee.id,
            "name": employee["name"],
            "self": f'{request.host_url}employees/{employee.id}'
        })
        return restaurant, employee

    @staticmethod
    def remove_employee_from_restaurant(employee, restaurant):
        """

        :param employee: employee entity
        :param restaurant: restaurant entity
        :return:
        """
        index_counter = 0
        for employee_iter in restaurant["employees"]:
            if int(employee_iter["id"]) == int(employee.id):
                restaurant["employees"].pop(index_counter)
                employee["workplace"] = None
                return employee, restaurant
            index_counter += 1


class ContentValidation:

    @staticmethod
    def validate_entity_exists(entity_type, entity):
        """
        validates entity exists
        :param entity_type: the string 'restaurants' or 'employees' (from constants.x)
        :param entity:
        :return: if entity exists, returns nothing. if not, returns error message and code.
        """
        if entity is None:
            return {"Error": f'No {entity_type[:-1]} with this {entity_type[:-1]}_id exists'}, 404
        return

    @staticmethod
    def validation_employee_removal(employee, restaurant):
        """
        validates that the employee exists, the restaurant exists, and the employee currently works at the restaurant
        :param employee:
        :param restaurant:
        :return: if content is valid, returns nothing. if not, returns error message and code.
        """
        if restaurant is None or employee is None:
            return {"Error": "No employee with this employee_id works at the restaurant with this restaurant_id"}, 404
        for employee_iter in restaurant["employees"]:
            if int(employee_iter["id"]) == int(employee.id):
                return
        return {"Error": "No employee with this employee_id works at the restaurant with this restaurant_id"}, 404

    @staticmethod
    def validation_employee_hire(employee, restaurant):
        """
        validates that the restaurant and employee exist, that the employee doesn't already have a workplace
        :param employee:
        :param restaurant:
        :return: if content is valid, returns nothing. if not, returns error message and code.
        """
        if employee is None or restaurant is None:
            return {"Error": "The specified restaurant and/or employee does not exist"}, 404
        if employee['workplace']:
            return {"Error": "The employee already has a workplace"}, 403
        return

    @staticmethod
    def validation_some_attributes(content, entity_type):
        """

        :param content:
        :param entity_type:
        :return:
        """
        # no extraneous attributes
        if len(content) > 3:
            return {"Error": "The request object includes extraneous attributes"}, 400

        # RESTAURANT VALIDATION ------------------------------------------------------
        if entity_type == "restaurants":

            # can't have all three attributes of restaurant (name, cost, cuisine)
            if "cost" in content and "cuisine" in content and "name" in content:
                return {"Error": "The request object includes all three attributes. Please use a PUT request to update all three attributes of a restaurant"}, 400

            # cost:
            if "cost" in content:
                costs_list = ["$", "$$", "$$$", "$$$$"]
                if content["cost"] not in costs_list:
                    return {"Error": "The ‘cost’ value must equal $, $$, $$$, or $$$$"}, 400

        # EMPLOYEE VALIDATION ------------------------------------------------------
        elif entity_type == "employees":

            # can't have all three attributes of restaurant (name, cost, cuisine)
            if "wage" in content and "position" in content and "name" in content:
                return {"Error": "The request object includes all three attributes. Please use a PUT request to update all three attributes of an employee"}, 400

            # above minimum wage:
            if "wage" in content:
                if content["wage"] < 14.20:
                    return {"Error": "The 'wage' value must not be less than 14.20"}, 400

        return

    @staticmethod
    def validation_all_attributes(content, entity_type):
        """
        Validates the JSON content of any incoming request to PUT or POST an entity.
        Content must include all attributes of an entity.
        :param content: request JSON
        :param entity_type: either "restaurants" or "employees" (uses constants.x)
        :return: if content is valid, returns nothing. if not, returns error message and code.
        """
        # no extraneous attributes
        if len(content) > 3:
            return {"Error": "The request object includes extraneous attributes"}, 400

        # EMPLOYEE VALIDATION --------------------------------------------------------
        if entity_type == "employees":
            # needs all three attributes of employee (name, wage, position)
            if "name" not in content or "wage" not in content or "position" not in content:
                return {"Error": "The request object is missing at least one of the required attributes"}, 400

            # above minimum wage:
            if content["wage"] < 14.20:
                return {"Error": "The 'wage' value must not be less than 14.20"}, 400

        # RESTAURANT VALIDATION ------------------------------------------------------
        elif entity_type == "restaurants":
            # needs all three attributes of restaurant (name, cost, cuisine)
            if "cost" not in content or "cuisine" not in content or "name" not in content:
                return {"Error": "The request object is missing at least one of the required attributes"}, 400

            # cost:
            costs_list = ["$", "$$", "$$$", "$$$$"]
            if content["cost"] not in costs_list:
                return {"Error": "The ‘cost’ value must equal $, $$, $$$, or $$$$"}, 400

        return



