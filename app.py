from flask import Flask, render_template

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('home.html')


@app.errorhandler(404)
def page_not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(403)
def restricted(error):
    return render_template('403.html'), 403


if __name__ == '__main__':
    app.run(debug=True)
