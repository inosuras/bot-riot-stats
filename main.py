from keep_alive import keep_alive
from discord.ext import tasks
from discord.ext import commands
import requests
import discord
import json

import os
from dotenv import load_dotenv
load_dotenv()  # Charge les variables d'environnement à partir du fichier .env


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)  #Crée une instance de bot Discord avec le préfixe de commande "!" et les intentions spécifiées.

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
    # Étape 1 : On ouvre le carnet d'adresses (le fichier JSON)
    try:
        with open("tracked_players.json", "r") as f:
            tracked_players = json.load(f)
    except FileNotFoundError:
        tracked_players = [] # Si le fichier n'existe pas encore
    
    # On définit le channel où envoyer les alertes
    channel = bot.get_channel(1458558905016910041)

    # Étape 2 : On passe en revue chaque joueur de la liste
    for player in tracked_players:
        
        # On interroge l'API pour ce joueur précis
        new_match_id, new_embed = fetch_lol_stats(player["game_name"], player["tag_line"])
        
        # Étape 3 : Le moment de vérité (Comparaison)
        if new_match_id != player["last_match_id"]:
            
            # C'est un nouveau match ! On met à jour le carnet d'adresses (mémoire vive)
            player["last_match_id"] = new_match_id
            
            # Étape 4 : ... et on sauvegarde immédiatement dans le fichier (mémoire dure)
            with open("tracked_players.json", "w") as f:
                json.dump(tracked_players, f)
            
            # Étape 5 : On prévient tout le monde sur Discord
            if channel:
                await channel.send(embed=new_embed)


@bot.command(name="rank")
async def rank(ctx, riot_id):
    # Commande Discord pour obtenir le rang d'un joueur en utilisant son Riot ID.
    try:
        game_name, tag_line = riot_id.split("#")  #Divise le Riot ID en nom de jeu et ligne de tag.
        api_key = os.getenv("RIOT_API_KEY")  #Récupère la clé API Riot Games à partir des variables d'environnement pour authentifier les requêtes API dans le fichier .env.
        url =(f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={api_key}")
        response = requests.get(url)      #Créee une requête GET à l'URL spécifiée c'est-à-dire l'API de Riot Games pour obtenir des informations sur un compte Riot ID.
        if response.status_code == 200:
            account_data = response.json()      #Stocke les données JSON de la réponse dans une variable pour un traitement ultérieur.
            puuid = account_data.get("puuid")    #Extrait la valeur associée à la clé "puuid" des données du compte et la stocke dans une variable.
            rank_url =(f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={api_key}")
            rank_data = requests.get(rank_url)      #Crée une requête GET à l'URL spécifiée pour obtenir les informations de classement du joueur identifié par le PUUID.      
            rank_data = rank_data.json()      #Stocke les données JSON de la réponse dans une variable pour un traitement ultérieur.
            tier = "Unranked"
            division = ""
            lp = 0
            wins = 0
            losses = 0
            win_rate = 0
            for entry in rank_data:
                if entry["queueType"] == "RANKED_SOLO_5x5":
                    tier = entry["tier"]
                    division = entry["rank"]
                    lp = entry["leaguePoints"]
                    wins = entry["wins"]
                    losses = entry["losses"]
                    win_rate = (wins / (wins + losses)) * 100
                    break
            await ctx.send(f"{game_name}#{tag_line} {tier} {division} - {lp} LP | {win_rate:.1f}% ({wins}W/{losses}L)")  #Envoie un message avec le rang du joueur dans le channel où la commande a été utilisée.
        else:
            await ctx.send("Riot ID non trouvé.")  #Envoie un message d'erreur si le Riot ID n'est pas trouvé.
            
    except ValueError:
        await ctx.send("Eh non, la commande s'écrit avec le tag : Pseudo#Tag") #Envoie un message d'erreur si le format du Riot ID est incorrect. ctx.send permet d'envoyer un message dans le channel où la commande a été utilisée.

    
@bot.command(name="track")
async def track(ctx, riot_id):
    # Commande Discord pour obtenir le rang d'un joueur en utilisant son Riot ID.
    try:
        game_name, tag_line = riot_id.split("#")  #Divise le Riot ID en nom de jeu et ligne de tag.

        try:
            with open("tracked_players.json", "r") as f:
                    tracked_players = json.load(f)  # Charge les joueurs suivis existants depuis le fichier JSON
        except FileNotFoundError:
                tracked_players = []  # Si le fichier n'existe pas, initialise une liste vide

        for player in tracked_players:
            if player["game_name"] == game_name and player["tag_line"] == tag_line:
                await ctx.send(f"Le suivi de {game_name}#{tag_line} est déjà en cours.")  #Envoie un message si le joueur est déjà suivi.
                return  #Sort de la fonction pour éviter d'ajouter le joueur en double grâce à return.


        api_key = os.getenv("RIOT_API_KEY")  #Récupère la clé API Riot Games à partir des variables d'environnement pour authentifier les requêtes API dans le fichier .env.
        url =(f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}?api_key={api_key}")
        response = requests.get(url)      #Créee une requête GET à l'URL spécifiée c'est-à-dire l'API de Riot Games pour obtenir des informations sur un compte Riot ID.
        if response.status_code == 200:
            account_data = response.json()      #Stocke les données JSON de la réponse dans une variable pour un traitement ultérieur.
            puuid = account_data.get("puuid")    #Extrait la valeur associée à la clé "puuid" des données du compte et la stocke dans une variable.

            last_match_id, last_embed = fetch_lol_stats(game_name, tag_line) #Appelle la fonction fetch_lol_stats pour obtenir les statistiques de jeu.

            player_data = {
                "puuid": puuid,
                "game_name": game_name,
                "tag_line": tag_line,
                "last_match_id": last_match_id
            }
                     
                    
            tracked_players.append(player_data)  # Ajoute le nouveau joueur à la liste des joueurs suivis
            with open("tracked_players.json", "w") as f:               

                json.dump(tracked_players, f)  # Enregistre la liste mise à jour dans le fichier JSON
                await ctx.send(f"Le suivi de {game_name}#{tag_line} a été ajouté.")  #Envoie un message confirmant que le suivi a été ajouté dans le channel où la commande a été utilisée.
        else:
            await ctx.send("Riot ID non trouvé.")  #Envoie un message d'erreur si le Riot ID n'est pas trouvé.
    except ValueError:
        await ctx.send("Eh non, la commande s'écrit avec le tag : Pseudo#Tag") #Envoie un message d'erreur si le format du Riot ID est incorrect. ctx.send permet d'envoyer un message dans le channel où la commande a été utilisée.
    


@bot.event
async def on_ready():
    print("Bot connecté")
    background_task.start()  #Démarre la tâche en arrière-plan lorsque le bot est prêt.

keep_alive()  #Démarre le serveur Flask pour maintenir le bot en ligne.
bot.run(os.getenv("DISCORD_TOKEN"))  #Récupère le token Discord à partir des variables d'environnement pour authentifier le bot Discord dans le fichier env 

#Démarre le bot Discord en utilisant le token spécifié pour se connecter à l'API Discord.