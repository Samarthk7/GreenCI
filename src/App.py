from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "<h1I've deployed a change, but I've temporarily set a very strict sustainability policy for this demo.</h1>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)