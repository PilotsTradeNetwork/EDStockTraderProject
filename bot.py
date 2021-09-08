# bot.py
# Written by Matthew Circelli
# Ver: 1.4 - Cleaner embeds!
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
import json
from dotenv import find_dotenv, load_dotenv, set_key
from discord.ext import commands

carrierdb = '.carriers'
load_dotenv()
load_dotenv(carrierdb)
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
CARRIERS = os.getenv('FLEET_CARRIERS')
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
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def addFC(ctx, FCCode, FCSys, FCName):
    # Checking if FC is already in the list, and if FC name is in correct format
    # Stops if FC is already in list, or if incorrect name format
    matched = re.match("[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]-[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]", FCCode)
    isnt_match = not bool(matched)  # If it is NOT a match, we enter the Invalid FC Code condition

    if isnt_match:
        await ctx.send(f'Invalid Fleet Carrier Code format! Format should look like XXX-YYY')
        return
    elif FCCode.upper() in FCDATA.keys():
        await ctx.send(f'{FCCode} is a code that is already in the Carrier list!')
        return
    # iterate through our known carriers and check if the alias is already assigned.
    for fc_code, fc_data in FCDATA.items():
        if FCName.lower() in fc_data['FCName']:
            await ctx.send(f'{FCName} is an alias that is already in the alias list belonging to carrier {fc_code}!')
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

    FCDATA[FCCode.upper()] = {'FCName': FCName.lower(), 'FCMid': midstr, 'FCSys': FCSys.lower()}
    save_carrier_data(FCDATA)

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
    fcname = fcname.lower()
    fcdata = False
    for fc_code, fc_data in FCDATA.items():
        if fc_data['FCName'] == fcname:
            fcdata = fc_data
            fccode = fc_code
            break

    if not fcdata:
        await ctx.send('The requested carrier is not in the list! Add carriers using the add_FC command!')
        return

    await ctx.send(f'Fetching stock levels for {fcname} ({fccode})')
    pmeters = {'marketId': fcdata['FCMid']}
    r = requests.get('https://www.edsm.net/api-system-v1/stations/market',params=pmeters)
    stn_data = r.json()

    com_data = stn_data['commodities']
    loc_data = stn_data['name']
    if com_data == []:
        await ctx.send(f"{fcname} has no current market data.")
        return

    name_data = ["" for x in range(len(com_data))]
    stock_data = ["" for x in range(len(com_data))]
    dem_data = ["" for x in range(len(com_data))]

    for i in range(len(com_data)):
        name_data[i] = com_data[i]['name']
        stock_data[i] = com_data[i]['stock']
        dem_data[i] = com_data[i]['demand']

    name_data = '\n'.join(name_data)
    string_stocks = [str(i) for i in stock_data]
    string_dems = [str(i) for i in dem_data]
    stock_data = '\n'.join(string_stocks)
    dem_data = '\n'.join(string_dems)
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


@bot.command(name='del_FC', help='Delete a fleet carrier from the tracking database.\n'
                                 'FCCode: Carrier ID Code')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def delFC(ctx, FCCode):
    FCCode = FCCode.upper()
    matched = re.match("[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]-[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]", FCCode)
    isnt_match = not bool(matched)  # If it is NOT a match, we enter the Invalid FC Code condition

    if isnt_match:
        await ctx.send(f'Invalid Fleet Carrier Code format! Format should look like XXX-YYY')
        return
    if FCCode in FCDATA.keys():
        fcname = FCDATA[FCCode]['FCName']
        FCDATA.pop(FCCode)
        save_carrier_data(FCDATA)
        await ctx.send(f'Carrier {fcname} ({FCCode}) has been removed from the list')


@bot.command(name='rename_FC', help='Rename a Fleet Carrier alias. \n'
                                    'FCCode: Carrier ID Code \n'
                                    'FCName: new name for the Carrier ')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def renameFC(ctx, FCCode, FCName):
    FCCode = FCCode.upper()
    FCName = FCName.lower()

    matched = re.match("[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]-[a-zA-Z0-9][a-zA-Z0-9][a-zA-Z0-9]", FCCode)
    isnt_match = not bool(matched)  # If it is NOT a match, we enter the Invalid FC Code condition

    if isnt_match:
        await ctx.send(f'Invalid Fleet Carrier Code format! Format should look like XXX-YYY')
        return
    if FCCode in FCDATA.keys():
        fcname_old = FCDATA[FCCode]['FCName']
        FCDATA[FCCode]['FCName'] = FCName
        save_carrier_data(FCDATA)
        await ctx.send(f'Carrier {fcname_old} ({FCCode}) has been renamed to {FCName}')


@bot.command(name='list', help='Lists all tracked carriers')
async def fclist(ctx):
    names = []
    for fc_code, fc_data in FCDATA.items():
        names.append("%s (%s)" % ( fc_data['FCName'], fc_code))
    if not names:
        names = ['No Fleet Carriers are being tracked, add one!']
    print('Listing active carriers')

    names = '\n'.join(names)  # Joining the list with newline as the delimeter
    embed = discord.Embed(title='Tracked carriers')
    embed.add_field(name = 'Carrier Names', value = names)
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

def convert_carrier_data():
    print(f'Attempting to convert old style carrier list, searching for data:')
    dotenv_file = find_dotenv()
    fcfile = open(dotenv_file)
    envlist = fcfile.readlines()
    fcfile.close()

    envlist[3] = envlist[3].strip('\n')
    fcids = envlist[3].split('.')

    envlist[4] = envlist[4].strip('\n')
    names = envlist[4].split('.')

    envlist[5] = envlist[5].strip('\n')
    fcmids = envlist[5].split('.')

    i = 0
    FCDATA = {}

    for carrier in fcids:
        if carrier:
            print(f"Found Carrier %s Name %s Mid %s" % ( carrier, names[i], fcmids[i] ))
            FCDATA[carrier.upper()] = {'FCName': names[i].lower(), 'FCMid': fcmids[i], 'FCSys': 'unknown'}
        i = i + 1

    save_carrier_data(FCDATA)
    print(f'Please remove the old style carrier list from the .env file')
    return FCDATA


def load_carrier_data(CARRIERS):
    # unpack carrier data if we have it, or start fresh
    print(f'Loading Carrier Data.')
    try:
        FCDATA = json.loads(CARRIERS)
    except:
        FCDATA = convert_carrier_data()
    return FCDATA


def save_carrier_data(FCDATA):
    print(f'Saving Carrier Data.')
    #dotenv_file = find_dotenv()
    CARRIERS = json.dumps(FCDATA)
    set_key(carrierdb, "FLEET_CARRIERS", CARRIERS)


FCDATA = load_carrier_data(CARRIERS)
bot.run(TOKEN)
