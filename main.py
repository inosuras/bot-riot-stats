from keep_alive import keep_alive
from discord.ext import tasks
from discord.ext import commands
import requests
import discord
import json
import os
from urllib.parse import quote # <--- NOUVEAU : Pour gérer les espaces dans les URL

from dotenv import load_dotenv
load_dotenv()  # Charge les variables d'environnement à partir du fichier .env

intents = discord.Intents.default()  # Activation des intents par défaut
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def fetch_lol_stats(game_name, tag_line):  # Fonction pour récupérer les stats d'un joueur
    api_key = os.getenv("RIOT_API_KEY")
    
    # --- CORRECTION URL ---
    # On encode le pseudo pour l'URL (Espace devient %20)
    game_name_url = quote(game_name)
    url = (f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name_url}/{tag_line}?api_key={api_key}")
    # ----------------------

    response = requests.get(url)
    account_data = response.json()
    puuid = account_data.get("puuid")

    rank_url = (f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={api_key}")
    rank = requests.get(rank_url)
    rank = rank.json()  # Conversion en JSON et stockage dans une variable

# Initialisation des variables de rang par défaut

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
            break
    
    matches_url = (f"https://europe.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1&api_key={api_key}")
    matches = requests.get(matches_url)
    matches = matches.json()

    match_id = matches[0]

    rapport_url = (f"https://europe.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={api_key}")
    rapport = requests.get(rapport_url)
    rapport = rapport.json()

    embed = None # Initialisation par sécurité

    for participant in rapport["info"]["participants"]:  # Parcours des participants pour trouver le joueur demandé et récupérer ses stats

        if participant["puuid"] == puuid:
            pseudo = participant["summonerName"]
            kills = participant["kills"]
            deaths = participant["deaths"]
            assists = participant["assists"]
            champion = participant["championName"]
            game_time = rapport["info"]["gameDuration"]
            minutes = game_time // 60
            seconds = game_time % 60
            game_time = f"{minutes}:{seconds:02d}"
            vision = participant["visionScore"]
            cs = participant["totalMinionsKilled"] + participant["neutralMinionsKilled"]
            
            # Sécurité pour éviter la division par zéro si la game dure 0s (remake instantané)
            duration_minutes = rapport["info"]["gameDuration"] / 60
            cs_per_minute = cs / duration_minutes if duration_minutes > 0 else 0

            win = participant["win"]
            if win:
                couleur_embed = discord.Color.green()
                titre_embed = "Victory"
            else:
                couleur_embed = discord.Color.red()
                titre_embed = "Defeat"
            
            embed = discord.Embed(title=titre_embed, color=couleur_embed)
            embed.add_field(name="Player", value=game_name, inline=True)
            embed.add_field(name="Champion", value=champion, inline=True)
            embed.add_field(name="K/D/A", value=f"{kills}/{deaths}/{assists}", inline=True)
            embed.add_field(name="CS", value=f"{cs} ({cs_per_minute:.1f})", inline=True)
            embed.add_field(name="Vision Score", value=vision, inline=True)
            embed.add_field(name="Game Duration", value=game_time, inline=True)
            embed.add_field(name="Rank", value=f"{tier} {division} - {lp} LP", inline=True)
            embed.add_field(name="Win Rate", value=f"{win_rate:.2f}% ({wins}W/{losses}L)", inline=True)
            break
            
    return match_id, embed  # Retourne l'ID du match et l'embed


@tasks.loop(minutes=2)
async def background_task():
    try:  
        with open("tracked_players.json", "r") as f:
            tracked_players = json.load(f)
    except FileNotFoundError:
        tracked_players = []
    
    try:
        channel_id = int(os.getenv("CHANNEL_DISCORD"))
        channel = bot.get_channel(channel_id)
    except (TypeError, ValueError):
        print("Erreur : CHANNEL_DISCORD n'est pas défini ou n'est pas un nombre valide dans le .env")
        return

    for player in tracked_players:
        # --- CORRECTION BOUCLE ---
        # Ajout du try/except pour qu'une erreur sur un joueur ne stoppe pas tout le bot
        try:
            new_match_id, new_embed = fetch_lol_stats(player["game_name"], player["tag_line"])
            
            if new_match_id != player["last_match_id"]:
                player["last_match_id"] = new_match_id
                
                with open("tracked_players.json", "w") as f:
                    json.dump(tracked_players, f)
                
                if channel:
                    await channel.send(embed=new_embed)
                    
        except Exception as e:
            print(f"Erreur lors du tracking de {player['game_name']} : {e}")
            continue # Passe au joueur suivant malgré l'erreur
        # -------------------------


@bot.command(name="rank")
async def rank(ctx, *, riot_id: str):  # Commande pour récupérer le rang d'un joueur, le * permet de prendre en compte les espaces dans le pseudo
    try:
        game_name, tag_line = riot_id.split("#")
        api_key = os.getenv("RIOT_API_KEY")
        
        # --- CORRECTION URL ---
        game_name_url = quote(game_name)
        url = (f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name_url}/{tag_line}?api_key={api_key}")
        # ----------------------
        
        response = requests.get(url)
        if response.status_code == 200:
            account_data = response.json()
            puuid = account_data.get("puuid")
            rank_url = (f"https://euw1.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}?api_key={api_key}")
            rank_data = requests.get(rank_url).json()
            
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
            await ctx.send(f"{game_name}#{tag_line} {tier} {division} - {lp} LP | {win_rate:.1f}% ({wins}W/{losses}L)")
        else:
            await ctx.send("Riot ID non trouvé.")
            
    except ValueError:
        await ctx.send("Eh non, la commande s'écrit avec le tag : Pseudo#Tag")


@bot.command(name="track")
async def track(ctx, *, riot_id: str):
    try:
        game_name, tag_line = riot_id.split("#")

        try:
            with open("tracked_players.json", "r") as f:
                tracked_players = json.load(f)
        except FileNotFoundError:
            tracked_players = []

        # Vérification doublon
        for player in tracked_players:
            if player["game_name"] == game_name and player["tag_line"] == tag_line:
                await ctx.send(f"Le suivi de {game_name}#{tag_line} est déjà en cours.")
                return

        api_key = os.getenv("RIOT_API_KEY")
        
        # --- CORRECTION URL ---
        game_name_url = quote(game_name)
        url = (f"https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name_url}/{tag_line}?api_key={api_key}")
        # ----------------------
        
        response = requests.get(url)
        
        if response.status_code == 200:
            account_data = response.json()
            puuid = account_data.get("puuid")

            # On récupère le dernier match pour initialiser le tracking
            last_match_id, last_embed = fetch_lol_stats(game_name, tag_line)

            player_data = {
                "puuid": puuid,
                "game_name": game_name, # On garde le nom original (avec espace) pour l'affichage
                "tag_line": tag_line,
                "last_match_id": last_match_id
            }
            
            # --- CORRECTION INDENTATION ---
            # Ces lignes ne s'exécutent QUE si response.status_code == 200
            tracked_players.append(player_data)
            with open("tracked_players.json", "w") as f:
                json.dump(tracked_players, f)
                await ctx.send(f"Le suivi de {game_name}#{tag_line} a été ajouté.")
            # ------------------------------
            
        else:
            await ctx.send("Riot ID non trouvé (Vérifiez l'orthographe ou le tag).")
            
    except ValueError:
        await ctx.send("Eh non, la commande s'écrit avec le tag : Pseudo#Tag")


@bot.event
async def on_ready():
    print("Bot connecté")
    background_task.start()

keep_alive()  # Démarre le serveur Flask pour garder le bot en vie
bot.run(os.getenv("DISCORD_TOKEN"))