# Stockbot
# Written by Matthew Circelli
# Ver: 2.1 - Discord.py v2
# Date: 2022-11-20
# Desc: Bot that tracks Carrier Stock and WMM data for the Pilots Trade Network discord.
# Refs: Discord.py API: https://discordpy.readthedocs.io/en/latest/api.html#
# Dev portal: https://discord.com/developers/applications/803357001765617705/bot

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
from discord import app_commands
from datetime import datetime
import traceback

carrierdb = '.carriers'
load_dotenv()
load_dotenv(carrierdb)
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
CARRIERS = os.getenv('FLEET_CARRIERS')
WMMCHANNEL = os.getenv('WMM_CHANNEL', '📦wmm-stock')
CCOWMMCHANNEL = os.getenv('CCO_WMM_CHANNEL', 'cco-wmm-supplies')
ENV = os.getenv('ENV', 'prod')
API_HOST = os.getenv('API_HOST')
API_TOKEN = os.getenv('API_TOKEN')
wmm_interval = int(os.getenv('WMM_INTERVAL', 3600))
wmm_trigger = False
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=';', intents=intents)
guild_obj = discord.Object(id=GUILD_ID)

if ENV != 'prod':
    # Debugging, used only in dev.
    import logging
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)

@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)

    print(
        f'{bot.user.name} is connected to {guild.name} (id: {guild.id})\n'
        f'Bot is running in env: {ENV}'
    )

    await start_wmm_task()
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)


