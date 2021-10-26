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
import sys
import discord
import re
import requests
import json
import asyncio
from texttable import Texttable
import requests
from bs4 import BeautifulSoup
from dotenv import find_dotenv, load_dotenv, set_key
from discord.ext import commands, tasks
from datetime import datetime
import traceback

'''
# Debugging, used only in dev.
import logging
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)
'''

carrierdb = '.carriers'
load_dotenv()
load_dotenv(carrierdb)
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
CARRIERS = os.getenv('FLEET_CARRIERS')
WMMCHANNEL = os.getenv('WMM_CHANNEL', '📦wmm-stock')
wmm_interval = int(os.getenv('WMM_INTERVAL', 3600))
wmm_trigger = False
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix=';', intents=intents)


@bot.event
async def on_ready():
    guild = discord.utils.get(bot.guilds, name = GUILD) #bot.guilds is a list of all connected servers

    print(
        f'{bot.user.name} is connected to \n'
        f'{guild.name} (id: {guild.id})'
    )

    await start_wmm_task()

@tasks.loop(seconds=30)
async def wmm_stock(message, channel):
    global wmm_trigger
    wmm_commodities = ['indite', 'bertrandite', 'gold', 'silver']
    wmm_carriers = []
    wmm_systems = []
    for fc_code, fc_data in FCDATA.items():
        if 'wmm' in fc_data:
            wmm_carriers.append(fc_code)
            if fc_data['wmm'] not in wmm_systems:
                wmm_systems.append(fc_data['wmm'])

    if wmm_systems == []:
        nofc = "WMM Stock: No Fleet Carriers are currently being tracked for WMM. Please add some to the list!"
        try:
            await message.edit(content=nofc)
        except:
            await clear_history(channel)
            await channel.send(nofc)
        return

    content = {}
    wmm_stock = {}
    for fcid in wmm_carriers:
        carrier_has_stock = False
        stn_data = get_fc_stock(fcid, 'inara')
        if not stn_data:
            print("Inara stock check for carrier '%s' failed, skipping." % FCDATA[fcid]['FCName'])
            continue
        try:
            utc_time = datetime.strptime(stn_data['market_updated'], "%d %b %Y, %I:%M%p")
            market_updated = "<t:%d:R>" % utc_time.timestamp()
        except:
            market_updated = stn_data['market_updated']
            pass
        if stn_data == False:
            print("wmm_stock: could not get data for %s (%s)" % ( FCDATA[fcid]['FCName'], fcid ))
            continue
        com_data = stn_data['commodities']
        # Indite x 11.8k - Wally (Malerba) - P.T.N. Candy Van - Price: 34,789cr - @CMDR Sofiya Khlynina
        if com_data == []:
            content[FCDATA[fcid]['wmm']].append("**%s** - %s (%s) has no current market data. please visit the carrier with EDMC running" % (
                stn_data['full_name'], stn_data['name'], FCDATA[fcid]['wmm'] )
            )
            continue
        for com in com_data:
            if com['name'].lower() not in wmm_commodities:
                continue
            if com['stock'] != 0:
                carrier_has_stock = True
                if FCDATA[fcid]['wmm'] not in wmm_stock:
                    wmm_stock[FCDATA[fcid]['wmm']] = []
                if int(com['stock'].replace(',', '')) < 1000:
                    #wmm_stock[FCDATA[fcid]['wmm']].append("%s x %s - %s - **%s** - Price: %s - LOW STOCK %s (As of %s)" % (
                    #    com['name'], com['stock'], FCDATA[fcid]['wmm'], stn_data['full_name'][:-10], com['buyPrice'], FCDATA[fcid]['owner'], market_updated )
                    #)
                    wmm_stock[FCDATA[fcid]['wmm']].append("%s x %s - %s (%s) - **%s** - Price: %s - LOW STOCK %s (As of %s)" % (
                        com['name'], com['stock'], stn_data['name'], FCDATA[fcid]['wmm'], stn_data['full_name'], com['buyPrice'], FCDATA[fcid]['owner'], market_updated )
                    )
                else:
                    #wmm_stock[FCDATA[fcid]['wmm']].append("%s x %s - %s - **%s** - Price: %s (As of %s)" % (
                    #    com['name'], com['stock'], FCDATA[fcid]['wmm'], stn_data['full_name'][:-10], com['buyPrice'], market_updated )
                    #)
                    wmm_stock[FCDATA[fcid]['wmm']].append("%s x %s - %s (%s) - **%s** - Price: %s (As of %s)" % (
                        com['name'], com['stock'], stn_data['name'], FCDATA[fcid]['wmm'], stn_data['full_name'], com['buyPrice'], market_updated )
                    )
        if not carrier_has_stock:
            #wmm_stock[FCDATA[fcid]['wmm']].append("**%s** - %s has no stock of any commodity! %s (As of %s)" % (
            #    stn_data['full_name'][:-10], FCDATA[fcid]['wmm'], FCDATA[fcid]['owner'], market_updated )
            #)
            wmm_stock[FCDATA[fcid]['wmm']].append("**%s** - %s (%s) has no stock of any commodity! %s (As of %s)" % (
                stn_data['full_name'], stn_data['name'], FCDATA[fcid]['wmm'], FCDATA[fcid]['owner'], market_updated )
            )

    for system in wmm_systems:
        content[system] = []
        content[system].append('-')
        if system not in wmm_stock:
            content[system].append("Could not find any carriers with stock in %s" % system)
        else:
            for line in wmm_stock[system]:
                content[system].append(line)

    try:
        wmm_updated = "<t:%d:R>" % datetime.now().timestamp()
    except:
        wmm_updated = datetime.now().strftime("%d %b %Y %H:%M:%S")
        pass

    # clear message history
    await clear_history(channel)

    # for each station, use a new message.
    # and split messages over 10 lines.
    # each line is between 120-200 chars
    # using max: 2000 / 200 = 10
    for (system, stncontent) in content.items():
        pages = [page for page in chunk(stncontent, 10)]
        for page in pages:
            page.insert(0, ':')
            await channel.send('\n'.join(page))

    footer = []
    footer.append(':')
    footer.append("-\nCarrier stocks last checked %s\nNumbers out of wack? Ensure EDMC is running!" % ( wmm_updated ))
    await channel.send('\n'.join(footer))

    # the following code allows us to change sleep time dynamically
    # waiting at least 10 seconds before checking wmm_interval again
    # This also checks for the trigger to manually update.
    slept_for = 0
    while slept_for < wmm_interval:
        # wmm_trigger is set by ;wmm_stock command
        if wmm_trigger:
            wmm_trigger = False
            slept_for = wmm_interval
        else:
            await asyncio.sleep(10)
            slept_for = slept_for + 10


