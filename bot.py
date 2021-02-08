# bot.py
# Written by Matthew Circelli
# Ver: 1.4 - Switched to readfile instead of getenv
# Date: 2/7/2021
# Desc: Bot that will hopefully track FC stock levels on pings
# TODO: Show only demand when on a loading mission, vice-versa
# TODO: deleteFC command or edit FC command
# Refs: Discord.py API: https://discordpy.readthedocs.io/en/latest/api.html#
# Dev portal: https://discord.com/developers/applications/803357001765617705/bot
# EDSM stations API: https://www.edsm.net/en/api-system-v1

import os
import discord
import re
import requests
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('TEST_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix=';', intents=intents)


@bot.event
async def on_ready() :
    guild = discord.utils.get(bot.guilds, name = GUILD) #bot.guilds is a list of all connected servers

    print(
        f'{bot.user.name} is connected to \n'
        f'{guild.name} (id: {guild.id})'
    )


#@bot.event
# on_member_join triggers when a new user joins the server
#async def on_member_join(member):
#    print(f'{member.name} joined!')
#    await member.send(
#        f'Hi {member.name}, welcome to P.T.N!\n\n'
#    )
#    print(f'Welcome Message Sent!')


@bot.command(name='ping', help='If the bot hasnt crashed, it will respond >pong<')
async def dingle(ctx):
    await ctx.send('pong!')
    r = requests.get('https://www.edsm.net/api-system-v1/stations/market')
    if r:
        await ctx.send('EDSM pongs as well! Everything should work great :)')
    else:
        await ctx.send('EDSM does not pong! Stock tracking will not function :(')


@bot.command(name='add_FC', help='Add a fleet carrier for stock tracking.\n'
                                 'FCCode: Carrier ID Code \n'
                                 'FCSys: Carrier current system \n'
                                 'FCName: The alias with which you want to refer to the carrier. Please use something '
                                 'simple like "orion" or "9oclock", as this is what you use to call the stock command!'
                                 '\n!!SYSTEMS WITH SPACES IN THE NAMES NEED TO BE "QUOTED LIKE THIS"!! ')
@commands.has_any_role('Carrier Owner','Bot Handler')
async def addFC(ctx, FCCode, FCSys, FCName):
    fcfile = open(".env")
    envlist = fcfile.readlines()
    fcfile.close()

    # Checking if FC is already in the list, and if FC name is in correct format
    # Stops if FC is already in list, or if incorrect name format
    matched = re.match("[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]-[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]", FCCode)
    isnt_match = not bool(matched)  # If it is NOT a match, we enter the Invalid FC Code condition

    if FCCode in envlist[3]:
        await ctx.send(f'{FCCode} is a code that is already in the Carrier list!')
        return
    elif FCName in envlist[4]:
        await ctx.send(f'{FCName} is an alias that is already in the alias list!')
        return
    elif isnt_match:
        await ctx.send(f'Invalid Fleet Carrier Code format! Format should look like XXX-YYY')
        return

    print(f'Format is good... Checking database...')

    pmeters = {'systemName': FCSys, 'stationName': FCCode}
    r = requests.get('https://www.edsm.net/api-system-v1/stations/market', params=pmeters)

    mid = r.json()

    if r.text=='{}':
        await ctx.send(f'FC does not exist in the EDSM database, check to make sure the inputs are correct!')
        return
    else:
        await ctx.send(f'This FC is NOT a lie!')

    print(mid['marketId'])
    midstr = str(mid['marketId'])

    envlist[3] = envlist[3].strip('\n')
    fcput = envlist[3] + '.' + FCCode + '\n'
    envlist[3] = fcput

    envlist[4] = envlist[4].strip('\n')
    aliasput = envlist[4] + '.' + FCName.lower() + '\n'
    envlist[4] = aliasput

    midput = envlist[5] + '.' + midstr + '\n'
    envlist[5] = midput

    print(envlist)

    fcfile = open(".env", "w")
    fcwrite = "".join(envlist)

    fcfile.write(fcwrite)
    fcfile.close()

    await ctx.send(f'Added {FCCode} to the FC list, under reference name {FCName}')


@bot.command(name='APItest', help='Test EDSM API')
@commands.has_role('Bot Handler')
async def APITest(ctx, mark):
    await ctx.send('Testing API with given marketId')
    pmeters = {'marketId': mark}
    r = requests.get('https://www.edsm.net/api-system-v1/stations/market',params=pmeters)
    stn_data = r.json()

    com_data = stn_data['commodities']
    loc_data = stn_data['name']
    if com_data == []:
        await ctx.send(f"{stn_data['sName']} is empty!")
        return

    name_data = ["" for x in range(len(com_data))]
    stock_data = ["" for x in range(len(com_data))]
    dem_data = ["" for x in range(len(com_data))]

    for i in range(len(com_data)):
        name_data[i] = com_data[i]['name']
        stock_data[i] = com_data[i]['stock']
        dem_data[i] = com_data[i]['demand']

    print('Creating embed...')
    embed = discord.Embed(title=f"{stn_data['sName']} stock")
    embed.add_field(name = 'Commodity', value = name_data, inline = True)
    embed.add_field(name = 'Amount', value = stock_data, inline = True)
    embed.add_field(name = 'FC Location', value = loc_data, inline= True)
    print('Embed created!')
    print(name_data)

    await ctx.send(embed=embed)
    print('Embed sent!')


@bot.command(name='stock', help='Returns stock and location of a PTN carrier (carrier needs to be added first)')
async def stock(ctx, fcname):
    fcfile = open(".env")
    envlist = fcfile.readlines()
    fcfile.close()

    names = envlist[4].lower()
    names = names.strip('\n')
    fcname = fcname.lower()

    # this if statement is problematic... might be worth revisiting later
    if fcname not in names:
        await ctx.send('The requested carrier is not in the list! Add carriers using the add_FC command!')

    namelist = names.split('.')
    envlist[5] = envlist[5].strip('\n')
    midlist = envlist[5].split('.')
    ind = namelist.index(fcname)
    mid = midlist[ind]

    await ctx.send(f'Fetching stock levels for {fcname}')
    pmeters = {'marketId': mid}
    r = requests.get('https://www.edsm.net/api-system-v1/stations/market',params=pmeters)
    stn_data = r.json()

    com_data = stn_data['commodities']
    loc_data = stn_data['name']
    if com_data == []:
        await ctx.send(f"{fcname} has no active mission")
        return

    name_data = ["" for x in range(len(com_data))]
    stock_data = ["" for x in range(len(com_data))]
    dem_data = ["" for x in range(len(com_data))]

    for i in range(len(com_data)):
        name_data[i] = com_data[i]['name']
        stock_data[i] = com_data[i]['stock']
        dem_data[i] = com_data[i]['demand']

    print('Creating embed...')
    embed = discord.Embed(title=f"{fcname} ({stn_data['sName']}) stock")
    embed.add_field(name = 'Commodity', value = name_data, inline = True)
    embed.add_field(name = 'Amount', value = stock_data, inline = True)
    # FIXME : Find a way to display demand only if stock is 0 (auto-determine loading mission)
    # EDSM API cargo tracking is too inconsistent to use for loading missions
    embed.add_field(name = 'Demand', value = dem_data, inline= True)
    embed.add_field(name = 'FC Location', value = loc_data, inline= True)
    embed.set_footer(text='Numbers out of wack? Ensure EDMC is running!')
    print('Embed created!')

    await ctx.send(embed=embed)
    print('Embed sent!')


@bot.command(name='list', help='Lists all tracked carriers')
async def fclist(ctx):
    fcfile = open(".env")
    envlist = fcfile.readlines()
    fcfile.close()

    names = envlist[4].lower()
    names = names.strip('\n')
    namelist = names.split('.')
    namelist.remove('')
    print('Listing active carriers')
    embed = discord.Embed(title='Tracked carriers')
    embed.add_field(name = 'Carrier Names', value = namelist)
    print('Sent!')

    await ctx.send(embed=embed)


@bot.event
async def on_error(event, *args, **kwargs):
    with open('err.log','a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.errors.CheckFailure):
        await ctx.send('You do not have the correct role for this command.')

bot.run(TOKEN)

