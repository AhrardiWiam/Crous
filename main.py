import json
import os
from datetime import datetime

import discord
import requests
from bs4 import BeautifulSoup
from discord.ext import tasks, commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=">", intents=intents)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TASKS_FILE = "tasks.json"

prev_results = {}
started_tasks = {}

# ----------- PERSISTANCE : lire & sauvegarder les tâches ----------- #
def load_tasks_from_file():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_tasks_to_file(tasks_dict):
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks_dict, f)

# ----------- FONCTION SCRAP ----------- #
async def scrap(ctx, url):
    current_time = datetime.now().strftime("%H:%M")
    response = requests.get(url)

    if response.status_code != 200:
        print(f"[{current_time}] Erreur de téléchargement.")
        embed = discord.Embed(title="Erreur de téléchargement de la page.", color=0xc20000)
        await ctx.author.send(embed=embed)
        return

    soup = BeautifulSoup(response.text, "html.parser")
    elements = soup.find_all("div", class_="fr-card svelte-12dfls6")
    names = {element.find("a").text for element in elements}

    if not names:
        print(f"[{current_time}] Aucun logement trouvé.")
        prev_results[ctx.author.id] = names
        return

    new_names = names - prev_results.get(ctx.author.id, set())
    if not new_names:
        print(f"[{current_time}] Aucun nouveau logement.")
        return

    prev_results[ctx.author.id] = names
    print(f"[{current_time}] Logement.s trouvé.s ({len(new_names)}):\n-" + "\n-".join(new_names))
    embed = discord.Embed(
        title=f"Logement.s trouvé.s ({len(new_names)}):",
        description="-" + "\n-".join(new_names),
        color=0x0f8000
    )
    await ctx.author.send(embed=embed)

# ----------- COMMANDE START ----------- #
@bot.command(name="start")
async def start(ctx, arg: str = None):
    if ctx.author.id in started_tasks:
        embed = discord.Embed(title="Recherche déjà en cours.", color=0xc20000)
        await ctx.channel.send(embed=embed)
        return

    if not arg:
        embed = discord.Embed(title="Aucune URL fournie.", color=0xc20000)
        await ctx.channel.send(embed=embed)
        return

    @tasks.loop(minutes=1)
    async def scrap_loop(context, url_):
        await scrap(context, url_)

    scrap_loop.start(ctx, arg)
    started_tasks[ctx.author.id] = scrap_loop
    prev_results[ctx.author.id] = set()

    # Sauvegarde dans le fichier
    tasks_data = load_tasks_from_file()
    tasks_data[str(ctx.author.id)] = arg
    save_tasks_to_file(tasks_data)

    print(f"[{datetime.now().strftime('%H:%M')}] Recherche commencée.")
    embed = discord.Embed(title="Recherche commencée.", color=0x0f8000)
    await ctx.channel.send(embed=embed)

# ----------- COMMANDE STOP ----------- #
@bot.command(name="stop")
async def stop(ctx):
    uid = ctx.author.id
    if uid not in started_tasks:
        embed = discord.Embed(title="Aucune recherche en cours.", color=0xc20000)
        await ctx.channel.send(embed=embed)
        return

    started_tasks[uid].cancel()
    del started_tasks[uid]
    del prev_results[uid]

    # Retirer du fichier
    tasks_data = load_tasks_from_file()
    tasks_data.pop(str(uid), None)
    save_tasks_to_file(tasks_data)

    print(f"[{datetime.now().strftime('%H:%M')}] Recherche arrêtée.")
    embed = discord.Embed(title="Recherche arrêtée.", color=0xc20000)
    await ctx.channel.send(embed=embed)

# ----------- AU DÉMARRAGE ----------- #
@bot.event
async def on_ready():
    print(f"[{datetime.now().strftime('%H:%M')}] Bot en ligne.")

    tasks_data = load_tasks_from_file()
    for uid_str, url in tasks_data.items():
        uid = int(uid_str)
        user = await bot.fetch_user(uid)

        @tasks.loop(minutes=1)
        async def scrap_loop(context, url_):
            await scrap(context, url_)

        # Démarrer la boucle
        scrap_loop.start(user, url)
        started_tasks[uid] = scrap_loop
        prev_results[uid] = set()

        print(f"[{datetime.now().strftime('%H:%M')}] Reprise de la surveillance pour {user}.")

# ----------- LANCEMENT DU BOT ----------- #
bot.run(BOT_TOKEN)