@tasks.loop(seconds=30)
async def wmm_stock(message, channel, ccochannel):
    #print(f"wmm_stock function start")
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
    ccocontent = {}
    wmm_stock = {}
    wmm_station_stock = {}

    for fcid in wmm_carriers:
        carrier_has_stock = False
        if 'cAPI' in FCDATA[fcid]:
            print(f"Calling CApi for carrier {fcid}")
            capi_response = capi(fcid)
            stn_data = capi_response.json()

            print(f"capi response: {capi_response.status_code}")
            if capi_response.status_code != 200:
                # TODO handle missing carriers, auth errors etc.
                print(f"Error from CAPI for {fcid}: {capi_response.status_code} - {stn_data}")
                if capi_response.status_code == 500:
                    # this is an internal stockbot api error, dont re-auth for this.
                    print(f"Internal stockbot API error, someone check the logs")
                    continue
                elif capi_response.status_code == 418:
                    # capi is down for maintenance.
                    await clear_history(channel)
                    message = f"Bleep Bloop: Frontier API is down for maintenance, unable to retrieve stocks for all carriers. Retrying in 60 seconds."
                    await channel.send(message)
                    await asyncio.sleep(60)
                    return
                elif capi_response.status_code == 400 or capi_response.status_code == 401:
                    # User needs to re-auth. (400 = EGS, 401 = Expired Token)
                    FCDATA[fcid].pop('cAPI', None)
                    save_carrier_data(FCDATA)
                    message = (f'I was unable to retrieve your carrier stock levels for "{FCDATA[fcid]["FCName"]} ({fcid})" from the cAPI, please re-authenticate '
                                f'using the `;capi_enable {FCDATA[fcid]["FCName"]}` command. Stocks will be fetched from Inara until this has been completed.')
                    await dm_bot_owner(fcid, FCDATA[fcid]['owner'], message)
                else:
                    # all other unknown errors.
                    print(f"Unknown error from CAPI, see above for details.")
                    continue
            else:
                carrier_name = f"{from_hex(stn_data['name']['vanityName']).title().strip()} ({stn_data['name']['callsign']})"
                market_updated = ''

        # this catches the case where we remove the cAPI flag above if auth fails.
        if 'cAPI' not in FCDATA[fcid]:
            stn_data = get_fc_stock(fcid, 'inara')
            if not stn_data:
                print(f"no inara market data for {fcid}")
                continue
            carrier_name = stn_data['full_name']
            stn_data['currentStarSystem'] = stn_data['name']
            stn_data['market'] = {'commodities': stn_data['commodities']}
            try:
                utc_time = datetime.strptime(stn_data['market_updated'].split('(')[1][0:-1], "%d %b %Y, %I:%M%p")
                market_updated = "(As of <t:%d:R>)" % utc_time.timestamp()
            except:
                market_updated = "(As of %s)" % stn_data['market_updated']
                pass
        if 'market' not in stn_data:
            print(f"No market data for {fcid}")
            continue

        com_data = stn_data['market']['commodities']
        if com_data == []:
            content[FCDATA[fcid]['wmm']].append("**%s** - %s (%s) has no current market data. please visit the carrier with EDMC running" % (
                carrier_name, stn_data['currentStarSystem'], FCDATA[fcid]['wmm'] )
            )
            continue
        for com in com_data:
            if FCDATA[fcid]['wmm'] not in wmm_stock:
                wmm_stock[FCDATA[fcid]['wmm']] = []
            if stn_data['currentStarSystem'] not in wmm_station_stock:
                wmm_station_stock[stn_data['currentStarSystem']] = {}
            if FCDATA[fcid]['wmm'] not in wmm_station_stock[stn_data['currentStarSystem']]:
                wmm_station_stock[stn_data['currentStarSystem']][FCDATA[fcid]['wmm']] = {}
            if com['name'].lower() not in wmm_commodities:
                continue
            if com['stock'] != 0:
                carrier_has_stock = True
                if com['name'].lower() not in wmm_station_stock[stn_data['currentStarSystem']][FCDATA[fcid]['wmm']]:
                    wmm_station_stock[stn_data['currentStarSystem']][FCDATA[fcid]['wmm']][com['name'].lower()] = int(com['stock'])
                else:
                    wmm_station_stock[stn_data['currentStarSystem']][FCDATA[fcid]['wmm']][com['name'].lower()] += int(com['stock'])
                if int(com['stock']) < 1000:
                    wmm_stock[FCDATA[fcid]['wmm']].append("%s x %s - %s (%s) - **%s** - Price: %s - LOW STOCK %s" % (
                        com['name'], format(com['stock'], ','), stn_data['currentStarSystem'], FCDATA[fcid]['wmm'], carrier_name, format(com['buyPrice'], ','), market_updated )
                    )
                    if 'notified' not in FCDATA[fcid]:
                        # catch wmm objects created before this update.
                        FCDATA[fcid]['notified'] = {}
                    if com['name'] not in FCDATA[fcid]['notified']:
                        # Notify the owner once per commodity per wmm_tracking session.
                        message = "Your Fleet Carrier **%s** is low on %s - %s remaining" % (
                                carrier_name, com['name'], com['stock'] )
                        if await dm_bot_owner(fcid, FCDATA[fcid]['owner'], message):
                            FCDATA[fcid]['notified'][com['name']] = True
                            save_carrier_data(FCDATA)
                else:
                    wmm_stock[FCDATA[fcid]['wmm']].append("%s x %s - %s (%s) - **%s** - Price: %s %s" % (
                        com['name'], format(com['stock'], ','), stn_data['currentStarSystem'], FCDATA[fcid]['wmm'], carrier_name, format(com['buyPrice'], ','), market_updated )
                    )
        if not carrier_has_stock:
            wmm_stock[FCDATA[fcid]['wmm']].append("**%s** - %s (%s) has no stock of any WMM commodity! %s" % (
                carrier_name, stn_data['currentStarSystem'], FCDATA[fcid]['wmm'], market_updated )
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
        if len(stncontent) == 1:
            # this station has no carriers, dont bother printing it.
            continue
        pages = [page for page in chunk(stncontent, 10)]
        for page in pages:
            page.insert(0, ':')
            await channel.send('\n'.join(page))

    footer = []
    footer.append(':')
    footer.append("-\nCarrier stocks last checked %s" % ( wmm_updated ))
    footer.append("Carriers with no timestamp are fetched from cAPI and are accurate to within an hour.")
    footer.append("Carriers with (As of ...) are fetched from Inara. Ensure EDMC is running to update stock levels!")
    await channel.send('\n'.join(footer))

    for system in wmm_station_stock:
        ccocontent[system] = []
        for station in wmm_station_stock[system]:
            ccocontent[system].append('-')
            for commodity in wmm_commodities:
                if commodity not in wmm_station_stock[system][station]:
                    ccocontent[system].append(f"{commodity.title()} x NO STOCK !! - {system} ({station})")
                else:
                    ccocontent[system].append(f"{commodity.title()} x {format(wmm_station_stock[system][station][commodity], ',')} - {system} ({station})")

    # for each station, use a new message.
    # and split messages over 10 lines.
    # each line is roughly 50 chars
    # using max: 2000 / 50 = 40
    await clear_history(ccochannel)
    for (system, stncontent) in ccocontent.items():
        if len(stncontent) == 1:
            # this station has no carriers, dont bother printing it.
            continue
        pages = [page for page in chunk(stncontent, 40)]
        for page in pages:
            page.insert(0, ':')
            await ccochannel.send('\n'.join(page))

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


@bot.hybrid_command(name='stockbot_ping', help='If the bot hasnt crashed, it will respond >pong<')
async def ping(ctx):
    await ctx.send('pong!')


@bot.command(name='add_FC', help='Add a fleet carrier for stock tracking.\n'
                                 'FCCode: Carrier ID Code \n'
                                 'FCName: The alias with which you want to refer to the carrier. Please use something\n'
                                 '        simple like "orion" or "9oclock", as this is what you use to call the stock command!\n'
                                 'Owner: The discord owner ID or @mention to DM on empty WMM and capi authentication.')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def addFC(ctx, FCCode, FCName, owner):
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
        if FCName.lower() == fc_data['FCName']:
            await ctx.send(f'{FCName} is an alias that is already in the alias list belonging to carrier {fc_code}!')
            return

    # verify owner ID is valid using server.get_member()
    try:
        owner_id = "".join(re.findall(r'\d+',str(owner)))
        owner_member = ctx.guild.get_member(int(owner_id))
        if owner_member is None:
            await ctx.send(f'"{owner}" is not a valid discord user!')
            return
    except:
        await ctx.send(f'"{owner}" is not a valid discord user!!')
        return

    print(f'Format is good... Checking database...')

    FCDATA[FCCode.upper()] = {
        'FCName': FCName.lower(),
        #'FCMid': midstr, # EDSM Data, removed.
        #'FCSys': FCSys.lower(), # EDSM Data, removed.
        'owner': owner_member.id,
    }
    save_carrier_data(FCDATA)

    await ctx.send(f'Added {FCCode} to the FC list, under reference name {FCName}')


def stock_command(fcname, source):
    source = source.lower()
    fccode = fcname.upper() if fcname.upper() in FCDATA.keys() else get_fccode(fcname)
    if fccode not in FCDATA:
        return {'msg': 'The requested carrier is not in the list! Add carriers using the add_FC command!'}

    if source == 'auto':
        if 'cAPI' in FCDATA[fccode]:
            stn_data = get_fc_stock(fccode, 'capi')
            source = 'capi'
        else:
            stn_data = get_fc_stock(fccode, 'inara')
            source = 'inara'
    else:
        if source not in ['capi', 'inara']:
             return {'msg': 'Invalid source! Please use "capi" or "inara"'}
        stn_data = get_fc_stock(fccode, source)

    if stn_data is False:
        return {'msg': f"{FCDATA[fccode]['FCName']} has no current market data."}

    com_data = stn_data['commodities']
    loc_data = stn_data['name']
    if com_data == []:
        return {'msg': f"{FCDATA[fccode]['FCName']} has no current market data."}

    table = Texttable()
    table.set_cols_align(["l", "r", "r"])
    table.set_cols_valign(["m", "m", "m"])
    table.set_cols_dtype(['t', 'i', 'i'])
    table.set_deco(Texttable.HEADER)
    table.header(["Commodity", "Amount", "Demand"])

    for com in com_data:
        if com['stock'] != 0 or com['demand'] != 0:
            table.add_row([com['name'], com['stock'], com['demand']])

    msg = "```%s```\n" % ( table.draw() )
    embed = discord.Embed()
    embed.add_field(name = f"{FCDATA[fccode]['FCName']} ({stn_data['sName']}) stock", value = msg, inline = False)
    embed.add_field(name = 'FC Location', value = loc_data, inline = False)
    embed.set_footer(text = f"Data last updated: {stn_data['market_updated']}\n"
                            f"Data Source: {source}\n"
                            f"Numbers out of wack? Ensure EDMC is running!")
    return {'embed': embed}


@bot.tree.command(guild=guild_obj, name="stock", description="Get the current stock of a fleet carrier")
@app_commands.describe(name='Name of the PTN carrier')
@app_commands.describe(source='Optional argument, one of "inara" or "capi". Defaults to capi -> inara fallback.')
async def slash_stock(interaction: discord.Interaction, name: str, source: str = 'auto'):
    response = stock_command(name, source)
    if 'msg' in response:
        await interaction.response.send_message(response['msg'])
    elif 'embed' in response:
        await interaction.response.send_message(embed=response['embed'])
    else:
        await interaction.response.send_message('Something went wrong!')


@bot.command(name='stock', help='Returns stock of a PTN carrier (carrier needs to be added first)\n'
                                'Source: Optional argument, one of "inara" or "capi". Defaults to capi -> inara fallback.')
async def stock(ctx, fcname, source='auto'):
    response = stock_command(fcname, source)
    if 'msg' in response:
        await ctx.send(response['msg'])
    elif 'embed' in response:
        await ctx.send(embed=response['embed'])
    else:
        await ctx.send('Something went wrong!')


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
        owner = 'Unknown'
        if 'owner' in fc_data:
            if isinstance(fc_data['owner'], int):
                owner = "<@!%s>" % fc_data['owner']
            else:
                owner = fc_data['owner']
        cAPI = 'Disabled'
        if 'cAPI' in fc_data:
            if fc_data['cAPI'] == True:
                cAPI = 'Enabled'
        if 'wmm' in fc_data:
            names.append("%s (%s) Owner: %s - cAPI: %s - WMM Active" % ( fc_data['FCName'], fc_code, owner, cAPI ))
        else:
            names.append("%s (%s) Owner: %s - cAPI: %s" % ( fc_data['FCName'], fc_code, owner, cAPI ))
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
                                    '!! STATIONS WITH SPACES IN THE NAMES NEED TO BE "QUOTED LIKE THIS" !!\n')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod', 'Certified Carrier')
