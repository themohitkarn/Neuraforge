from flask import Blueprint, request, jsonify
from modules.admin import services

admin_routes = Blueprint('admin_routes', __name__)

@admin_routes.route('/admin', methods=['GET'])
def get_admin():
    return jsonify({'message': 'Admin route'})

@admin_routes.route('/admin/create', methods=['POST'])
def create_admin():
    data = request.get_json()
    services.create_admin(data)
    return jsonify({'message': 'Admin created successfully'}), 201

@admin_routes.route('/admin/update', methods=['PUT'])
def update_admin():
    data = request.get_json()
    services.update_admin(data)
    return jsonify({'message': 'Admin updated successfully'}), 200

@admin_routes.route('/admin/delete', methods=['DELETE'])
def delete_admin():
    data = request.get_json()
    services.delete_admin(data)
    return jsonify({'message': 'Admin deleted successfully'}), 200

@admin_routes.route('/admin/getall', methods=['GET'])
def get_all_admins():
    admins = services.get_all_admins()
    return jsonify(admins), 200

@admin_routes.route('/admin/login', methods=['POST'])
def login_admin():
    data = request.get_json()
    token = services.login_admin(data)
    if token:
        return jsonify({'token': token}), 200
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

@admin_routes.route('/admin/logout', methods=['POST'])
def logout_admin():
    data = request.get_json()
    services.logout_admin(data)
    return jsonify({'message': 'Admin logged out successfully'}), 200