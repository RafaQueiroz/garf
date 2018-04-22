from flask import Flask, render_template

app = Flask(__name__)


@app.route("/configuracoes")
def index():
    return render_template('index.html')


@app.route("/regras-ativas")
def regras_ativas():
    return render_template('regras-ativas.html')
    

@app.route("/historico")
def historico():
    return render_template('historico.html')


if __name__ == "__main__":
    app.run()