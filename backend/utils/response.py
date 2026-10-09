from flask import jsonify


def ok(data=None, message="ok"):
    return jsonify({"code": 0, "message": message, "data": data}), 200


def err(message, code=400, http_status=400):
    return jsonify({"code": code, "message": message, "data": None}), http_status