@wmm_stock.after_loop
async def wmm_after_loop():
    if not wmm_stock.is_running() or wmm_stock.failed():
        print("wmm_stock after_loop(). task has failed.\n")

@wmm_stock.error
async def wmm_stock_error(error):
    if not wmm_stock.is_running() or wmm_stock.failed():
        print("wmm_stock error(). task has failed.\n")
    traceback.print_exc()


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
                                 'FCSys: Carrier current system, use "auto", "auto-edsm", or "auto-inara" to search. ("auto" uses edsm)\n'
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

    if FCSys == 'auto-inara':
        search_data = inara_find_fc_system(FCCode)
    elif FCSys == 'auto-edsm' or FCSys == 'auto':
        search_data = edsm_find_fc_system(FCCode)
    if search_data is False:
        await ctx.send(f'Could not find the FC system. please manually supply system name')
        return
    else:
        FCSys = search_data['system']

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


@bot.command(name='stock', help='Returns stock of a PTN carrier (carrier needs to be added first)\n'
                                'source: Optional argument, one of "edsm" or "inara". Defaults to "edsm".')
async def stock(ctx, fcname, source='edsm'):
    fccode = get_fccode(fcname)
    if fccode not in FCDATA:
        await ctx.send('The requested carrier is not in the list! Add carriers using the add_FC command!')
        return

    await ctx.send(f'Fetching stock levels for **{fcname} ({fccode})**')

    stn_data = get_fc_stock(fccode, source)
    if stn_data is False:
        await ctx.send(f"{fcname} has no current market data.")
        return

    com_data = stn_data['commodities']
    loc_data = stn_data['name']
    if com_data == []:
        await ctx.send(f"{fcname} has no current market data.")
        return

    table = Texttable()
    table.set_cols_align(["l", "r", "r"])
    table.set_cols_valign(["m", "m", "m"])
    table.set_cols_dtype(['t', 'i', 'i'])
    #table.set_deco(Texttable.HEADER | Texttable.HLINES)
    table.set_deco(Texttable.HEADER)
    table.header(["Commodity", "Amount", "Demand"])

    for com in com_data:
        if com['stock'] != 0 or com['demand'] != 0:
            table.add_row([com['name'], com['stock'], com['demand']])

    msg = "```%s```\n" % ( table.draw() )
    #print('Creating embed...')
    embed = discord.Embed()
    embed.add_field(name = f"{fcname} ({stn_data['sName']}) stock", value = msg, inline = False)
    embed.add_field(name = 'FC Location', value = loc_data, inline = False)
    embed.set_footer(text = f"Data last updated: {stn_data['market_updated']}\nNumbers out of wack? Ensure EDMC is running!")
    #print('Embed created!')
    await ctx.send(embed=embed)
    #print('Embed sent!')


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


