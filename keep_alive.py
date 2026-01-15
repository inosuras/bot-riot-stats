from flask import Flask
from threading import Thread

app = Flask('') #Création d'une instance de l'application Flask

@app.route('/') #Définition de la route principale de l'application Flask
def home():
    return "I'm alive!"

def run():
  app.run(host='0.0.0.0', port=8080) #Démarrage de l'application Flask sur le port 8080

def keep_alive():     #Fonction pour démarrer l'application Flask dans un thread séparé
    t = Thread(target=run)   #Création d'un thread pour exécuter l'application Flask
    t.start()