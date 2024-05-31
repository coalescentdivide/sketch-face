import asyncio
import io
import os
import random
import re
import sqlite3
from pathlib import Path

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

import replicate

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
USER_DB = 'user_credits.db'
queue_count = 0
bot = commands.Bot(command_prefix='!', intents=discord.Intents.all())
default_negative_prompt = os.getenv("DEFAULT_NEGATIVE_PROMPT")

def init_db():
    with sqlite3.connect(USER_DB) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS credits (
                user_id INTEGER PRIMARY KEY,
                credits INTEGER NOT NULL
            )
        ''')
        conn.commit()

init_db()


def get_random_line(file_path):
    with open(file_path, mode="r", encoding="utf-8") as file:
        lines = file.readlines()
        return random.choice(lines).strip()


def replace_wildcards(prompt):
    wildcard_folder = Path(__file__).parent / "wildcards"
    placeholders = re.findall(r"\{(\w+)\}", prompt)
    for placeholder in placeholders:
        filename = wildcard_folder / f"{placeholder}.txt"
        if filename.exists():
            replacement = get_random_line(filename)
            prompt = prompt.replace(f"{{{placeholder}}}", replacement)
        else:
            print(f"Warning: Placeholder file {filename} not found.")
    return prompt


def get_user_credits(user_id):
    with sqlite3.connect(USER_DB) as conn:
        c = conn.cursor()
        c.execute('SELECT credits FROM credits WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if result:
            return result[0]
        else:
            initial_credits = 100  # Initial credits for new users
            c.execute('INSERT INTO credits (user_id, credits) VALUES (?, ?)', (user_id, initial_credits))
            conn.commit()
            return initial_credits


def deduct_credits(user_id, amount):
    with sqlite3.connect(USER_DB) as conn:
        c = conn.cursor()
        current_credits = get_user_credits(user_id)
        updated_credits = max(current_credits - amount, 0)
        c.execute('UPDATE credits SET credits = ? WHERE user_id = ?', (updated_credits, user_id))
        conn.commit()


def add_credits(user_id, amount):
    with sqlite3.connect(USER_DB) as conn:
        c = conn.cursor()
        current_credits = get_user_credits(user_id)
        updated_credits = current_credits + amount
        c.execute('UPDATE credits SET credits = ? WHERE user_id = ?', (updated_credits, user_id))
        conn.commit()


async def download_image(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()


async def generate(input_data_list):
    global queue_count
    model = await replicate.models.async_get("zsxkib/pulid")
    version = await model.versions.async_get("c169c3b8f6952cf895d043d7b56830b4e9a3e9409a026004e9efbd9da42912b4")
    tasks = []
    results = []
    cost_per_second = 0.000725
    credits_per_dollar = 1 / 0.005
    credits_per_second = cost_per_second * credits_per_dollar  # Conversion rate from dollars to credits

    for input_data in input_data_list:
        prediction = await replicate.predictions.async_create(version, input=input_data)
        tasks.append(prediction)

    queue_count += len(tasks)

    for prediction in tasks:
        await prediction.async_wait()
        await prediction.async_reload()  # Ensure metadata is up-to-date

        prediction = await replicate.predictions.async_get(prediction.id)  # Refreshing prediction must be async_get

        if prediction.status == "succeeded":
            predict_time = prediction.metrics['predict_time']
            cost_in_credits = max(1, int(predict_time * credits_per_second))  # Ensure at least 1 credit is charged
            results.append((prediction.output, cost_in_credits, predict_time))

            print(f"Prediction {prediction.id} took {predict_time:.2f} seconds, cost: {cost_in_credits} credits")

        queue_count -= 1
        print(f"Generation completed, remaining in queue: {queue_count}")

    return results


@bot.command()
async def sketch(ctx, *, args):
    author = ctx.author if hasattr(ctx, 'author') else ctx.message.author
    user_id = author.id

    pattern = re.compile(r"--(\w+)(?:\s+([^--]+))?")
    matches = pattern.findall(args)
    options = {flag: value.strip() if value else None for flag, value in matches}
    
    seed = random.randint(1, 999999999)
    scale = 1.2
    max_generations = 4

    if 'seed' in options:
        seed = int(options['seed']) if options['seed'].isdigit() and int(options['seed']) > 0 else seed
    if 'scale' in options:
        scale = float(options['scale']) if options['scale'].replace('.', '', 1).isdigit() and float(options['scale']) > 0 else scale
    if 'no' in options:
        if options['no']:
            negative_prompt = options['no']
    else:
        negative_prompt = default_negative_prompt
    if 'n' in options:
        num_generations = min(max(int(options['n']), 1), max_generations) if options['n'].isdigit() else max_generations
    else:
        num_generations = 1

    prompt = re.sub(r"(?:--\w+\s+[^--]+|--\w+)", "", args).strip()

    if 'no' in options and options['no']:
        no_terms = options['no'].split(',')
        for term in no_terms:
            prompt = prompt.replace(term.strip(), "").strip()

    prompt = replace_wildcards(prompt)
    current_credits = get_user_credits(user_id)
    min_required_credits = 1
    
    if current_credits < min_required_credits:
        await ctx.send(f"You do not have enough credits to perform this operation. Your current balance is {current_credits} credits.")
        return
    
    attachments = ctx.message.attachments + (await ctx.fetch_message(ctx.message.reference.message_id)).attachments if ctx.message.reference else ctx.message.attachments
    if not attachments:
        await ctx.send("Please attach at least one image for the main face.")
        return

    attachment_urls = [att.url for att in attachments] + [None] * (4 - len(attachments))

    current_seed = seed

    tasks = []
    for i in range(num_generations):
        input_data = {
            "main_face_image": attachment_urls[0],
            "num_samples": 1, # we set this to 1 and iterate on the client side to control the seed
            "seed": current_seed,
            "prompt": prompt,
            "cfg_scale": scale,
            "negative_prompt": negative_prompt,
        }
        if len(attachments) > 1 and attachment_urls[1]: 
            input_data["auxiliary_face_image1"] = attachment_urls[1]
        if len(attachments) > 2 and attachment_urls[2]: 
            input_data["auxiliary_face_image2"] = attachment_urls[2]
        if len(attachments) > 3 and attachment_urls[3]: 
            input_data["auxiliary_face_image3"] = attachment_urls[3]

        tasks.append(generate([input_data]))

        current_seed += 1

    print(f"Generations Queued: {num_generations}")

    all_results = await asyncio.gather(*tasks)
    for idx, results in enumerate(all_results):
        if results is None:
            continue
        for output, cost_in_credits, predict_time in results:
            deduct_credits(user_id, cost_in_credits)
            current_credits -= cost_in_credits

            seed_info = f"🌱`{seed + idx}`"

            for image_idx, image_url in enumerate(output):
                image_data = await download_image(image_url)
                file = discord.File(fp=io.BytesIO(image_data), filename=f"image_{idx}_{image_idx}.webp")
                embed = discord.Embed(description=prompt, color=discord.Color.blue())
                
                scale_info = f"⚖️`{1.2}`"
                balance = f"🪙{cost_in_credits}/{current_credits}"
                info = f"🧠{author.mention} {seed_info} {scale_info} {balance}"

                await ctx.send(content=info, file=file, embed=embed)
                
                print(f"Generation Complete: {file.filename}, Cost: {cost_in_credits} credits, Predict Time: {predict_time:.2f}s. Remaining Credits: {current_credits}")


@bot.command()
async def balance(ctx):
    user_id = ctx.author.id
    credits = get_user_credits(user_id)
    await ctx.send(f"You currently have {credits} credits.")


@bot.command()
async def credit(ctx, amount: int, user: discord.User):
    if ctx.author.id != ADMIN_ID:
        await ctx.send("You do not have permission to use this command.")
        return

    if amount <= 0:
        await ctx.send("The amount of credits to add must be a positive number.")
        return

    user_id = user.id
    add_credits(user_id, amount)

    updated_credits = get_user_credits(user_id)
    await ctx.send(f"Added {amount} to {user.mention} for a total balance of {updated_credits} credits.")


@bot.command()
async def gift(ctx, amount: int, user: discord.User):
    sender_id = ctx.author.id
    recipient_id = user.id

    if amount <= 0:
        await ctx.send("The amount of credits to gift must be a positive number.")
        return

    sender_credits = get_user_credits(sender_id)
    if sender_credits < amount:
        await ctx.send(f"You do not have enough credits to gift. Your current balance is {sender_credits} credits.")
        return

    deduct_credits(sender_id, amount)
    add_credits(recipient_id, amount)

    await ctx.send(f"You have successfully gifted {amount} credits to {user.mention}. Your new balance is {get_user_credits(sender_id)} credits.")
    await user.send(f"You have received {amount} credits from {ctx.author.mention}. Your new balance is {get_user_credits(recipient_id)} credits.")


bot.run(DISCORD_TOKEN)