async def addwmm(ctx, FCName, station):
    fccode = get_fccode(FCName)
    if not fccode:
        await ctx.send('The requested carrier is not in the list! Add carriers using the add_FC command!')
        return
    FCDATA[fccode]['wmm'] = "%s" % station.title()
    FCDATA[fccode]['notified'] = {}
    save_carrier_data(FCDATA)
    msg = f'Carrier {FCName} ({fccode}) has been added to WMM stock list. Consider using ;capi_enable to fetch stocks if this is a non-Epic Games carrier.'
    if 'cAPI' in FCDATA[fccode]:
        if FCDATA[fccode]['cAPI'] == True:
            msg = f'Carrier {FCName} ({fccode}) has been added to WMM stock list. cAPI is already enabled.'
    await ctx.send(msg)


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
        FCDATA[fccode].pop('notified', None)
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


@bot.hybrid_command(name='wmm_stock', help='Manually trigger the wmm stock update without changing the interval.')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod', 'Certified Carrier')
async def wmmstock(ctx):
    global wmm_trigger
    wmm_trigger = True
    await ctx.send(f'wmm stock update triggered, please stand by.')
    if not wmm_stock.is_running() or wmm_stock.failed():
        print("wmm_stock task has failed, restarting.")
        await ctx.send(f'wmm stock background task has failed, restarting...')
        await start_wmm_task()