@bot.command(name='list', help='Lists all tracked carriers. \n'
                               'Filter: use "wmm" to show only wmm-tracked carriers.')
async def fclist(ctx, Filter=None):
    names = []
    for fc_code, fc_data in FCDATA.items():
        if Filter and 'wmm' not in fc_data:
            continue
        if 'wmm' in fc_data:
            names.append("%s (%s) - WMM" % ( fc_data['FCName'], fc_code))
        else:
            names.append("%s (%s)" % ( fc_data['FCName'], fc_code))
    if not names:
        names = ['No Fleet Carriers are being tracked, add one!']
    print('Listing active carriers')

    carriers = sorted(names)  # Joining the list with newline as the delimeter

    def validate_response(react, user):
        return user == ctx.author and str(react.emoji) in ["◀️", "▶️"]
        # This makes sure nobody except the command sender can interact with the "menu"

    pages = [page for page in chunk(carriers)]

    max_pages = len(pages)
    current_page = 1

    embed = discord.Embed(title=f"{len(carriers)} Tracked Fleet Carriers, Page: #{current_page} of {max_pages}")
    embed.add_field(name = 'Carrier Names', value = '\n'.join(pages[0]))

    # Now go send it and wait on a reaction
    message = await ctx.send(embed=embed)

    # From page 0 we can only go forwards
    if max_pages > 1:
        await message.add_reaction("▶️")

    # 60 seconds time out gets raised by Asyncio
    while True:
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=60, check=validate_response)
            if str(reaction.emoji) == "▶️" and current_page != max_pages:

                print(f'{ctx.author} requested to go forward a page.')
                current_page += 1   # Forward a page
                new_embed = discord.Embed(title=f"{len(carriers)} Tracked Fleet Carriers, Page: #{current_page} of {max_pages}")
                new_embed.add_field(name='Carrier Names', value='\n'.join(pages[current_page-1]))
                await message.edit(embed=new_embed)

                await message.add_reaction("◀️")
                if current_page == 2:
                    await message.clear_reaction("▶️")
                    await message.add_reaction("▶️")
                elif current_page == max_pages:
                    await message.clear_reaction("▶️")
                else:
                    await message.remove_reaction(reaction, user)

            elif str(reaction.emoji) == "◀️" and current_page > 1:
                print(f'{ctx.author} requested to go back a page.')
                current_page -= 1   # Go back a page

                new_embed = discord.Embed(title=f"{len(carriers)} Tracked Fleet Carriers, Page: #{current_page} of {max_pages}")
                new_embed.add_field(name='Carrier Names', value='\n'.join(pages[current_page-1]))


                await message.edit(embed=new_embed)
                # Ok now we can go forwards, check if we can also go backwards still
                if current_page == 1:
                    await message.clear_reaction("◀️")

                await message.remove_reaction(reaction, user)
                await message.add_reaction("▶️")
            else:
                # It should be impossible to hit this part, but lets gate it just in case.
                print(f'HAL9000 error: {ctx.author} ended in a random state while trying to handle: {reaction.emoji} '
                      f'and on page: {current_page}.')
                # HAl-9000 error response.
                error_embed = discord.Embed(title=f"I'm sorry {ctx.author}, I'm afraid I can't do that.")
                await message.edit(embed=error_embed)
                await message.remove_reaction(reaction, user)

        except asyncio.TimeoutError:
            print(f'Timeout hit during carrier request by: {ctx.author}')
            await ctx.send(f'Closed the active carrier list request from: {ctx.author} due to no input in 60 seconds.')
            await message.delete()
            break


