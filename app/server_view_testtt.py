from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "Hello!"

if __name__ == "__main__":
    app.run(host='127.0.0.9', port=9999, debug=True)