@bot.hybrid_command(name='wmm_status', help='Check the wmm background task status')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def wmmstatus(ctx):
    if not wmm_stock.is_running() or wmm_stock.failed():
        await ctx.send(f'wmm stock background task has failed, restarting...')
        await start_wmm_task()
    else:
        await ctx.send(f'wmm stock background task is running.')


@bot.command(name='capi_enable', help='Enable the use of Frontier cAPI for a carriers stock check.\n'
                                'FCName: name of an existing fleet carrier(s).\n'
                                'Multiple carriers can be specified using comma seperation. \n')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod', 'Certified Carrier')
async def capienable(ctx, FCName):
    carriers = FCName.split(',')
    for carrier in carriers:
        fccode = get_fccode(carrier)
        if not fccode:
            await ctx.send('The requested carrier %s is not in the list! Add carriers using the add_FC command!' % carrier)
            continue
        # do we have an existing auth?
        capi_response = capi(fccode)
        if capi_response.status_code != 200:
            r = oauth_new(fccode)
            oauth_response = r.json()
            print(f"capi_enable response {r.status_code} - {oauth_response}")
            if 'token' in oauth_response:
                oauth_url = f"{API_HOST}/generate/{fccode}?token={oauth_response['token']}"
                message = f'Please allow me access to track your carrier "{carrier} ({fccode})" data by linking me to your Frontier account here: {oauth_url}'
                await dm_bot_owner(fccode, FCDATA[fccode]['owner'], message)
                await ctx.send(f"cAPI auth URL generated, DM sent to carrier owner.")
                FCDATA[fccode]['cAPI'] = True
            else:
                await ctx.send("Could not generate auth URL for carrier %s: something went horribly wrong :(" % carrier)
        else:
            FCDATA[fccode]['cAPI'] = True
            await ctx.send(f"cAPI auth already exists for carrier, enabling stock fetching.")
    save_carrier_data(FCDATA)


