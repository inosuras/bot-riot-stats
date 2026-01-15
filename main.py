from discord.ext import tasks
import requests
import discord

import os
from dotenv import load_dotenv
load_dotenv()  # Charge les variables d'environnement à partir du fichier .env


try:
    with open("last match.txt", "r") as f:
        last_match_id = f.read().strip()  # Lire l'ID du dernier match traité depuis le fichier texte

except: last_match_id = None  # Si le fichier n'existe pas, initialiser last_match_id à None

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def fetch_lol_stats(game_name, tag_line):

    api_key = os.getenv("RIOT_API_KEY")  #Récupère la clé API Riot Games à partir des variables d'environnement pour authentifier les requêtes API dans le fichier .env.

    url =(f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={api_key}")

    response = requests.get(url)      #Créee une requête GET à l'URL spécifiée c'est-à-dire l'API de Riot Games pour obtenir des informations sur un compte Riot ID.
        #print(response.json())      #Affiche la réponse de l'API au format JSON, qui contient les informations du compte Riot ID demandé.

    account_data = response.json()      #Stocke les données JSON de la réponse dans une variable pour un traitement ultérieur.

    puuid = account_data.get("puuid")    #Extrait la valeur associée à la clé "puuid" des données du compte et la stocke dans une variable.

        #print("PUUID:", puuid) #Affiche le PUUID (Player Unique Identifier) du compte Riot ID.

    rank_url =(f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={api_key}")

    rank = requests.get(rank_url)      #Crée une requête GET à l'URL spécifiée pour obtenir les informations de classement du joueur identifié par le PUUID.      
    rank = rank.json()      #Stocke les données JSON de la réponse dans une variable pour un traitement ultérieur.
    #print(rank)

    tier = "Unranked"
    division = ""
    lp = 0
    wins = 0
    losses = 0
    win_rate = 0

    for entry in rank:
        if entry["queueType"] == "RANKED_SOLO_5x5":
            tier = entry["tier"]
            division = entry["rank"]
            lp = entry["leaguePoints"]
            wins = entry["wins"]
            losses = entry["losses"]
            win_rate = (wins / (wins + losses)) * 100
            #print(f"Rank: {tier} {division} | {lp} LP | Win Rate: {win_rate:.2f}%")
            break
    

    matches_url =(f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1&api_key={api_key}")

    matches =requests.get(matches_url)      #Crée une requête GET à l'URL spécifiée pour obtenir l'historique des matchs du joueur identifié par le PUUID.
        #print(matches.json())      #Affiche la réponse de l'API au format JSON, qui contient les identifiants des matchs du joueur.

    matches = matches.json()      #Stocke les données JSON de la réponse dans une variable pour un traitement ultérieur.

    match_id = matches[0]      #Extrait le premier identifiant de match de la liste des identifiants de matchs obtenus et le stocke dans une variable.
        #print("Match ID:", match_id)

    rapport_url =(f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={api_key}")

    rapport = requests.get(rapport_url)      #Crée une requête GET à l'URL spécifiée pour obtenir les détails du match identifié par l'ID de match.
        #print(rapport.json())      #Affiche la réponse de l'API au format JSON, qui contient les détails du match.

    rapport = rapport.json()      #Stocke les données JSON de la réponse dans une variable pour un traitement ultérieur.

    for participant in rapport["info"]["participants"]:
        if participant["puuid"] == puuid:
            pseudo = participant["summonerName"]
            kills = participant["kills"]
            deaths = participant["deaths"]
            assists = participant["assists"]
            champion = participant["championName"]
            game_time = rapport["info"]["gameDuration"]
            minutes = game_time // 60  #Convertir la durée du jeu en minutes
            seconds = game_time % 60   #Obtenir les secondes restantes
            game_time = f"{minutes}:{seconds:02d}" #Formater la durée du jeu en minutes:secondes
            vision = participant["visionScore"]
            cs = participant["totalMinionsKilled"] + participant["neutralMinionsKilled"]
            cs_per_minute = cs / (rapport["info"]["gameDuration"] / 60)
            win = participant["win"]
            if win:
                couleur_embed = discord.Color.green() #Définir la couleur de l'embed Discord en vert pour une victoire
                titre_embed = "Victory" #Définir le titre de l'embed Discord pour une victoire
            else:
                couleur_embed = discord.Color.red()
                titre_embed = "Defeat"
            
            embed = discord.Embed(title = titre_embed, color = couleur_embed) #Créer un embed Discord avec le titre et la couleur appropriés en fonction du résultat du match.

            embed.add_field(name="Player", value=game_name, inline=True)
            embed.add_field(name="Champion", value=champion, inline=True)
            embed.add_field(name="K/D/A", value=f"{kills}/{deaths}/{assists}", inline=True)
            embed.add_field(name="CS", value=f"{cs} ({cs_per_minute:.1f})" , inline=True)
            embed.add_field(name="Vision Score", value=vision, inline=True)
            embed.add_field(name="Game Duration", value=game_time, inline=True)
            embed.add_field(name="Rank", value=f"{tier} {division} - {lp} LP", inline=True)
            embed.add_field(name="Win Rate", value=f"{win_rate:.2f}% ({wins}W/{losses}L)", inline=True)
            break
    return match_id, embed
# Parcourt la liste des participants dans les informations du match pour trouver le joueur correspondant au PUUID.
# Une fois trouvé, il extrait et affiche les statistiques de kills, deaths et assists du joueur ainsi que le champion joué et la durée de la partie en minutes.


@tasks.loop(minutes=2)
async def background_task():

    global last_match_id  # Indique que nous utilisons la variable globale last_match_id, ça évite les erreurs de portée de variable.
    channel = client.get_channel(1458558905016910041) #Ici on récupère l'ID du channel où le bot enverra les messages.
    new_match_id, new_embed = fetch_lol_stats("NK7", "9665") #Appelle la fonction fetch_lol_stats pour obtenir les statistiques de jeu. 
    
    
    if last_match_id is None or last_match_id != new_match_id:  #Vérifie si le dernier ID de match est différent du nouvel ID de match récupéré.
        await channel.send(embed = new_embed) #Envoie le message avec les statistiques dans le channel spécifié
        last_match_id = new_match_id  # Met à jour l'ID du dernier match traité
        with open("last_match.txt", "w") as f:  #Ouvre (ou crée) un fichier texte nommé "last_match.txt" en mode écriture.
            f.write(str(new_match_id))  #Écrit l'ID du dernier match traité dans le fichier texte pour une persistance des données.



@client.event
async def on_ready():
    print("Bot connecté")
    background_task.start()  #Démarre la tâche en arrière-plan lorsque le bot est prêt.


client.run(os.getenv("DISCORD_TOKEN"))  #Récupère le token Discord à partir des variables d'environnement pour authentifier le bot Discord dans le fichier env 

#Démarre le bot Discord en utilisant le token spécifié pour se connecter à l'API Discord.