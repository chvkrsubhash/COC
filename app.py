from flask import Flask, jsonify
import socket

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Flask App is Running!"

@app.route("/get-my-ip")
def get_my_ip():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return jsonify({"internal_ip": ip_address})

if __name__ == "__main__":
    app.run()
