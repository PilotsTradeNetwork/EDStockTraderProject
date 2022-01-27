# EDStockTracker Discord Bot
(yes, the repository is misspelt)

![image](https://user-images.githubusercontent.com/6062471/122630789-6d27e380-d094-11eb-9554-d185af5b69d2.png)


## Current Release Version: 2.0

This release brings Frontier cAPI support. Please note that due to a current bug with Epic Games authentication, we should continue to use Inara for EGS based carriers.

## Functionality

The EDStockTracker is a bot which allows fleet carrier owners to track the commodities present in their fleet carrier's markets via Discord. This can be done in a public discord server, or by PMing the bot on Discord. Upon command, the bot will post information about the fleet carrier's commodity market, such as what is being bought or sold, as well as their stock (for sell orders), and demand (for buy orders).

Currently, the bot accomplishes this by utilising EDSM, Inara, or cAPI to determine what is in the FLeet Carrier's market, though this information can often become out of date fast if it has been a while since a CMDR has docked with an EDDN uploader.

## 2.0 Rework / cAPI integration

cAPI stocks appear to be updated every ~60 minutes, but there is no timestamp for us to check when that has occured.

Once a carrier has been added using `;add_FC`, simply issue the `;capi_enable <carrier>` command to begin the authentication process.

After a successfull authentication and account link, the bot is able to retrieve stocks using cAPI for WMM and regular `;stock` commands.

Note: currently the `;stock` command defaults to EDSM, but you can use `;stock <carrier> capi` to force a fetch from the cAPI.\
This was done because during loading/unloading, a 60 minute delay was deemed ineffecient. This of course requires pilots to continue running EDMC.

Due to a current bug with Epic Games authentication, we should continue to use Inara for EGS based carriers.

## First time setup
Create a `.env` file with the following values:

```
DISCORD_TOKEN=YOUR_TOKEN_HERE
DISCORD_GUILD=SERVER_NAME_HERE
WMM_CHANNEL='CHANNEL HERE'
WMM_INTERVAL=3600
API_HOST=PTN2FDevAPI_HERE
API_TOKEN=API_TOKEN_HERE
```

The `.env` file can be set to read-only for the bot.

The tracked fleet carriers will be written to the `.carriers`, so ensure it has write permissions for the bot user.

# Required Permissions and Intents

The bot requires the following server permissions to function: (Permission Integer: 103079308352)
- Send Messages
- Public Threads
- Private Threads
- Manage Messages
- Embed Links
- Read Message History
- Add Reactions
- View Channels

As well, it requires the following intents:
- Presence Intent
- Server Members Intent

## Features, Commands, How-Tos
The EDStockTracker uses ';' as a prefix for commands. Example: `;ping`

### The ;help command
The `;help` command is your best friend when using the bot. By simply using the ;help command, you can find a list of commands available to you.\
Looking for help with a specific command? Simply add the desired command as an argument to your help command. Example: `;help add_FC`

### Adding a Fleet Carrier to the list of tracking ;add_FC
In order for EDStockTracker to be able to track the market of your Fleet Carrier, your carrier must first be added to the list of tracked carriers.\
To do this, you must use the `;add_FC` command. Here's how:

`;add_FC FCCode FCSystem FCalias Owner`
  
Where:\
FCCode is your Fleet Carrier's 6 digit ID code X9X-9Y9\
FCSystem is the system where your Fleet Carrier is located (If your Fleet Carrier is not found, look yourself up on www.edsm.net , and use the location that EDSM thinks you are at.\
FCalias is the name you will call your carrier by when using the ;stock command Example: ;stock FCalias\
Owner is a discord owner ID or @mention of the carrier owner, this is used for cAPI Auth and WMM low stock notifications.\

### Checking the list of tracked carriers ;list
The bot returns a list of all actively tracked carriers when sent the command ;list

### Checking a Fleet Carrier's stock ;stock
In order to check a carrier's stock, the carrier must be in the tracked list of carriers. Once this is done using the `;add_FC` command, simply check its stock by adding its alias as an argument.
Example: `;stock alias`

## WMM Stock Tracking
The bot can now track a group of carriers and automatically update stock levels in #wmm-stock

Use the following commands to set up stock tracking for existing Fleet Carriers.

### Start tracking a carrier for WMM
To begin tracking a Fleet Carrier, use the ;start_wmm_tracking command which takes arguments FCName Station Owner

Example: `;start_wmm_tracking gandalf malerba`

### Stop tracking a carrier or multiple carriers for WMM
To stop tracking a Fleet Carrier, use the ;stop_wmm_tracking command which takes a single argument of comma seperated carrier name(s)

Example: `;stop_wmm_tracking gandalf,cult,devastator,carrier1,carrier2`

### List only WMM tracked carriers
Example: `;list wmm`

### Get / Set the WMM update interval
To control the delay on updating stock levels in the #wmm-stock room.

Example: `;get_wmm_interval`

Example: `;set_wmm_interval 3800`

### Manually trigger an update of stock levels
To trigger an immediate update of stock levels use this command.

Example: `;wmm_stock`

### Check the status of the background task
To check if the background task is running or not (and restart it).

Example: `;wmm_status`

## Thanks

A sincere thankyou to the tools and people which make EDStockTracker's development possible, including:

- the Pilot's Trade Network
- www.edsm.net
- www.elitebgs.app
- www.eddb.io