@bot.command(name='capi_disable', help='Disable the use of Frontier cAPI for a carriers stock check.\n'
                                'FCName: name of an existing fleet carrier(s).\n'
                                'Multiple carriers can be specified using comma seperation. \n')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod', 'Certified Carrier')
async def capidisable(ctx, FCName):
    carriers = FCName.split(',')
    for carrier in carriers:
        fccode = get_fccode(carrier)
        if not fccode:
            await ctx.send('The requested carrier %s is not in the list! Add carriers using the add_FC command!' % carrier)
            continue
        FCDATA[fccode].pop('cAPI', None)
        await ctx.send(f'Carrier {carrier} ({fccode}) cAPI access has been disabled')
    save_carrier_data(FCDATA)


@bot.command(name='set_owner', help='Set the owner of a fleet carrier.\n'
                                'FCName: name of an existing fleet carrier.\n'
                                'Owner: discord user id or @mention of the owner.')
@commands.has_any_role('Bot Handler', 'Admin', 'Mod')
async def setowner(ctx, FCName, owner):
    fccode = get_fccode(FCName)
    if not fccode:
        await ctx.send('The requested carrier %s is not in the list! Add carriers using the add_FC command!' % FCName)
        return

    # verify owner ID is valid using server.get_member()
    try:
        owner_id = "".join(re.findall(r'\d+',str(owner)))
        owner_member = ctx.guild.get_member(int(owner_id))
        if owner_member is None:
            await ctx.send(f'"{owner}" is not a valid discord user!')
            return
    except:
        await ctx.send(f'"{owner}" is not a valid discord user!!')
        return

    FCDATA[fccode]['owner'] = owner_member.id
    await ctx.send(f'Carrier {FCName} ({fccode}) owner set to {owner_member.mention}')
    save_carrier_data(FCDATA)


