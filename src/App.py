from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>This is just testing .</h1>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

