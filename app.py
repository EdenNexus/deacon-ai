import flask
from flask import request, jsonify, render_template
import os
import json

deacon_ai_bp = flask.Blueprint('deacon_ai', __name__)


@deacon_ai_bp.route('/')
def home():
    return render_template('index.html')

@deacon_ai_bp.route('/api/data', methods=['POST'])
def receive_data():
    data = {}
    return jsonify(data)
