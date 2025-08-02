from flask import Flask, jsonify, request
from flask_cors import CORS
import socket
import requests

app = Flask(__name__)
CORS(app)

@app.route("/")
def home():
    return "✅ Flask Flask app is running on Vercel!"

@app.route("/get-my-ip")
def get_internal_ip():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return jsonify({"internal_ip": ip_address})

@app.route("/public-ip")
def get_public_ip():
    ip = requests.get("https://api64.ipify.org").text
    return jsonify({"public_ip": ip})


# 👇 Required for Vercel serverless
def handler(environ, start_response):
    return app(environ, start_response)