@bot.command(name='start_wmm_tracking', help='Start tracking a FC for the WMM stock list. \n'
                                    'FCName: name of an existing fleet carrier\n'
                                    'Station: name of the closest station to the carrier. For display purposes only\n'
                                    'Owner: the discord owner to notify on empty stock')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod', 'Certified Carrier')
async def addwmm(ctx, FCName, station, owner):
    fccode = get_fccode(FCName)
    if not fccode:
        await ctx.send('The requested carrier is not in the list! Add carriers using the add_FC command!')
        return

    FCDATA[fccode]['wmm'] = "%s" % station.title()
    FCDATA[fccode]['owner'] = owner
    save_carrier_data(FCDATA)
    await ctx.send(f'Carrier {FCName} ({fccode}) has been added to WMM stock list')


@bot.command(name='stop_wmm_tracking', help='Stop tracking a Fleet Carrier(s) for the WMM stock list. \n'
                                    'FCName: name of an existing fleet carrier(s).\n'
                                    'Multiple carriers can be specified using comma seperation. \n')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod', 'Certified Carrier')
async def delwmm(ctx, FCName):
    carriers = FCName.split(',')
    for carrier in carriers:
        fccode = get_fccode(carrier)
        if not fccode:
            await ctx.send('The requested carrier %s is not in the list! Add carriers using the add_FC command!' % carrier)
            continue

        FCDATA[fccode].pop('wmm', None)
        FCDATA[fccode].pop('owner', None)
        await ctx.send(f'Carrier {carrier} ({fccode}) has been removed from the WMM stock list')
    save_carrier_data(FCDATA)


@bot.command(name='set_wmm_interval', help='Change the wmm-stock update interval.')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def setwmminterval(ctx, interval):
    global wmm_interval
    wmm_interval = int(interval)
    save_wmm_interval(wmm_interval)
    await ctx.send(f'wmm-stock interval changed to {wmm_interval} seconds')


@bot.command(name='get_wmm_interval', help='Get the current wmm-stock update interval.')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def getwmminterval(ctx):
    await ctx.send(f'wmm-stock interval is currently {wmm_interval} seconds')


@bot.command(name='wmm_stock', help='Manually trigger the wmm stock update without changing the interval.')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod', 'Certified Carrier')
async def wmmstock(ctx):
    global wmm_trigger
    wmm_trigger = True
    await ctx.send(f'wmm stock update triggered, please stand by.')
    if not wmm_stock.is_running() or wmm_stock.failed():
        print("wmm_stock task has failed, restarting.")
        await ctx.send(f'wmm stock background task has failed, restarting...')
        await start_wmm_task()


@bot.command(name='wmm_status', help='Check the wmm background task status')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def wmmstatus(ctx):
    if not wmm_stock.is_running() or wmm_stock.failed():
        await ctx.send(f'wmm stock background task has failed, restarting...')
        await start_wmm_task()
    else:
        await ctx.send(f'wmm stock background task is running.')


@bot.event
async def on_error(event, *args, **kwargs):
    traceback.print_exc()
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


def save_wmm_interval(wmm_interval):
    print("Saving WMM Update Interval: %d ..." % wmm_interval, end='')
    set_key(find_dotenv(), "WMM_INTERVAL", str(wmm_interval), "auto")
    print("Done.")


def inara_find_fc_system(fcid):
    #print("Searching inara for carrier %s" % ( fcid ))
    #URL = "https://inara.cz/station/?search=%s" % ( fcid )
    URL = "https://inara.cz/search/?search=%s" % ( fcid )
    try:
        page = requests.get(URL)
        soup = BeautifulSoup(page.content, "html.parser")
        results = soup.find_all("div", class_="mainblock")
        stationid = results[1].find("a", class_="inverse", href=True)
        carrier = results[1].find("span", class_="normal")
        system = results[1].find("span", class_="uppercase")
        if fcid == carrier.text[-11:-4]:
            #print("Carrier: %s (stationid %s) is at system: %s" % (carrier.text[:-3], stationid['href'][9:-1], system.text))
            return {'system': system.text, 'stationid': stationid['href'][9:-1], 'full_name': carrier.text[:-3] }
        else:
            #print("Could not find exact match, aborting inara search")
            return False
    except Exception as e:
        print("No results from inara for %s, aborting search. Error: %s" % ( fcid, e ))
        traceback.print_exc()
        return False


