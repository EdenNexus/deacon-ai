import flask
from flask import request, jsonify, render_template
import os
import json


app = flask.Flask(__name__)
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/data', methods=['POST'])
def receive_data():
    data = {}
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
    