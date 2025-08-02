import socket

@app.route("/get-my-ip")
def get_my_ip():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return jsonify({"internal_ip": ip_address})