def edsm_find_fc_system(fcid):
    #print("Searching edsm for carrier %s" % ( fcid ))
    URL = "https://www.edsm.net/en/search/stations/index/name/%s/sortBy/distanceSol/type/31" % ( fcid )
    try:
        page = requests.get(URL)
        soup = BeautifulSoup(page.content, "html.parser")
        results = soup.find("table", class_="table table-hover").find("tbody").find_all("a")
        carrier = results[0].get_text()
        system = results[1].get_text()
        market_updated = results[6].find("i").attrs.get("title")[27:]
        if fcid == carrier:
            #print("Carrier: %s is at system: %s" % (carrier, system))
            return {'system': system, 'market_updated': market_updated}
        else:
            #print("Could not find exact match, aborting inara search")
            return False
    except:
        print("No results from edsm for %s, aborting search." % fcid)
        return False


def inara_fc_market_data(stationid, fcid):
    #print("Searching inara market data for station: %s (%s)" % ( stationid, fcid ))
    try:
        URL = "https://inara.cz/station/%s" % ( stationid )
        page = requests.get(URL)
        soup = BeautifulSoup(page.content, "html.parser")
        system = soup.find("title").get_text()[21:-8]
        updated = soup.find("div", text="Market update").next_sibling.get_text()
        results = soup.find("div", class_="mainblock maintable")
        rows = results.find("table", class_="tablesorterintab").find("tbody").find_all("tr")
        marketdata = []
        for row in rows:
            rowclass = row.attrs.get("class") or []
            if "subheader" in rowclass:
                continue
            cells = row.find_all("td")
            rn = cells[0].get_text()
            commodity = {
                            'id': rn,
                            'name': rn,
                            'sellPrice': cells[1].get_text(),
                            'buyPrice': cells[2].get_text(),
                            'demand': cells[3].get_text().replace('-', '0'),
                            'stock': cells[4].get_text().replace('-', '0')
                        }
            marketdata.append(commodity)
        data = {}
        data['name'] = system
        data['sName'] = fcid
        data['stationId'] = stationid
        data['market_updated'] = updated
        data['commodities'] = marketdata
        return data
    except Exception as e:
        print("Exception getting inara data: %s" % e)
        return False


def get_fccode(fcname):
    # TODO support ;stock command here, namely fcdata
    fcname = fcname.lower()
    #fcdata = False
    fccode = False
    for fc_code, fc_data in FCDATA.items():
        if fc_data['FCName'] == fcname:
            #fcdata = fc_data
            fccode = fc_code
            break
    return fccode


def get_fc_stock(fccode, source='edsm'):
    if source == 'inara':
        inara_data = inara_find_fc_system(fccode)
        if inara_data:
            stn_data = inara_fc_market_data(inara_data['stationid'], fccode)
            if not stn_data:
                return False
            stn_data['full_name'] = inara_data['full_name']
        else:
            return False
    else:
        pmeters = {'marketId': FCDATA[fccode]['FCMid']}
        r = requests.get('https://www.edsm.net/api-system-v1/stations/market',params=pmeters)
        stn_data = r.json()

        edsm_search = edsm_find_fc_system(fccode)
        if edsm_search:
            stn_data['market_updated'] = edsm_search['market_updated']
        else:
            stn_data['market_updated'] = "Unknown"
        stn_data['full_name'] = False
    return stn_data


async def start_wmm_task():
    if wmm_stock.is_running():
        print("def start_wmm_task: task is_running(), cannot start.")
        return False
    channel = discord.utils.get(bot.get_all_channels(), guild__name=GUILD, name=WMMCHANNEL)
    print("Clearing last stock update message in #%s" % channel)
    await clear_history(channel)
    print("Starting WMM stock background task")
    message = await channel.send('Stock Bot initialized, preparing for WMM stock update.')
    wmm_stock.start(message, channel)


def chunk(chunk_list, max_size=10):
    """
    Take an input list, and an expected max_size.

    :returns: A chunked list that is yielded back to the caller
    :rtype: iterator
    """
    for i in range(0, len(chunk_list), max_size):
        yield chunk_list[i:i + max_size]


async def clear_history(channel, limit=20):
    msgs = []
    async for message in channel.history(limit=limit):
        if message.author.name == bot.user.name:
            msgs.append(message)
    await channel.delete_messages(msgs)


FCDATA = load_carrier_data(CARRIERS)
bot.run(TOKEN)
