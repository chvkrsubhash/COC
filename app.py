from flask import Flask, jsonify
import socket
import requests

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Flask App is Running!"

@app.route("/get-my-ip")
def get_internal_ip():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return jsonify({"internal_ip": ip_address})

@app.route("/public-ip")
def get_public_ip():
    ip = requests.get("https://api64.ipify.org").text
    return jsonify({"public_ip": ip})

if __name__ == "__main__":
    app.run()