@bot.event
async def on_error(event, *args, **kwargs):
    traceback.print_exc()
    raise


@bot.event
async def on_command_error(ctx, error):
    command = ctx.invoked_with
    if ENV == 'dev':
        from pprint import pprint
        print('== Start Command Error ==')
        pprint(command)
        pprint(error)
        print('== End Command Error ==')
    if isinstance(error, commands.errors.CheckFailure):
        message = "You do not have the correct role for this command."
    elif isinstance(error, commands.MissingPermissions):
        message = "You are missing the required permissions to run this command!"
    elif isinstance(error, commands.MissingRequiredArgument):
        message = f"Missing a required argument: '{error.param}'. See `;help {command}` for more info."
    elif isinstance(error, commands.ConversionError):
        message = str(error)
    else:
        message = "Oh no! Something went wrong while running the command!"
    await ctx.send(message)


def convert_carrier_data():
    print(f'Attempting to convert old style carrier list, searching for data:')
    dotenv_file = find_dotenv()
    fcfile = open(dotenv_file)
    envlist = fcfile.readlines()
    fcfile.close()

    envlist[3] = envlist[3].strip('\n')
    if ' ' not in envlist[3]:
        print("old style carrier list not found in env file, skipping conversion.")
        return {}
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
        # remove EDSM data from carrier data
        print(f'Removing EDSM data from carrier data.')
        for carrier in FCDATA:
            FCDATA[carrier].pop('FCSys', None)
            FCDATA[carrier].pop('FCMid', None)
        save_carrier_data(FCDATA)
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
    URL = "https://inara.cz/elite/station-market/?search=%s" % (fcid)
    try:
        page = requests.get(URL, headers={'User-Agent': 'PTNStockBot'})
        soup = BeautifulSoup(page.content, "html.parser")
        header = soup.find_all("div", class_="headercontent")
        header_info = header[0].find("h2")
        carrier_system_info = header_info.find_all('a', href=True)
        carrier = carrier_system_info[0].text
        system = carrier_system_info[1].text

        if fcid in carrier:
            # print("Carrier: %s (stationid %s) is at system: %s" % (carrier.text, stationid['href'][9:-1], system))
            return {'system': system, 'stationid': carrier_system_info[0]['href'][15:-1], 'full_name': carrier}
        else:
            print("Could not find exact match, aborting inara search")
            return False
    except Exception as e:
        print("No results from inara for %s, aborting search. Error: %s" % (fcid, e))
        return False

def inara_fc_market_data(fcid):
    # print("Searching inara market data for station: %s (%s)" % ( stationid, fcid ))
    try:
        URL = "https://inara.cz/elite/station-market/?search=%s" % (fcid)
        page = requests.get(URL, headers={'User-Agent': 'PTNStockBot'})
        soup = BeautifulSoup(page.content, "html.parser")
        mainblock = soup.find_all('div', class_='mainblock')

        # Find carrier and system info
        header = soup.find_all("div", class_="headercontent")
        header_info = header[0].find("h2")
        carrier_system_info = header_info.find_all('a', href=True)
        carrier = carrier_system_info[0].text
        system = carrier_system_info[1].text

        # Find market info
        updated = soup.find("div", text="Market update").next_sibling.get_text()
        # main_content = soup.find('div', class_="maincontent0")
        table = mainblock[1].find('table')
        tbody = table.find("tbody")
        rows = tbody.find_all('tr')
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
                'sellPrice': int(cells[1].get_text().replace('-', '0').replace(',', '').replace(' Cr', '')),
                'buyPrice': int(cells[3].get_text().replace('-', '0').replace(',', '').replace(' Cr', '')),
                'demand': int(cells[2].get_text().replace('-', '0').replace(',', '')),
                'stock': int(cells[4].get_text().replace('-', '0').replace(',', ''))
            }
            marketdata.append(commodity)
        data = {}
        data['name'] = system
        data['currentStarSystem'] = system
        data['full_name'] = carrier
        data['sName'] = fcid
        data['market_updated'] = updated
        data['commodities'] = marketdata
        return data
    except Exception as e:
        print("Exception getting inara data for carrier: %s" % fcid)
        return False


def capi_fc_market_data(fcid):
    # get stocks from capi and format as inara data.
    capi_response = capi(fcid)
    if capi_response.status_code != 200:
        print(f"Error from CAPI for {fcid}: {capi_response.status_code}")
        return False
    stn_data = capi_response.json()
    if 'market' not in stn_data:
        print(f"No market data for {fcid}")
        return False
    stn_data['name'] = stn_data['currentStarSystem']
    stn_data['sName'] = fcid
    stn_data['market_updated'] = 'cAPI'
    if 'commodities' in stn_data['market']:
        # remove commodity from list if it has name 'Drones'.
        # this is a bug in the CAPI data.
        # then sort by name alphabetically.
        stn_data['commodities'] = sorted([c for c in stn_data['market']['commodities'] if c['name'] != 'Drones'], key=lambda d: d['name'])
    return stn_data


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


def get_fc_stock(fccode, source='inara'):
    if source == 'inara':
        stn_data = inara_fc_market_data(fccode)
        if not stn_data:
            return False
    elif source == 'capi':
        stn_data = capi_fc_market_data(fccode)
        if not stn_data:
            return False
    return stn_data


async def start_wmm_task():
    if wmm_stock.is_running():
        print("def start_wmm_task: task is_running(), cannot start.")
        return False
    channel = discord.utils.get(bot.get_all_channels(), guild__name=GUILD, name=WMMCHANNEL)
    ccochannel = discord.utils.get(bot.get_all_channels(), guild__name=GUILD, name=CCOWMMCHANNEL)
    print("Clearing last stock update message in #%s" % channel)
    await clear_history(channel)
    print("Starting WMM stock background task")
    message = await channel.send('Stock Bot initialized, preparing for WMM stock update.')
    wmm_stock.start(message, channel, ccochannel)


def chunk(chunk_list, max_size=10):
    """
    Take an input list, and an expected max_size.

    :returns: A chunked list that is yielded back to the caller
    :rtype: iterator
    """
    for i in range(0, len(chunk_list), max_size):
        yield chunk_list[i:i + max_size]


async def clear_history(channel, limit=20):
    try:
        msgs = []
        async for message in channel.history(limit=limit):
            if message.author.name == bot.user.name:
                msgs.append(message)
        await channel.delete_messages(msgs)
    except:
        # discord doesn't let us delete history after 14 days, nothing we can do.
        pass


async def dm_bot_owner(carrierid, owner, message):
    try:
        ownerid = "".join(re.findall(r'\d+',str(owner)))
        if ENV == 'dev':
            ownerid = os.getenv('DEVOWNERID', None)
        ownerdm = bot.get_user(int(ownerid))
        await ownerdm.send(message)
        return True
    except Exception as e:
        # couldnt send a DM, most likely wrong owner supplied or discord perms.
        print("Could not notify carrier %s owner %s via DM: %s" % ( carrierid, owner, e))
        return False


def oauth_new(carrierid, force=False):
    pmeters = {'token': API_TOKEN}
    if force:
        pmeters['force'] = "true"
    r = requests.get(f"{API_HOST}/generate/{carrierid}",params=pmeters)
    return r


def capi(carrierid, dev=False):
    pmeters = {'token': API_TOKEN}
    if dev:
        pmeters['dev'] = "true"
    r = requests.get(f"{API_HOST}/capi/{carrierid}",params=pmeters)
    return r


# function taken from FCMS
def from_hex(mystr):
    try:
        return bytes.fromhex(mystr).decode('utf-8')
    except TypeError:
        return "Unregistered Carrier"
    except ValueError:
        return "Unregistered Carrier"


FCDATA = load_carrier_data(CARRIERS)
bot.run(TOKEN)
